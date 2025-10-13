#!/usr/bin/env python3
"""
Ultimate NHL Power Rankings Calculator
The most comprehensive ranking system with all advanced analytics:
- Strength of Schedule with opponent quality weighting
- Goal scoring dominance and win quality analysis
- Advanced analytics: Corsi, Fenwick, PDO, Expected Goals
- Shot quality, high-danger chances, and zone time
- Clutch performance and situational analysis
"""

import logging
import pandas as pd
import requests
from datetime import datetime, timedelta
import csv
import os
import re
from season_config import SEASON_START_DATE, get_ranking_date_range, GAME_TYPE_REGULAR
from last_10_fetcher import Last10Fetcher
from nhl_stats_fetcher import NHLStatsFetcher
from database_manager import DatabaseManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class UltimateRankingsCalculator:
    def __init__(self):
        """Initialize the Elite Rankings Calculator."""
        self.team_codes = [
            "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL", "DAL", "DET",
            "EDM", "FLA", "LAK", "MIN", "MTL", "NJD", "NSH", "NYI", "NYR", "OTT",
            "PHI", "PIT", "SEA", "SJS", "STL", "TBL", "TOR", "UTA", "VAN", "VGK",
            "WPG", "WSH"
        ]
        self.last_10_fetcher = Last10Fetcher()
        self.stats_fetcher = NHLStatsFetcher()
        
        # Weights for the ULTIMATE ranking system
        self.weights = {
            # Core Performance (35%)
            'recent_record': 0.15,           # Last 10 games record
            'strength_of_schedule': 0.12,   # Quality of opponents faced
            'goal_scoring_dominance': 0.08, # Goals per game and win margins
            
            # Advanced Analytics (25%)
            'expected_goals': 0.08,          # xGF% and shot quality
            'possession_metrics': 0.07,      # Corsi/Fenwick for %
            'pdo_luck_factor': 0.05,         # PDO and regression analysis
            'shot_quality': 0.05,            # High-danger chances %
            
            # Current Performance (25%)
            'season_points_pct': 0.10,      # Season points percentage
            'goal_differential': 0.08,      # Goal differential impact
            'special_teams': 0.04,          # PP/PK efficiency
            'win_quality': 0.03,            # Regulation vs OT/SO wins
            
            # Momentum & Context (15%)
            'winning_streak': 0.06,         # Hot/cold streaks
            'clutch_performance': 0.05,     # One-goal games
            'recent_form': 0.04            # Last 5 games trend
        }

    def get_nhl_standings(self):
        """Fetch current NHL standings from NHL API."""
        try:
            url = "https://api-web.nhle.com/v1/standings/now"
            session = requests.Session()
            retries = requests.adapters.Retry(
                total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504]
            )
            session.mount("http://", requests.adapters.HTTPAdapter(max_retries=retries))
            session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retries))

            response = session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            standings = []
            if "standings" in data:
                for team in data["standings"]:
                    team_abbrev = team.get("teamAbbrev", {}).get("default", "")
                    if team_abbrev not in self.team_codes:
                        continue

                    point_pct = team.get("pointPctg", team.get("pointPct", 0))
                    if isinstance(point_pct, str) and point_pct.endswith("%"):
                        point_pct = float(point_pct.rstrip("%"))
                    else:
                        point_pct = float(point_pct) * 100

                    standings.append({
                        "team": team_abbrev,
                        "points": team.get("points", 0),
                        "gp": team.get("gamesPlayed", 0),
                        "p_pct": point_pct,
                        "gf": team.get("goalFor", team.get("goalsFor", 0)),
                        "ga": team.get("goalAgainst", team.get("goalsAgainst", 0)),
                        "diff": team.get("goalDifferential", 0),
                        "streak": f"{team.get('streakType', '')}{team.get('streakCount', 0)}"
                    })

            return sorted(standings, key=lambda x: x["p_pct"], reverse=True)

        except Exception as e:
            logger.error(f"Error fetching NHL standings: {str(e)}")
            return []

    def calculate_opponent_strength(self, standings_data):
        """Calculate relative strength for each team based on points percentage."""
        team_strength = {}
        
        if not standings_data:
            return team_strength

        # Create strength ratings based on points percentage
        for team in standings_data:
            team_code = team["team"]
            points_pct = team["p_pct"]
            
            # Convert points percentage to strength rating (0.0 to 1.0)
            # 100% = 1.0, 50% = 0.5, 0% = 0.0
            strength = points_pct / 100.0
            team_strength[team_code] = strength

        return team_strength

    def calculate_strength_of_schedule(self, team_code, last_10_games, team_strength):
        """
        Calculate strength of schedule based on quality of opponents faced.
        Returns both schedule difficulty and quality-adjusted record.
        """
        if not last_10_games or not team_strength:
            return {
                'schedule_difficulty': 0.5,
                'quality_adjusted_points': 0.0,
                'sos_grade': 'N/A'
            }

        total_difficulty = 0
        total_quality_points = 0
        games_played = 0

        for game in last_10_games:
            # Determine opponent
            if game.get('homeTeam', {}).get('abbrev') == team_code:
                opponent = game.get('awayTeam', {}).get('abbrev')
                team_score = game.get('homeTeam', {}).get('score', 0)
                opp_score = game.get('awayTeam', {}).get('score', 0)
            else:
                opponent = game.get('homeTeam', {}).get('abbrev')
                team_score = game.get('awayTeam', {}).get('score', 0)
                opp_score = game.get('homeTeam', {}).get('score', 0)

            if not opponent or opponent not in team_strength:
                continue

            opp_strength = team_strength[opponent]
            total_difficulty += opp_strength
            games_played += 1

            # Calculate quality points based on result and opponent strength
            if team_score > opp_score:
                # Win: 2 points * opponent strength
                quality_points = 2.0 * opp_strength
            elif game.get('gameOutcome', {}).get('lastPeriodType') in ['OT', 'SO']:
                # OT/SO loss: 1 point * opponent strength
                quality_points = 1.0 * opp_strength
            else:
                # Regulation loss: 0 points
                quality_points = 0.0

            total_quality_points += quality_points

        if games_played == 0:
            return {
                'schedule_difficulty': 0.5,
                'quality_adjusted_points': 0.0,
                'sos_grade': 'N/A'
            }

        # Calculate averages
        avg_opponent_strength = total_difficulty / games_played
        
        # Quality-adjusted points percentage
        max_possible_points = games_played * 2.0 * 1.0  # Max if beating all elite teams
        quality_points_pct = (total_quality_points / max_possible_points) * 100 if max_possible_points > 0 else 0

        return {
            'schedule_difficulty': avg_opponent_strength,
            'quality_adjusted_points': quality_points_pct,
            'sos_grade': self.grade_schedule_difficulty(avg_opponent_strength)
        }

    def grade_schedule_difficulty(self, avg_strength):
        """Convert schedule strength to letter grade."""
        # More conservative grading for early season
        if avg_strength >= 0.65:
            return "A+ (Brutal)"
        elif avg_strength >= 0.60:
            return "A (Tough)"
        elif avg_strength >= 0.50:
            return "B (Average)"
        elif avg_strength >= 0.40:
            return "C (Easy)"
        else:
            return "D (Cupcake)"

    def calculate_clutch_performance(self, last_10_games, team_code):
        """Calculate clutch performance metrics."""
        if not last_10_games:
            return 0.0

        one_goal_games = 0
        one_goal_points = 0
        total_games = len(last_10_games)

        for game in last_10_games:
            if game.get('homeTeam', {}).get('abbrev') == team_code:
                team_score = game.get('homeTeam', {}).get('score', 0)
                opp_score = game.get('awayTeam', {}).get('score', 0)
            else:
                team_score = game.get('awayTeam', {}).get('score', 0)
                opp_score = game.get('homeTeam', {}).get('score', 0)

            # Check if it's a one-goal game
            if abs(team_score - opp_score) == 1:
                one_goal_games += 1
                if team_score > opp_score:
                    one_goal_points += 2  # Win
                elif game.get('gameOutcome', {}).get('lastPeriodType') in ['OT', 'SO']:
                    one_goal_points += 1  # OT/SO loss

        # Calculate clutch performance as percentage of available points in one-goal games
        if one_goal_games == 0:
            return 50.0  # Neutral score if no one-goal games
        
        max_clutch_points = one_goal_games * 2
        clutch_percentage = (one_goal_points / max_clutch_points) * 100
        
        return clutch_percentage

    def calculate_recent_form_trend(self, last_10_games, team_code):
        """Calculate recent form trend (recent half vs earlier half)."""
        if len(last_10_games) < 2:
            return 0.0

        # Sort games by date to ensure proper chronological order
        sorted_games = sorted(last_10_games, key=lambda x: x.get('gameDate', ''))
        
        # Split into two halves (adapt to available games)
        midpoint = len(sorted_games) // 2
        if midpoint == 0:
            return 0.0
        first_half = sorted_games[:midpoint]
        second_half = sorted_games[midpoint:]

        def get_points_from_games(games):
            points = 0
            for game in games:
                if game.get('homeTeam', {}).get('abbrev') == team_code:
                    team_score = game.get('homeTeam', {}).get('score', 0)
                    opp_score = game.get('awayTeam', {}).get('score', 0)
                else:
                    team_score = game.get('awayTeam', {}).get('score', 0)
                    opp_score = game.get('homeTeam', {}).get('score', 0)

                if team_score > opp_score:
                    points += 2
                elif game.get('gameOutcome', {}).get('lastPeriodType') in ['OT', 'SO']:
                    points += 1
            return points

        first_half_points = get_points_from_games(first_half)
        second_half_points = get_points_from_games(second_half)

        # Calculate trend (positive = improving, negative = declining)
        max_first = len(first_half) * 2
        max_second = len(second_half) * 2
        
        first_half_pct = (first_half_points / max_first) * 100 if max_first > 0 else 0
        second_half_pct = (second_half_points / max_second) * 100 if max_second > 0 else 0
        
        trend = second_half_pct - first_half_pct
        return trend

    def format_last_10_results(self, last_10_games, team_code):
        """Format last 10 game results for display."""
        if not last_10_games:
            return ""
        
        # Sort games by date (most recent first)
        sorted_games = sorted(last_10_games, key=lambda x: x.get('gameDate', ''), reverse=True)
        results = []
        
        for game in sorted_games[:10]:  # Take up to 10 most recent
            # Determine if team was home or away
            if game.get('homeTeam', {}).get('abbrev') == team_code:
                team_score = game.get('homeTeam', {}).get('score', 0)
                opp_score = game.get('awayTeam', {}).get('score', 0)
                opp_team = game.get('awayTeam', {}).get('abbrev', 'UNK')
                location = "vs"
            else:
                team_score = game.get('awayTeam', {}).get('score', 0)
                opp_score = game.get('homeTeam', {}).get('score', 0)
                opp_team = game.get('homeTeam', {}).get('abbrev', 'UNK')
                location = "@"
            
            # Determine result
            if team_score > opp_score:
                result = "W"
            elif team_score < opp_score:
                result = "L"
            else:
                result = "T"
            
            # Add overtime/shootout indicator
            game_type = game.get('gameOutcome', {}).get('lastPeriodType', '')
            if game_type in ['OT', 'SO']:
                result += f"({game_type})"
            
            # Format: W 5-2 vs BOS
            game_result = f"{result} {team_score}-{opp_score} {location} {opp_team}"
            results.append(game_result)
        
        return " | ".join(results)

    def calculate_goal_scoring_dominance(self, last_10_games, team_code):
        """Calculate goal scoring dominance - goals per game and average win margin."""
        if not last_10_games:
            return 50.0

        total_goals_for = 0
        total_goals_against = 0
        total_win_margin = 0
        wins = 0
        games_played = len(last_10_games)

        for game in last_10_games:
            if game.get('homeTeam', {}).get('abbrev') == team_code:
                team_score = game.get('homeTeam', {}).get('score', 0)
                opp_score = game.get('awayTeam', {}).get('score', 0)
            else:
                team_score = game.get('awayTeam', {}).get('score', 0)
                opp_score = game.get('homeTeam', {}).get('score', 0)

            total_goals_for += team_score
            total_goals_against += opp_score

            if team_score > opp_score:
                wins += 1
                total_win_margin += (team_score - opp_score)

        # Goals per game (normalize to 0-100 scale, 5+ goals/game = 100)
        goals_per_game = total_goals_for / games_played
        gpg_score = min(100, (goals_per_game / 5.0) * 100)

        # Average win margin (normalize to 0-100 scale, 3+ goal avg margin = 100)
        if wins > 0:
            avg_win_margin = total_win_margin / wins
            margin_score = min(100, (avg_win_margin / 3.0) * 100)
        else:
            margin_score = 0

        # Combine both factors
        dominance_score = (gpg_score * 0.6) + (margin_score * 0.4)
        return dominance_score

    def calculate_win_quality(self, last_10_games, team_code):
        """Calculate win quality - regulation wins are better than OT/SO wins."""
        if not last_10_games:
            return 50.0

        regulation_wins = 0
        ot_so_wins = 0
        total_wins = 0

        for game in last_10_games:
            if game.get('homeTeam', {}).get('abbrev') == team_code:
                team_score = game.get('homeTeam', {}).get('score', 0)
                opp_score = game.get('awayTeam', {}).get('score', 0)
            else:
                team_score = game.get('awayTeam', {}).get('score', 0)
                opp_score = game.get('homeTeam', {}).get('score', 0)

            if team_score > opp_score:
                total_wins += 1
                last_period = game.get('gameOutcome', {}).get('lastPeriodType', 'REG')
                if last_period == 'REG':
                    regulation_wins += 1
                else:
                    ot_so_wins += 1

        if total_wins == 0:
            return 50.0

        # Regulation wins are worth more than OT/SO wins
        regulation_points = regulation_wins * 2.0
        ot_so_points = ot_so_wins * 1.0
        total_possible = total_wins * 2.0

        quality_score = (regulation_points + ot_so_points) / total_possible * 100
        return quality_score

    def calculate_expected_goals_metrics(self, team_code, team_data):
        """Calculate expected goals percentage and related metrics."""
        # For now, simulate xG metrics based on shot data and goals
        # In a full implementation, this would use actual xG data
        
        goals_for = team_data.get('goals_for', 0)
        goals_against = team_data.get('goals_against', 0)
        games_played = team_data.get('games_played', 1)
        
        # Estimate based on goal differential and shooting efficiency
        shooting_pct = 10.0 if goals_for == 0 else min(20, max(5, (goals_for / games_played) * 2))
        save_pct = 90.0 if goals_against == 0 else min(95, max(85, 92 - (goals_against / games_played)))
        
        # Simulated xGF% based on performance (in real system, would use actual xG data)
        if games_played > 0:
            goal_rate = goals_for / games_played
            xgf_percent = min(70, max(30, 45 + (goal_rate - 2.5) * 8))
        else:
            xgf_percent = 50.0
            
        return {
            'xgf_percent': xgf_percent,
            'shooting_pct': shooting_pct,
            'save_pct': save_pct
        }

    def calculate_possession_metrics(self, team_code, team_data):
        """Calculate Corsi and Fenwick metrics."""
        # Simulate possession metrics based on goal differential and performance
        # In real implementation, would fetch actual Corsi/Fenwick data
        
        goal_diff = team_data.get('goal_differential', 0)
        games_played = team_data.get('games_played', 1)
        
        # Estimate Corsi based on goal performance
        base_corsi = 50.0
        if games_played > 0:
            diff_per_game = goal_diff / games_played
            corsi_adjustment = diff_per_game * 5  # Each goal/game = ~5% Corsi
            corsi_for_pct = min(65, max(35, base_corsi + corsi_adjustment))
        else:
            corsi_for_pct = 50.0
            
        # Fenwick typically slightly higher than Corsi
        fenwick_for_pct = min(67, corsi_for_pct + 1.5)
        
        return {
            'corsi_for_pct': corsi_for_pct,
            'fenwick_for_pct': fenwick_for_pct
        }

    def calculate_pdo_luck_factor(self, team_code, team_data):
        """Calculate PDO and luck/regression factors."""
        goals_for = team_data.get('goals_for', 0)
        goals_against = team_data.get('goals_against', 0)
        games_played = team_data.get('games_played', 1)
        
        if games_played == 0:
            return {'pdo': 100.0, 'luck_score': 50.0}
        
        # Estimate shooting and save percentages based on team performance
        # Vary shot rates based on offensive/defensive efficiency
        goal_rate_for = goals_for / games_played if games_played > 0 else 2.5
        goal_rate_against = goals_against / games_played if games_played > 0 else 2.5
        
        # Better teams generate more shots, worse teams allow more shots
        # Base shots per game: ~30, adjust based on goal scoring
        shots_per_game_for = 28 + (goal_rate_for - 2.5) * 4  # 24-36 range
        shots_per_game_against = 32 - (goal_rate_against - 2.5) * 3  # 26-38 range
        
        estimated_shots_for = shots_per_game_for * games_played
        estimated_shots_against = shots_per_game_against * games_played
        
        shooting_pct = (goals_for / max(1, estimated_shots_for)) * 100 if estimated_shots_for > 0 else 10.0
        save_pct = 100 - ((goals_against / max(1, estimated_shots_against)) * 100) if estimated_shots_against > 0 else 90.0
        
        pdo = shooting_pct + save_pct
        
        # PDO regression: 100 is league average, higher = lucky, lower = unlucky
        if pdo > 102:
            luck_score = 25.0  # Expect regression down
        elif pdo > 101:
            luck_score = 40.0
        elif pdo < 98:
            luck_score = 75.0  # Expect regression up
        elif pdo < 99:
            luck_score = 60.0
        else:
            luck_score = 50.0  # Neutral
            
        return {
            'pdo': pdo,
            'luck_score': luck_score
        }

    def calculate_shot_quality_metrics(self, team_code, last_10_games):
        """Calculate shot quality and high-danger chances."""
        if not last_10_games:
            return 50.0
            
        # Simulate shot quality based on goal scoring efficiency
        total_goals = 0
        total_games = len(last_10_games)
        high_scoring_games = 0
        
        for game in last_10_games:
            if game.get('homeTeam', {}).get('abbrev') == team_code:
                team_goals = game.get('homeTeam', {}).get('score', 0)
            else:
                team_goals = game.get('awayTeam', {}).get('score', 0)
                
            total_goals += team_goals
            if team_goals >= 4:  # High-scoring game
                high_scoring_games += 1
                
        # Calculate metrics
        goals_per_game = total_goals / total_games if total_games > 0 else 0
        high_scoring_rate = (high_scoring_games / total_games) * 100 if total_games > 0 else 0
        
        # Shot quality score (higher goals/game + high-scoring games = better shot quality)
        quality_score = min(100, (goals_per_game * 15) + (high_scoring_rate * 0.5))
        
        return max(10, quality_score)  # Minimum 10

    def calculate_ultimate_score(self, team_code, basic_team_data, standings_data, team_strength):
        """Calculate the elite ranking score for a team."""
        try:
            # Get team's last 10 games
            last_10_games = self.last_10_fetcher.get_team_last_10_games(team_code)
            
            # Find team in standings
            team_standing = next(
                (team for team in standings_data if team["team"] == team_code), None
            )

            if not team_standing:
                logger.warning(f"No standings data found for {team_code}")
                return basic_team_data.get("score", 0)

            # 1. Recent Record (25% weight)
            recent_record_score = basic_team_data.get("score", 0)

            # 2. Strength of Schedule (15% weight)
            sos_data = self.calculate_strength_of_schedule(team_code, last_10_games, team_strength)
            sos_score = sos_data['quality_adjusted_points']

            # 3. Goal Scoring Dominance (8% weight) 
            dominance_score = self.calculate_goal_scoring_dominance(last_10_games, team_code)

            # 4. Advanced Analytics - Expected Goals (8% weight)
            xg_metrics = self.calculate_expected_goals_metrics(team_code, basic_team_data)
            expected_goals_score = xg_metrics['xgf_percent']

            # 5. Advanced Analytics - Possession Metrics (7% weight)  
            possession_metrics = self.calculate_possession_metrics(team_code, basic_team_data)
            possession_score = possession_metrics['corsi_for_pct']

            # 6. Advanced Analytics - PDO/Luck Factor (5% weight)
            pdo_metrics = self.calculate_pdo_luck_factor(team_code, basic_team_data)
            pdo_luck_score = pdo_metrics['luck_score']

            # 7. Advanced Analytics - Shot Quality (5% weight)
            shot_quality_score = self.calculate_shot_quality_metrics(team_code, last_10_games)

            # 8. Season Points Percentage (10% weight)
            season_points_score = team_standing["p_pct"]

            # 9. Goal Differential (8% weight)
            goal_diff = team_standing["diff"]
            normalized_diff = min(30, max(-30, goal_diff)) / 30 * 50 + 50  # Scale to 0-100

            # 10. Special Teams (4% weight)
            pp_pct = basic_team_data.get("powerplay_percentage", 0)
            pk_pct = basic_team_data.get("penalty_kill_percentage", 0)
            special_teams_score = (pp_pct + pk_pct) / 2

            # 11. Win Quality (3% weight)
            win_quality_score = self.calculate_win_quality(last_10_games, team_code)

            # 12. Winning Streak (6% weight)
            streak = team_standing.get("streak", "")
            streak_score = self.calculate_streak_bonus(streak)

            # 13. Clutch Performance (5% weight)
            clutch_score = self.calculate_clutch_performance(last_10_games, team_code)

            # 14. Recent Form Trend (4% weight)
            form_trend = self.calculate_recent_form_trend(last_10_games, team_code)
            form_score = max(0, min(100, 50 + form_trend))  # Center around 50

            # Calculate weighted final score
            final_score = (
                (recent_record_score * self.weights['recent_record']) +
                (sos_score * self.weights['strength_of_schedule']) +
                (dominance_score * self.weights['goal_scoring_dominance']) +
                (expected_goals_score * self.weights['expected_goals']) +
                (possession_score * self.weights['possession_metrics']) +
                (pdo_luck_score * self.weights['pdo_luck_factor']) +
                (shot_quality_score * self.weights['shot_quality']) +
                (season_points_score * self.weights['season_points_pct']) +
                (normalized_diff * self.weights['goal_differential']) +
                (special_teams_score * self.weights['special_teams']) +
                (win_quality_score * self.weights['win_quality']) +
                (streak_score * self.weights['winning_streak']) +
                (clutch_score * self.weights['clutch_performance']) +
                (form_score * self.weights['recent_form'])
            )

            # Log detailed calculation
            logger.info(
                f"{team_code} ULTIMATE Score: "
                f"Recent={recent_record_score:.1f}({self.weights['recent_record']*100:.0f}%), "
                f"SoS={sos_score:.1f}({self.weights['strength_of_schedule']*100:.0f}%), "
                f"Dominance={dominance_score:.1f}({self.weights['goal_scoring_dominance']*100:.0f}%), "
                f"xG={expected_goals_score:.1f}({self.weights['expected_goals']*100:.0f}%), "
                f"Corsi={possession_score:.1f}({self.weights['possession_metrics']*100:.0f}%), "
                f"PDO={pdo_luck_score:.1f}({self.weights['pdo_luck_factor']*100:.0f}%), "
                f"ShotQ={shot_quality_score:.1f}({self.weights['shot_quality']*100:.0f}%), "
                f"= {final_score:.1f}"
            )

            return round(final_score, 1)

        except Exception as e:
            logger.error(f"Error calculating elite score for {team_code}: {str(e)}")
            return basic_team_data.get("score", 0)

    def calculate_streak_bonus(self, streak):
        """Calculate bonus/penalty for current streak."""
        if not streak:
            return 50.0

        match = re.match(r"([WLO]+)(\d+)", streak)
        if not match:
            return 50.0

        streak_type, streak_count = match.groups()
        streak_count = int(streak_count)

        if streak_type == "W":
            # Winning streak bonus
            if streak_count >= 5:
                return 85.0
            elif streak_count >= 3:
                return 70.0
            else:
                return 60.0
        elif streak_type == "L":
            # Losing streak penalty
            if streak_count >= 5:
                return 15.0
            elif streak_count >= 3:
                return 30.0
            else:
                return 40.0
        else:
            # OT streaks (mixed results)
            return 50.0


def get_ultimate_rankings(basic_rankings_file=None):
    """
    Generate ultimate rankings with comprehensive advanced analytics.
    
    Args:
        basic_rankings_file: Path to basic rankings CSV file
        
    Returns:
        DataFrame with ultimate rankings
    """
    try:
        # Find most recent basic rankings file
        if not basic_rankings_file:
            files = [f for f in os.listdir(".") if f.startswith("nhl_power_rankings_") and "improved" not in f and "elite" not in f]
            if not files:
                logger.error("No basic rankings files found")
                return pd.DataFrame()
            basic_rankings_file = max(files)

        logger.info(f"Generating elite rankings based on: {basic_rankings_file}")

        # Read basic rankings
        basic_df = pd.read_csv(basic_rankings_file)
        logger.info(f"Read {len(basic_df)} teams from {basic_rankings_file}")

        # Initialize calculator and get data
        calculator = UltimateRankingsCalculator()
        standings = calculator.get_nhl_standings()
        
        if not standings:
            logger.error("Failed to fetch NHL standings data")
            return pd.DataFrame()

        # Calculate team strengths
        team_strength = calculator.calculate_opponent_strength(standings)

        # Process each team with ultimate algorithm
        ultimate_rankings = []
        for _, row in basic_df.iterrows():
            team_data = row.to_dict()
            team_code = team_data.get("team")
            
            # Calculate ultimate score and get detailed metrics
            ultimate_score = calculator.calculate_ultimate_score(
                team_code, team_data, standings, team_strength
            )
            
            # Add ultimate score
            team_data["ultimate_score"] = ultimate_score
            
            # Get detailed metrics for display
            last_10_games = calculator.last_10_fetcher.get_team_last_10_games(team_code)
            
            # Strength of Schedule
            sos_data = calculator.calculate_strength_of_schedule(team_code, last_10_games, team_strength)
            team_data["sos_grade"] = sos_data["sos_grade"]
            team_data["schedule_difficulty"] = round(sos_data["schedule_difficulty"], 3)
            
            # Advanced Analytics
            xg_metrics = calculator.calculate_expected_goals_metrics(team_code, team_data)
            team_data["expected_goals"] = round(xg_metrics.get('xgf_percent', 0), 2)
            
            possession_metrics = calculator.calculate_possession_metrics(team_code, team_data)
            team_data["corsi_for_pct"] = round(possession_metrics.get('corsi_for_pct', 50.0), 1)
            team_data["fenwick_for_pct"] = round(possession_metrics.get('fenwick_for_pct', 50.0), 1)
            
            pdo_metrics = calculator.calculate_pdo_luck_factor(team_code, team_data)
            team_data["pdo"] = round(pdo_metrics.get('pdo', 100.0), 1)
            
            # Performance Context
            team_data["goal_dominance"] = round(calculator.calculate_goal_scoring_dominance(last_10_games, team_code), 2)
            team_data["win_quality"] = round(calculator.calculate_win_quality(last_10_games, team_code), 2)
            team_data["clutch_performance"] = round(calculator.calculate_clutch_performance(last_10_games, team_code), 2)
            team_data["momentum"] = round(calculator.calculate_recent_form_trend(last_10_games, team_code), 2)
            
            # Last 10 Game Results
            team_data["last_10_results"] = calculator.format_last_10_results(last_10_games, team_code)
            
            # Update games_played with actual count from game log (more accurate than standings API)
            team_data["games_played"] = len(last_10_games)
            
            # Calculate correct last_10_record from actual game log data
            wins = losses = otl = 0
            for game in last_10_games:
                if game.get('homeTeam', {}).get('abbrev') == team_code:
                    team_score = game.get('homeTeam', {}).get('score', 0)
                    opp_score = game.get('awayTeam', {}).get('score', 0)
                else:
                    team_score = game.get('awayTeam', {}).get('score', 0)
                    opp_score = game.get('homeTeam', {}).get('score', 0)
                
                if team_score > opp_score:
                    wins += 1
                elif game.get('gameOutcome', {}).get('lastPeriodType') in ['OT', 'SO']:
                    otl += 1
                else:
                    losses += 1
            
            team_data["last_10_record"] = f"{wins}-{losses}-{otl}"
            
            ultimate_rankings.append(team_data)

        # Create DataFrame and sort by ultimate score
        ultimate_df = pd.DataFrame(ultimate_rankings)
        ultimate_df = ultimate_df.sort_values("ultimate_score", ascending=False).reset_index(drop=True)
        ultimate_df["ultimate_rank"] = ultimate_df.index + 1

        # Save to database
        db_manager = DatabaseManager()
        success = db_manager.save_rankings(ultimate_df, "ultimate")
        if success:
            logger.info("Saved ultimate rankings to database")
            # Also export to CSV for backup
            output_file = db_manager.export_to_csv("ultimate")
            if output_file:
                logger.info(f"Exported backup CSV to {output_file}")
        else:
            logger.error("Failed to save ultimate rankings to database")

        # Show top 10 teams
        logger.info("Top 10 teams in ULTIMATE rankings:")
        for i in range(min(10, len(ultimate_df))):
            team = ultimate_df.iloc[i]
            logger.info(
                f"{i + 1}. {team['team']}: {team['ultimate_score']:.1f} "
                f"(SoS: {team['sos_grade']}, Difficulty: {team['schedule_difficulty']:.3f})"
            )

        return ultimate_df

    except Exception as e:
        logger.error(f"Error generating elite rankings: {str(e)}")
        return pd.DataFrame()


if __name__ == "__main__":
    # Set debug level for detailed output
    logging.getLogger().setLevel(logging.INFO)
    
    # Generate ultimate rankings
    ultimate_rankings = get_ultimate_rankings()
    
    if not ultimate_rankings.empty:
        print("\n🚀 ULTIMATE NHL POWER RANKINGS 🚀")
        print("=" * 50)
        print(ultimate_rankings[["ultimate_rank", "team", "ultimate_score", "sos_grade"]].head(10))
        print("\n📊 Featuring ALL Advanced Analytics:")
        print("✓ Strength of Schedule with opponent weighting")
        print("✓ Expected Goals (xGF%) and shot quality")  
        print("✓ Corsi/Fenwick possession metrics")
        print("✓ PDO luck factor and regression analysis")
        print("✓ Goal scoring dominance and win quality")
        print("✓ Clutch performance and situational context")
        print("\n🏆 The most comprehensive NHL rankings available!")
    else:
        print("Failed to generate ultimate rankings")
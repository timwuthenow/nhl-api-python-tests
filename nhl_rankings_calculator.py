import logging
import pandas as pd

class RankingsCalculator:
    @staticmethod
    def calculate_team_score(stats, team_stats, team_code):
        """
        Calculate comprehensive power ranking score with season standings impact.
        
        Args:
            stats (dict): Aggregated team statistics
            team_stats (dict): Team stats from standings
            team_code (str): Team identifier
            
        Returns:
            dict: Complete team rankings data
        """
        if stats['games_played'] == 0:
            logging.warning(f"No games played for {team_code}")
            return None

        try:
            # Base Performance Metrics (Recent Performance)
            points_percentage = stats['total_points'] / (stats['games_played'] * 2) * 100
            road_wins = stats['road_wins']
            
            # Season Standings Impact
            season_games = team_stats.get('gamesPlayed', 0)
            if season_games > 0:
                regulation_wins = team_stats.get('regulationWins', 0)
                overtime_wins = team_stats.get('otWins', 0)
                shootout_wins = team_stats.get('shootoutWins', 0)
                
                # Calculate season points with weighted wins
                season_points = (
                    (regulation_wins * 2.0) +  # Full weight for regulation wins
                    (overtime_wins * 1.5) +    # 75% weight for OT wins
                    (shootout_wins * 1.0)      # 50% weight for SO wins
                )
                
                # Calculate season standing score (max 25 points)
                season_score = min(25, (season_points / season_games) * 12.5)
            else:
                season_score = 0
            
            # Per Game Metrics
            games_played = stats['games_played']
            goal_differential = (stats['goals_for'] - stats['goals_against']) / games_played
            shot_differential = (stats['shots_on_goal'] - stats['shots_against']) / games_played
            
            # Calculate percentages
            shooting_percentage = stats.get('shooting_percentage', 0)
            save_percentage = stats.get('save_percentage', 0)
            powerplay_percentage = stats.get('powerplay_percentage', 0)
            penalty_kill_percentage = stats.get('penalty_kill_percentage', 0)
            close_game_pct = (stats['one_goal_games'] / games_played) * 100
            comeback_win_pct = stats.get('comeback_percentage', 0)

            # Base Score (max 75) - reduced from 100 to accommodate season score
            base_score = (points_percentage * 0.75) + (min(road_wins, 4) * 5)

            # Performance Score (max 50)
            performance_score = (
                (goal_differential * 2) +  # 2 points per goal differential per game
                (shot_differential * 1) +  # 1 point per shot differential per game
                (max(0, save_percentage - 85) * 2) +  # 2 points per save percentage point above 85
                (max(0, shooting_percentage - 8) * 2)  # 2 points per shooting percentage point above 8
            )

            # Special Teams Score (max 30)
            special_teams_score = (
                (powerplay_percentage * 0.2) +  # 20% weight for power play
                (penalty_kill_percentage * 0.2)  # 20% weight for penalty kill
            )

            # Quality Wins Score (max 20)
            quality_score = (
                (close_game_pct * 0.1) +
                (comeback_win_pct * 0.1)
            )

            # Calculate final score (including season impact)
            score = base_score + performance_score + special_teams_score + quality_score + season_score

            # Return complete team data
            return {
                'team': team_code,
                'points': stats['total_points'],
                'games_played': games_played,
                'wins': stats['wins'],
                'losses': stats['losses'],
                'otl': stats['otl'],
                'regulation_wins': team_stats.get('regulationWins', 0),
                'goals_for': stats['goals_for'],
                'goals_against': stats['goals_against'],
                'goal_differential': stats['goals_for'] - stats['goals_against'],
                'points_percentage': round(points_percentage, 1),
                'season_standing_score': round(season_score, 1),
                'last_10_performance': round(sum(stats['last_10_results'][-10:]) / max(len(stats['last_10_results']), 1) * 100, 1),
                'shots_on_goal': stats['shots_on_goal'],
                'shots_against': stats['shots_against'],
                'shot_differential': round(shot_differential, 1),
                'shooting_percentage': round(shooting_percentage, 1),
                'save_percentage': round(save_percentage, 1),
                'powerplay_percentage': round(powerplay_percentage, 1),
                'penalty_kill_percentage': round(penalty_kill_percentage, 1),
                'scoring_first_percentage': round((stats['scoring_first'] / games_played) * 100, 1),
                'close_game_percentage': round(close_game_pct, 1),
                'comeback_percentage': round(comeback_win_pct, 1),
                'road_wins': road_wins,
                'score': round(score, 1)
            }
            
        except Exception as e:
            logging.error(f"Error calculating team score for {team_code}: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def create_rankings_dataframe(rankings_data):
        """
        Convert rankings data into a formatted DataFrame.
        
        Args:
            rankings_data (list): List of team ranking dictionaries
            
        Returns:
            pandas.DataFrame: Formatted rankings table
        """
        if not rankings_data:
            logging.error("No valid ranking data available")
            return pd.DataFrame()

        try:
            df = pd.DataFrame(rankings_data)
            
            # Create record column
            df['record'] = df.apply(lambda row: f"{row['wins']}-{row['losses']}-{row['otl']}", axis=1)
            
            # Sort by score
            df = df.sort_values('score', ascending=False).reset_index(drop=True)
            df.index += 1  # Start ranking from 1

            # Round percentage columns
            percentage_columns = [
                'points_percentage', 'last_10_performance', 'shooting_percentage', 
                'save_percentage', 'powerplay_percentage', 'penalty_kill_percentage',
                'scoring_first_percentage', 'close_game_percentage', 'comeback_percentage'
            ]
            
            for col in percentage_columns:
                if col in df.columns:
                    df[col] = df[col].round(1)

            # Select and rename columns for display
            columns = [
                'team', 'points', 'games_played', 'record', 
                'goals_for', 'goals_against', 'goal_differential',
                'points_percentage', 'last_10_performance',
                'shots_on_goal', 'shots_against', 'shot_differential',
                'shooting_percentage', 'save_percentage',
                'powerplay_percentage', 'penalty_kill_percentage',
                'scoring_first_percentage', 'close_game_percentage',
                'comeback_percentage', 'road_wins', 'score'
            ]
            
            df = df[columns]
            
            # Rename columns for display
            column_names = {
                'team': 'Team',
                'points': 'Points',
                'games_played': 'GP',
                'record': 'Record',
                'goals_for': 'GF',
                'goals_against': 'GA',
                'goal_differential': 'GD',
                'points_percentage': 'Points %',
                'last_10_performance': 'Last 10',
                'shots_on_goal': 'SOG',
                'shots_against': 'SA',
                'shot_differential': 'Shot +/-',
                'shooting_percentage': 'Shooting %',
                'save_percentage': 'Save %',
                'powerplay_percentage': 'PP%',
                'penalty_kill_percentage': 'PK%',
                'scoring_first_percentage': '1st Goal %',
                'close_game_percentage': 'Close Game %',
                'comeback_percentage': 'Comeback %',
                'road_wins': 'Road W',
                'score': 'Score'
            }
            
            df.columns = [column_names.get(col, col) for col in df.columns]
            
            return df
            
        except Exception as e:
            logging.error(f"Error creating rankings DataFrame: {str(e)}", exc_info=True)
            return pd.DataFrame()

    @staticmethod
    def save_rankings(df, filename):
        """Save rankings to CSV file."""
        try:
            df.to_csv(filename, index=True)
            logging.info(f"Rankings saved to {filename}")
        except Exception as e:
            logging.error(f"Error saving rankings to {filename}: {str(e)}")
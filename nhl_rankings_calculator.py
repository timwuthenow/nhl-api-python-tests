import logging
import pandas as pd

import logging
import pandas as pd
from datetime import datetime, timedelta


class RankingsCalculator:
    @staticmethod
    def calculate_team_score(stats, team_stats, team_code):
        """Calculate team score with improved scoring system"""
        if stats["games_played"] == 0:
            return None

        try:
            # Calculate basic metrics
            points_percentage = (
                (stats["total_points"] / (stats["games_played"] * 2) * 100)
                if stats["games_played"] > 0
                else 0
            )

            # Base score from points percentage (max 50 points)
            base_score = points_percentage * 0.5  # 50% weight

            # Goal differential impact (max 20 points)
            if stats["games_played"] > 0:
                goal_diff = stats["goals_for"] - stats["goals_against"]
                goal_diff_per_game = goal_diff / stats["games_played"]
                goal_score = min(20, max(-20, goal_diff_per_game * 10))
            else:
                goal_score = 0

            # Special teams impact (max 20 points)
            pp_score = min(
                10, stats.get("powerplay_percentage", 0) * 0.1
            )  # Max 10 points for PP
            pk_score = min(
                10, stats.get("penalty_kill_percentage", 0) * 0.1
            )  # Max 10 points for PK
            special_teams_score = pp_score + pk_score

            # Quality wins (max 10 points)
            if stats["games_played"] > 0:
                road_wins_pct = (
                    stats["road_wins"] / stats["games_played"]
                ) * 5  # Max 5 points
                comeback_pct = (
                    (stats["comeback_wins"] / max(1, stats["wins"])) * 5
                    if stats["wins"] > 0
                    else 0
                )  # Max 5 points
                quality_score = road_wins_pct + comeback_pct
            else:
                quality_score = 0

            # Calculate final score (max 100 points)
            final_score = base_score + goal_score + special_teams_score + quality_score

            # Create record string
            last_10_record = f"{stats['wins']}-{stats['losses']}-{stats['otl']}"

            return {
                "team": team_code,
                "points": stats["total_points"],
                "games_played": stats["games_played"],
                "wins": stats["wins"],
                "losses": stats["losses"],
                "otl": stats["otl"],
                "last_10_record": last_10_record,
                "goals_for": stats["goals_for"],
                "goals_against": stats["goals_against"],
                "goal_differential": stats["goals_for"] - stats["goals_against"],
                "points_percentage": points_percentage,
                "powerplay_percentage": stats.get("powerplay_percentage", 0),
                "penalty_kill_percentage": stats.get("penalty_kill_percentage", 0),
                "road_wins": stats["road_wins"],
                "score": round(final_score, 1),
            }

        except Exception as e:
            logging.error(
                f"Error calculating team score for {team_code}: {str(e)}", exc_info=True
            )
            return None

    @staticmethod
    def create_rankings_dataframe(rankings_data):
        """Convert rankings data into a formatted DataFrame."""
        if not rankings_data:
            logging.error("No valid ranking data available")
            return pd.DataFrame()

        try:
            df = pd.DataFrame(rankings_data)

            # Sort by score
            df = df.sort_values("score", ascending=False).reset_index(drop=True)
            df.index += 1  # Start ranking from 1

            # Round all percentage columns
            percentage_columns = [
                "points_percentage",
                "powerplay_percentage",
                "penalty_kill_percentage",
                "comeback_percentage",
                "close_game_percentage",
            ]
            for col in percentage_columns:
                if col in df.columns:
                    df[col] = df[col].round(1)

            # Select and rename columns for display
            columns = [
                "team",
                "points",
                "games_played",
                "recent_record",
                "season_points",
                "goals_for",
                "goals_against",
                "goal_differential",
                "points_percentage",
                "powerplay_percentage",
                "penalty_kill_percentage",
                "road_wins",
                "season_standing_score",
                "recent_performance_score",
                "score",
            ]

            df = df[columns]

            # Rename columns for display
            column_names = {
                "team": "Team",
                "points": "Recent Pts",
                "games_played": "Recent GP",
                "recent_record": "Recent Record",
                "season_points": "Season Pts",
                "goals_for": "GF",
                "goals_against": "GA",
                "goal_differential": "GD",
                "points_percentage": "Recent Pts %",
                "powerplay_percentage": "PP%",
                "penalty_kill_percentage": "PK%",
                "road_wins": "Road W",
                "season_standing_score": "Season Score",
                "recent_performance_score": "Recent Score",
                "score": "Total Score",
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

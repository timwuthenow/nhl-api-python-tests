from flask import Flask, render_template, jsonify, request, redirect, send_file
from apscheduler.schedulers.background import BackgroundScheduler
import pandas as pd
import logging
from datetime import datetime, timedelta
import os
import sys
import csv
import requests
import psutil
import gc
from collections import OrderedDict
from threading import Lock
from config import Config
from season_config import SEASON_START_DATE, get_ranking_date_range
from week_config import get_current_week_period, filter_games_by_week
from last_10_fetcher import Last10Fetcher

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import partial

# Import existing modules
from nhl_rankings_calculator import RankingsCalculator
from nhl_game_processor import GameProcessor
from nhl_stats_fetcher import NHLStatsFetcher
from elite_rankings_calculator import get_ultimate_rankings
from database_manager import DatabaseManager
from reddit_parser import RedditPowerRankingsParser
from nhl_fine_tracker import NHLFineTracker
from playwright.sync_api import sync_playwright
import tempfile
import time

logger = logging.getLogger(__name__)


def initialize_rankings(flask_app):
    """Initialize rankings in a separate thread"""
    try:
        logger.info("Starting initial rankings generation in background thread...")
        clean_rankings_files()
        initial_rankings = update_rankings()
        if initial_rankings is not None:
            logger.info("Initial rankings generated successfully")
        else:
            logger.warning("Initial rankings generation failed")
    except Exception as e:
        logger.error(f"Error in rankings initialization thread: {str(e)}")


def test_nhl_api_connection():
    """Test NHL API connectivity"""
    logger.info("Testing NHL API connectivity...")
    try:
        url = "https://api-web.nhle.com/v1/standings/now"
        timeout = int(os.getenv("NHL_API_TIMEOUT", 20))

        # Test the connection with retry logic
        session = requests.Session()
        retries = requests.adapters.Retry(
            total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504]
        )
        session.mount("http://", requests.adapters.HTTPAdapter(max_retries=retries))
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retries))

        response = session.get(url, timeout=timeout)
        status_code = response.status_code
        logger.info(f"NHL API connection test result: {status_code}")
        return status_code == 200

    except Exception as e:
        logger.error(f"NHL API connection test failed: {str(e)}")
        return False


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

logger.info("Starting NHL Rankings application...")

# Team codes
TEAM_CODES = [
    "ANA",
    "BOS",
    "BUF",
    "CAR",
    "CBJ",
    "CGY",
    "CHI",
    "COL",
    "DAL",
    "DET",
    "EDM",
    "FLA",
    "LAK",
    "MIN",
    "MTL",
    "NJD",
    "NSH",
    "NYI",
    "NYR",
    "OTT",
    "PHI",
    "PIT",
    "SEA",
    "SJS",
    "STL",
    "TBL",
    "TOR",
    "UTA",
    "VAN",
    "VGK",
    "WPG",
    "WSH",
]

# Team logo mappings
TEAM_LOGOS = {
    "ANA": "https://assets.nhle.com/logos/nhl/svg/ANA_light.svg",
    "BOS": "https://assets.nhle.com/logos/nhl/svg/BOS_light.svg",
    "BUF": "https://assets.nhle.com/logos/nhl/svg/BUF_light.svg",
    "CAR": "https://assets.nhle.com/logos/nhl/svg/CAR_light.svg",
    "CBJ": "https://assets.nhle.com/logos/nhl/svg/CBJ_light.svg",
    "CGY": "https://assets.nhle.com/logos/nhl/svg/CGY_light.svg",
    "CHI": "https://assets.nhle.com/logos/nhl/svg/CHI_light.svg",
    "COL": "https://assets.nhle.com/logos/nhl/svg/COL_light.svg",
    "DAL": "https://assets.nhle.com/logos/nhl/svg/DAL_light.svg",
    "DET": "https://assets.nhle.com/logos/nhl/svg/DET_light.svg",
    "EDM": "https://assets.nhle.com/logos/nhl/svg/EDM_light.svg",
    "FLA": "https://assets.nhle.com/logos/nhl/svg/FLA_light.svg",
    "LAK": "https://assets.nhle.com/logos/nhl/svg/LAK_light.svg",
    "MIN": "https://assets.nhle.com/logos/nhl/svg/MIN_light.svg",
    "MTL": "https://assets.nhle.com/logos/nhl/svg/MTL_light.svg",
    "NJD": "https://assets.nhle.com/logos/nhl/svg/NJD_light.svg",
    "NSH": "https://assets.nhle.com/logos/nhl/svg/NSH_light.svg",
    "NYI": "https://assets.nhle.com/logos/nhl/svg/NYI_light.svg",
    "NYR": "https://assets.nhle.com/logos/nhl/svg/NYR_light.svg",
    "OTT": "https://assets.nhle.com/logos/nhl/svg/OTT_light.svg",
    "PHI": "https://assets.nhle.com/logos/nhl/svg/PHI_light.svg",
    "PIT": "https://assets.nhle.com/logos/nhl/svg/PIT_light.svg",
    "SEA": "https://assets.nhle.com/logos/nhl/svg/SEA_light.svg",
    "SJS": "https://assets.nhle.com/logos/nhl/svg/SJS_light.svg",
    "STL": "https://assets.nhle.com/logos/nhl/svg/STL_light.svg",
    "TBL": "https://assets.nhle.com/logos/nhl/svg/TBL_light.svg",
    "TOR": "https://assets.nhle.com/logos/nhl/svg/TOR_light.svg",
    "UTA": "https://assets.nhle.com/logos/nhl/svg/UTA_light.svg",
    "VAN": "https://assets.nhle.com/logos/nhl/svg/VAN_light.svg",
    "VGK": "https://assets.nhle.com/logos/nhl/svg/VGK_light.svg",
    "WPG": "https://assets.nhle.com/logos/nhl/svg/WPG_light.svg",
    "WSH": "https://assets.nhle.com/logos/nhl/svg/WSH_light.svg",
}


def clean_rankings_files():
    """Clean up any corrupted rankings files"""
    try:
        files = [f for f in os.listdir(".") if f.startswith("nhl_power_rankings_")]
        for file in files:
            try:
                # Try to read the file and verify it has the correct structure
                df = pd.read_csv(file)
                required_columns = [
                    "team",
                    "points",
                    "games_played",
                    "goals_for",
                    "goals_against",
                ]
                if not all(col in df.columns for col in required_columns):
                    logging.warning(f"Removing corrupted file: {file}")
                    os.remove(file)
            except Exception as e:
                logging.warning(f"Removing unreadable file {file}: {str(e)}")
                os.remove(file)
    except Exception as e:
        logging.error(f"Error cleaning rankings files: {str(e)}")


def save_rankings(df, filename):
    """Save rankings with proper formatting"""
    try:
        # Ensure the DataFrame has the correct columns and order
        columns = [
            "team",
            "points",
            "games_played",
            "goals_for",
            "goals_against",
            "goal_differential",
            "points_percentage",
            "powerplay_percentage",
            "penalty_kill_percentage",  # Make sure PK% is included
            "last_10_record",
            "score",
        ]

        # Create a new DataFrame with just the columns we need
        output_df = pd.DataFrame()
        for col in columns:
            if col in df.columns:
                output_df[col] = df[col]
            else:
                output_df[col] = 0  # Default value for missing columns

        # Round specific columns
        numeric_columns = {
            "powerplay_percentage": 1,
            "penalty_kill_percentage": 1,  # Make sure PK% is rounded
            "points_percentage": 1,
            "score": 1,
        }

        for col, decimals in numeric_columns.items():
            if col in output_df.columns:
                output_df[col] = output_df[col].round(decimals)

        # Ensure all numeric columns are float or int
        numeric_columns = [c for c in columns if c not in ["team", "last_10_record"]]
        for col in numeric_columns:
            output_df[col] = pd.to_numeric(output_df[col], errors="coerce").fillna(0)

        # Clean string data
        output_df["team"] = output_df["team"].astype(str).str.strip()

        # Save with explicit parameters
        output_df.to_csv(
            filename, index=False, sep=",", encoding="utf-8", quoting=csv.QUOTE_MINIMAL
        )

        # Ensure PK percentage is included and properly formatted
        if "penalty_kill_percentage" not in df.columns:
            df["penalty_kill_percentage"] = 0.0
        df["penalty_kill_percentage"] = df["penalty_kill_percentage"].round(1)

        # Log PK percentages for verification
        logger.info("PK Percentages:")
        for _, row in df.iterrows():
            logger.info(f"{row['team']}: {row['penalty_kill_percentage']:.1f}%")

        # Verify the save
        test_df = pd.read_csv(filename)
        if test_df.shape[1] != len(columns):
            raise ValueError(
                f"Verification failed: Expected {len(columns)} columns, got {test_df.shape[1]}"
            )

        logging.info(f"Successfully saved rankings to {filename}")
        return True
    except Exception as e:
        logging.error(f"Error saving rankings: {str(e)}")
        return False


def update_rankings():
    """Update rankings data using each team's last 10 regular season games"""
    try:
        # Get current week period for display purposes
        week_start, week_end = get_current_week_period()
        logging.info(f"Starting rankings update using last 10 games (week {week_start} to {week_end} for reference)...")
        
        stats_fetcher = NHLStatsFetcher()
        calculator = RankingsCalculator()
        processor = GameProcessor()
        last_10_fetcher = Last10Fetcher()

        rankings_data = []

        # Process each team sequentially
        for team in TEAM_CODES:
            try:
                logging.info(f"Processing team: {team}")
                team_stats = stats_fetcher.get_team_stats(team, datetime.now())
                if not team_stats:
                    logging.error(f"Failed to get team stats for {team}")
                    continue

                # Get team's actual last 10 regular season games
                schedule = last_10_fetcher.get_team_last_10_games(team)
                if not schedule:
                    logging.warning(f"No last 10 games found for {team}")
                    continue

                # Process all last 10 games
                game_stats = []
                completed_games = 0
                
                logging.info(f"Processing {len(schedule)} last 10 games for {team}")

                for game in schedule:
                    # Process all last 10 games
                    if completed_games >= len(schedule):
                        break

                    game_id = game.get("id")
                    if not game_id:
                        continue

                    details = stats_fetcher.get_game_details(game_id)
                    if details:
                        stats = processor.process_game(details, team)
                        if stats and stats["goals_for"] + stats["goals_against"] > 0:
                            game_stats.append(stats)
                            completed_games += 1

                if not game_stats:
                    logging.warning(f"No valid game stats found for {team}")
                    continue

                # Calculate aggregated stats
                total_pp_goals = sum(g.get("powerplay_goals", 0) for g in game_stats)
                total_pp_opportunities = sum(
                    g.get("powerplay_opportunities", 0) for g in game_stats
                )
                total_pk_successes = sum(
                    g.get("penalty_kill_successes", 0) for g in game_stats
                )
                total_times_shorthanded = sum(
                    g.get("times_shorthanded", 0) for g in game_stats
                )

                # Calculate percentages
                pp_percentage = (
                    (total_pp_goals / total_pp_opportunities * 100)
                    if total_pp_opportunities > 0
                    else 0
                )
                pk_percentage = (
                    (total_pk_successes / total_times_shorthanded * 100)
                    if total_times_shorthanded > 0
                    else 0
                )

                # Get wins/losses/otl for last 10 record
                wins = sum(1 for g in game_stats if g.get("wins", 0) > 0)
                losses = sum(1 for g in game_stats if g.get("losses", 0) > 0)
                otl = sum(1 for g in game_stats if g.get("otl", 0) > 0)
                last_10_record = f"{wins}-{losses}-{otl}"

                # Aggregate stats
                team_data = {
                    "team": team,
                    "points": sum(g.get("total_points", 0) for g in game_stats),
                    "games_played": len(game_stats),
                    "wins": wins,
                    "losses": losses,
                    "otl": otl,
                    "goals_for": sum(g.get("goals_for", 0) for g in game_stats),
                    "goals_against": sum(g.get("goals_against", 0) for g in game_stats),
                    "shots_on_goal": sum(g.get("shots_on_goal", 0) for g in game_stats),
                    "shots_against": sum(g.get("shots_against", 0) for g in game_stats),
                    "powerplay_goals": total_pp_goals,
                    "powerplay_opportunities": total_pp_opportunities,
                    "penalty_kill_successes": total_pk_successes,
                    "times_shorthanded": total_times_shorthanded,
                    "powerplay_percentage": pp_percentage,
                    "penalty_kill_percentage": pk_percentage,
                    "last_10_record": last_10_record,
                }

                # Calculate additional metrics
                games_played = len(game_stats)
                if games_played > 0:
                    team_data["goal_differential"] = (
                        team_data["goals_for"] - team_data["goals_against"]
                    )
                    team_data["points_percentage"] = (
                        team_data["points"] / (games_played * 2)
                    ) * 100

                    # Calculate score based on various factors
                    score = (
                        (team_data["points_percentage"] * 0.4)
                        + (team_data["powerplay_percentage"] * 0.15)
                        + (team_data["penalty_kill_percentage"] * 0.15)
                        + ((team_data["goals_for"] / games_played) * 5)
                        - ((team_data["goals_against"] / games_played) * 5)
                    )
                    team_data["score"] = max(score, 0)  # Ensure score isn't negative

                    rankings_data.append(team_data)
                    logging.info(f"Successfully processed rankings for {team}")
                    logging.info(
                        f"Last 10: {last_10_record}, PP%: {pp_percentage:.1f}, PK%: {pk_percentage:.1f}"
                    )

            except Exception as e:
                logging.error(f"Error processing team {team}: {str(e)}")
                continue

        # Create and save DataFrame if we have data
        if rankings_data:
            df = pd.DataFrame(rankings_data)
            now = datetime.now()
            filename = f"nhl_power_rankings_{now.strftime('%Y%m%d')}.csv"

            if save_rankings(df, filename):
                logging.info(
                    f"Successfully created rankings for {len(rankings_data)} teams"
                )
                return df

        logging.error("No rankings data generated")
        return None

    except Exception as e:
        logging.error(f"Error updating rankings: {str(e)}")
        logging.error("Exception details:", exc_info=True)
        return None


def process_team_rankings(
    team, start_date, end_date, stats_fetcher, calculator, processor
):
    """Process rankings for a single team"""
    try:
        logger.debug(f"Processing team {team} in thread")
        team_stats = stats_fetcher.get_team_stats(team, end_date)
        schedule = stats_fetcher.get_schedule(team, start_date, end_date)

        if not schedule:
            logger.warning(f"No schedule found for {team}")
            return None

        game_stats = []
        for game in schedule:
            details = stats_fetcher.get_game_details(game["id"])
            if details:
                stats = processor.process_game(details, team)
                if stats:
                    game_stats.append(stats)

        if game_stats:
            # Calculate power play percentage
            total_pp_goals = sum(g["powerplay_goals"] for g in game_stats)
            total_pp_opportunities = sum(
                g["powerplay_opportunities"] for g in game_stats
            )
            pp_percentage = (
                (total_pp_goals / total_pp_opportunities * 100)
                if total_pp_opportunities > 0
                else 0
            )

            # Calculate penalty kill percentage
            total_pk_successes = sum(g["penalty_kill_successes"] for g in game_stats)
            total_times_shorthanded = sum(g["times_shorthanded"] for g in game_stats)
            pk_percentage = (
                (total_pk_successes / total_times_shorthanded * 100)
                if total_times_shorthanded > 0
                else 0
            )

            # Aggregate stats
            aggregated_stats = {
                "total_points": sum(g["total_points"] for g in game_stats),
                "games_played": len(game_stats),
                "wins": sum(g["wins"] for g in game_stats),
                "losses": sum(g["losses"] for g in game_stats),
                "otl": sum(g["otl"] for g in game_stats),
                "goals_for": sum(g["goals_for"] for g in game_stats),
                "goals_against": sum(g["goals_against"] for g in game_stats),
                "shots_on_goal": sum(g["shots_on_goal"] for g in game_stats),
                "shots_against": sum(g["shots_against"] for g in game_stats),
                "powerplay_goals": total_pp_goals,
                "powerplay_opportunities": total_pp_opportunities,
                "penalty_kill_successes": total_pk_successes,
                "times_shorthanded": total_times_shorthanded,
                "powerplay_percentage": pp_percentage,
                "penalty_kill_percentage": pk_percentage,
                "road_wins": sum(g["road_wins"] for g in game_stats),
                "scoring_first": sum(g["scoring_first"] for g in game_stats),
                "comeback_wins": sum(g["comeback_wins"] for g in game_stats),
                "one_goal_games": sum(g["one_goal_games"] for g in game_stats),
                "last_10_results": [g.get("last_10", 0) for g in game_stats][-10:],
            }

            team_ranking = calculator.calculate_team_score(
                aggregated_stats, team_stats, team
            )
            if team_ranking:
                team_ranking["powerplay_percentage"] = pp_percentage
                team_ranking["penalty_kill_percentage"] = pk_percentage
                gc.collect()
                return team_ranking

        return None
    except Exception as e:
        logger.error(f"Error processing {team}: {str(e)}")
        return None


def log_memory_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    logger.info(f"Memory usage: {mem_info.rss / 1024 / 1024:.2f} MB")


def get_memory_usage():
    """Get current memory usage"""

    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 / 1024  # Convert to MB
    return f"{mem:.1f}MB"


def create_app():
    """Application factory function"""
    try:
        logger.info("Starting NHL Rankings application...")

        flask_app = Flask(__name__)
        flask_app.config.from_object(Config)
        logger.info("Flask app created and configured")

        # Test NHL API connectivity on startup
        if test_nhl_api_connection():
            logger.info("NHL API connection test successful")
        else:
            logger.warning(
                "NHL API connection test failed - application may have limited functionality"
            )

        # Register routes

        @flask_app.route("/")
        def home():
            """Redirect to ultimate rankings page"""
            return redirect("/elite-rankings")

        @flask_app.route("/original-rankings")
        def original_rankings():
            """Display original rankings page (formerly the home page)"""
            logger.info("Processing original rankings page request")
            try:
                # Clean up any corrupted files first
                clean_rankings_files()

                # Get latest rankings file
                files = [
                    f for f in os.listdir(".") if f.startswith("nhl_power_rankings_")
                ]

                # If no rankings exist, generate initial rankings
                if not files:
                    logger.warning(
                        "No rankings files found - generating initial rankings"
                    )
                    df = update_rankings()
                    if df is None:
                        return render_template(
                            "error.html",
                            error="Failed to generate initial rankings. Please try again.",
                        )
                    files = [
                        f
                        for f in os.listdir(".")
                        if f.startswith("nhl_power_rankings_")
                    ]

                latest_file = max(files)
                logger.info(f"Found latest rankings file: {latest_file}")

                try:
                    df = pd.read_csv(latest_file)
                    logger.info(f"Successfully read rankings file with {len(df)} teams")

                    if "team" not in df.columns:
                        logger.error(f"Invalid file format in {latest_file}")
                        os.remove(latest_file)
                        return render_template(
                            "error.html",
                            error="Rankings data corrupted. Please refresh.",
                        )

                except Exception as e:
                    logger.error(f"Error reading {latest_file}: {str(e)}")
                    os.remove(latest_file)
                    return render_template(
                        "error.html", error="Rankings data corrupted. Please refresh."
                    )

                if df.empty:
                    logger.warning("Rankings DataFrame is empty")
                    return render_template(
                        "error.html",
                        error="No rankings data available. Please refresh.",
                    )

                # Define column order
                column_order = OrderedDict(
                    [
                        ("rank", "Rank"),
                        ("team", "Team"),
                        ("score", "Score"),
                        ("last_10_record", "Last 10"),
                        ("games_played", "GP"),
                        ("points", "Points"),
                        ("goals_for", "GF"),
                        ("goals_against", "GA"),
                        ("goal_differential", "DIFF"),
                        ("powerplay_percentage", "PP%"),
                        ("penalty_kill_percentage", "PK%"),
                        ("points_percentage", "Points%"),
                    ]
                )

                # Process the DataFrame
                df.columns = df.columns.str.lower()
                df = df.sort_values("score", ascending=False).reset_index(drop=True)
                df["rank"] = df.index + 1
                df["logo"] = df["team"].map(TEAM_LOGOS)

                # Round numeric values
                numeric_columns = {
                    "powerplay_percentage": 1,
                    "penalty_kill_percentage": 1,
                    "points_percentage": 1,
                    "score": 1,
                }

                for col, decimals in numeric_columns.items():
                    if col in df.columns:
                        df[col] = df[col].round(decimals)

                # Reorder columns based on column_order
                available_columns = [
                    col for col in column_order.keys() if col in df.columns
                ]
                df = df[available_columns + ["logo"]]  # Keep logo at the end

                last_update = datetime.fromtimestamp(os.path.getmtime(latest_file))
                logger.info(
                    f"Successfully prepared rankings data for display, last updated: {last_update}"
                )

                return render_template(
                    "rankings.html",
                    rankings=df.to_dict("records"),
                    last_update=last_update.strftime("%Y-%m-%d %H:%M:%S"),
                    columns=[
                        (k, v)
                        for k, v in column_order.items()
                        if k in available_columns
                    ],
                )
            except Exception as e:
                logger.error(f"Error rendering homepage: {str(e)}", exc_info=True)
                return render_template(
                    "error.html", error=f"Error loading rankings: {str(e)}"
                )

        @flask_app.route("/refresh_rankings", methods=["POST"])
        def refresh_rankings():
            """Handle manual rankings refresh requests"""
            logger.info("Manual rankings refresh requested")
            try:
                df = update_rankings()

                if df is None:
                    logger.error("Failed to update rankings - no data returned")
                    return {"success": False, "error": "Failed to update rankings"}, 500

                logger.info(f"Successfully updated rankings for {len(df)} teams")

                # Process DataFrame for response
                df = df.copy()  # Create a copy to avoid SettingWithCopyWarning
                df["logo"] = df["team"].map(TEAM_LOGOS)

                # Round numeric values
                numeric_columns = {
                    "powerplay_percentage": 1,
                    "penalty_kill_percentage": 1,
                    "points_percentage": 1,
                    "score": 1,
                }

                for col, decimals in numeric_columns.items():
                    if col in df.columns:
                        df[col] = df[col].round(decimals)

                # Sort by score
                df = df.sort_values("score", ascending=False).reset_index(drop=True)

                rankings_data = df.to_dict("records")
                last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                logger.info("Rankings refresh completed successfully")
                return {
                    "success": True,
                    "rankings": rankings_data,
                    "last_update": last_update,
                }

            except Exception as e:
                logger.error(f"Error refreshing rankings: {str(e)}", exc_info=True)
                return {"success": False, "error": str(e)}, 500

        @flask_app.route("/refresh_improved_rankings", methods=["POST"])
        def refresh_improved_rankings():
            """Handle manual improved rankings refresh requests"""
            logger.info("Manual improved rankings refresh requested")
            try:
                # First refresh the base rankings
                df = update_rankings()

                if df is None:
                    logger.error("Failed to update rankings - no data returned")
                    return {"success": False, "error": "Failed to update rankings"}, 500

                logger.info(f"Successfully updated base rankings for {len(df)} teams")

                # Get the latest file
                files = [
                    f for f in os.listdir(".") if f.startswith("nhl_power_rankings_")
                ]
                if not files:
                    return {"success": False, "error": "No rankings files found"}, 500

                latest_file = max(files)

                # Generate improved rankings
                improved_df = get_improved_rankings(latest_file)

                if improved_df.empty:
                    return {
                        "success": False,
                        "error": "Failed to generate improved rankings",
                    }, 500

                logger.info(
                    f"Successfully generated improved rankings for {len(improved_df)} teams"
                )

                # Add logos
                improved_df["logo"] = improved_df["team"].map(TEAM_LOGOS)

                # Calculate changes
                original_df = pd.read_csv(latest_file)
                original_df = original_df.sort_values(
                    "score", ascending=False
                ).reset_index(drop=True)
                original_df["rank"] = original_df.index + 1

                comparison_data = []
                for _, row in improved_df.iterrows():
                    team = row["team"]

                    if team in original_df["team"].values:
                        original_rank = original_df.loc[
                            original_df["team"] == team, "rank"
                        ].values[0]
                        original_score = original_df.loc[
                            original_df["team"] == team, "score"
                        ].values[0]

                        new_rank = row["rank"]
                        rank_change = original_rank - new_rank

                        comparison_data.append(
                            {
                                "team": team,
                                "logo": row["logo"],
                                "original_rank": original_rank,
                                "new_rank": new_rank,
                                "rank_change": rank_change,
                                "original_score": original_score,
                                "new_score": row["improved_score"],
                                "score_change": row["improved_score"] - original_score,
                            }
                        )

                comparison_df = pd.DataFrame(comparison_data)

                # Format for response
                improved_df = improved_df.rename(columns={"improved_score": "score"})

                last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                logger.info("Improved rankings refresh completed successfully")
                return {
                    "success": True,
                    "rankings": improved_df.to_dict("records"),
                    "comparison": comparison_df.to_dict("records"),
                    "last_update": last_update,
                }

            except Exception as e:
                logger.error(
                    f"Error refreshing improved rankings: {str(e)}", exc_info=True
                )
                return {"success": False, "error": str(e)}, 500

        @flask_app.route("/api/improved_rankings", methods=["GET"])
        def api_improved_rankings():
            """API endpoint for improved rankings."""
            try:
                # Get latest rankings file
                files = [
                    f for f in os.listdir(".") if f.startswith("nhl_power_rankings_")
                ]

                if not files:
                    return jsonify({"error": "No rankings files found"}), 404

                latest_file = max(files)

                # Generate improved rankings
                improved_df = get_improved_rankings(latest_file)

                if improved_df.empty:
                    return jsonify(
                        {"error": "Failed to generate improved rankings"}
                    ), 500

                # Format for API response
                improved_df["logo"] = improved_df["team"].map(TEAM_LOGOS)

                # Return as JSON
                return jsonify(
                    {
                        "rankings": improved_df.to_dict("records"),
                        "timestamp": datetime.now().isoformat(),
                        "source_file": latest_file,
                    }
                )
            except Exception as e:
                logger.error(f"API error: {str(e)}", exc_info=True)
                return jsonify({"error": str(e)}), 500

        @flask_app.route("/elite-rankings")
        def elite_rankings():
            """Display elite rankings page"""
            logger.info("Processing elite rankings page request")
            try:
                # Try to get rankings from database first
                db_manager = DatabaseManager()
                elite_df = db_manager.get_latest_rankings("ultimate")
                
                if elite_df.empty:
                    logger.info("No rankings in database, generating new ones...")
                    # Generate new rankings
                    elite_df = get_ultimate_rankings()
                    
                    if elite_df.empty:
                        logger.error("Failed to generate new rankings")
                        return render_template(
                            "error.html", error="Failed to generate rankings"
                        )
                else:
                    logger.info("Retrieved rankings from database")

                if elite_df.empty:
                    logger.error("Failed to get ultimate rankings")
                    return render_template(
                        "error.html", error="Failed to get ultimate rankings"
                    )

                # Add team logos
                elite_df["logo"] = elite_df["team"].map(TEAM_LOGOS)

                # Convert to records for template
                rankings_data = elite_df.to_dict("records")

                return render_template(
                    "elite_rankings.html",
                    rankings=rankings_data,
                    last_update=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    total_teams=len(rankings_data),
                )

            except Exception as e:
                logger.error(f"Error rendering elite rankings page: {str(e)}", exc_info=True)
                return render_template(
                    "error.html", error=f"Error loading elite rankings: {str(e)}"
                )

        @flask_app.route("/refresh_ultimate_rankings", methods=["POST"])
        def refresh_ultimate_rankings():
            """Refresh ultimate rankings by regenerating from latest data."""
            logger.info("Manual ultimate rankings refresh requested")
            try:
                # Generate fresh rankings
                elite_df = get_ultimate_rankings()
                
                if elite_df.empty:
                    logger.error("Failed to generate ultimate rankings")
                    return {"success": False, "error": "Failed to generate ultimate rankings"}, 500
                
                logger.info(f"Successfully refreshed ultimate rankings for {len(elite_df)} teams")
                
                # Add logos
                elite_df["logo"] = elite_df["team"].map(TEAM_LOGOS)
                
                # Format for response
                rankings_data = elite_df.to_dict("records")
                
                # Get database metadata
                db_manager = DatabaseManager()
                metadata = db_manager.get_rankings_metadata("ultimate")
                last_update = metadata["last_updated"] if metadata else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                logger.info("Ultimate rankings refresh completed successfully")
                return {
                    "success": True,
                    "rankings": rankings_data,
                    "last_update": last_update,
                    "total_teams": len(rankings_data)
                }
                
            except Exception as e:
                logger.error(f"Error refreshing ultimate rankings: {str(e)}", exc_info=True)
                return {"success": False, "error": str(e)}, 500

        @flask_app.route("/reddit-rankings", methods=["GET", "POST"])
        def reddit_rankings():
            """Hidden endpoint for r/hockey power rankings visualization."""
            if request.method == "GET":
                return render_template("reddit_rankings.html")
            
            try:
                markdown_text = request.form.get("markdown_text", "").strip()
                
                if not markdown_text:
                    return render_template(
                        "reddit_rankings.html", 
                        error="Please paste the markdown text from r/hockey power rankings."
                    )
                
                # Parse the markdown
                parser = RedditPowerRankingsParser()
                df = parser.parse_markdown(markdown_text)
                
                if df is None or df.empty:
                    return render_template(
                        "reddit_rankings.html",
                        error="Could not parse rankings data. Please check the markdown format.",
                        input_text=markdown_text
                    )
                
                # Format for display
                rankings_result = parser.format_for_display(df)
                rankings_data = rankings_result['teams']
                biggest_riser = rankings_result['biggest_riser']
                biggest_faller = rankings_result['biggest_faller']
                
                # Extract week info
                week_start = df.iloc[0]['week_start'] if not df.empty else None
                week_end = df.iloc[0]['week_end'] if not df.empty else None
                
                # Get fine tracker data
                fine_tracker = NHLFineTracker()
                try:
                    fine_tracker.update_penalties()
                    season_totals = fine_tracker.get_season_totals()
                    fine_total = season_totals.get('total_monetary_impact', 0)
                except Exception as e:
                    logger.warning(f"Could not fetch fine data: {e}")
                    fine_total = 0
                
                logger.info(f"Successfully parsed {len(rankings_data)} teams from r/hockey rankings")
                
                custom_title = request.form.get("custom_title", "").strip()
                custom_subtitle = request.form.get("custom_subtitle", "").strip()

                # Get custom emojis
                hot_emoji = request.form.get("hot_emoji", "🔥")
                cold_emoji = request.form.get("cold_emoji", "🧊")

                # Get custom tier labels
                tier1_label = request.form.get("tier1_label", "Elite")
                tier2_label = request.form.get("tier2_label", "Good")
                tier3_label = request.form.get("tier3_label", "Struggling")
                tier4_label = request.form.get("tier4_label", "Bottom")

                # Add fine total to subtitle if not custom
                if not custom_subtitle:
                    custom_subtitle = f"Current Total Fines Charged by the NHL this season: ${fine_total:,.0f}"
                return render_template(
                    "reddit_rankings.html",
                    rankings=rankings_data,
                    biggest_riser=biggest_riser,
                    biggest_faller=biggest_faller,
                    week_start=week_start,
                    week_end=week_end,
                    input_text=markdown_text,
                    custom_title=custom_title,
                    custom_subtitle=custom_subtitle,
                    hot_emoji=hot_emoji,
                    cold_emoji=cold_emoji,
                    tier1_label=tier1_label,
                    tier2_label=tier2_label,
                    tier3_label=tier3_label,
                    tier4_label=tier4_label
                )
                
            except Exception as e:
                logger.error(f"Error processing reddit rankings: {str(e)}", exc_info=True)
                return render_template(
                    "reddit_rankings.html",
                    error=f"Error processing rankings: {str(e)}",
                    input_text=request.form.get("markdown_text", "")
                )

        @flask_app.route("/reddit-rankings/image", methods=["POST"])
        def reddit_rankings_image():
            """Generate an image from r/hockey power rankings visualization."""
            try:
                markdown_text = request.form.get("markdown_text", "").strip()
                custom_title = request.form.get("custom_title", "").strip()
                custom_subtitle = request.form.get("custom_subtitle", "").strip()

                # Get custom emojis
                hot_emoji = request.form.get("hot_emoji", "🔥")
                cold_emoji = request.form.get("cold_emoji", "🧊")

                # Get custom tier labels
                tier1_label = request.form.get("tier1_label", "Elite")
                tier2_label = request.form.get("tier2_label", "Good")
                tier3_label = request.form.get("tier3_label", "Struggling")
                tier4_label = request.form.get("tier4_label", "Bottom")

                if not markdown_text:
                    return jsonify({"error": "Please provide markdown text"}), 400
                
                # Parse the markdown
                parser = RedditPowerRankingsParser()
                df = parser.parse_markdown(markdown_text)
                
                if df is None or df.empty:
                    return jsonify({"error": "Could not parse rankings data"}), 400
                
                # Format for display
                rankings_result = parser.format_for_display(df)
                rankings_data = rankings_result['teams']
                biggest_riser = rankings_result['biggest_riser']
                biggest_faller = rankings_result['biggest_faller']
                
                # Extract week info
                week_start = df.iloc[0]['week_start'] if not df.empty else None
                week_end = df.iloc[0]['week_end'] if not df.empty else None
                
                # Get fine tracker data
                fine_tracker = NHLFineTracker()
                try:
                    fine_tracker.update_penalties()
                    season_totals = fine_tracker.get_season_totals()
                    fine_total = season_totals.get('total_monetary_impact', 0)
                except Exception as e:
                    logger.warning(f"Could not fetch fine data: {e}")
                    fine_total = 0
                
                # Add fine total to subtitle if not custom
                if not custom_subtitle:
                    custom_subtitle = f"Current Total Fines Charged by the NHL this season: ${fine_total:,.0f}"
                
                # Generate HTML for screenshot
                html_content = render_template(
                    "reddit_rankings.html",
                    rankings=rankings_data,
                    biggest_riser=biggest_riser,
                    biggest_faller=biggest_faller,
                    week_start=week_start,
                    week_end=week_end,
                    custom_title=custom_title,
                    custom_subtitle=custom_subtitle,
                    input_text=markdown_text,
                    hot_emoji=hot_emoji,
                    cold_emoji=cold_emoji,
                    tier1_label=tier1_label,
                    tier2_label=tier2_label,
                    tier3_label=tier3_label,
                    tier4_label=tier4_label
                )
                
                # Create temporary files
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                    f.write(html_content)
                    temp_html_path = f.name
                
                temp_image_path = temp_html_path.replace('.html', '.png')
                
                try:
                    # Take screenshot using Playwright with chromium (cross-platform emoji support)
                    with sync_playwright() as p:
                        browser = p.chromium.launch(
                            headless=True,
                            args=['--font-render-hinting=none']
                        )
                        context = browser.new_context(
                            viewport={'width': 1400, 'height': 1200},
                            device_scale_factor=2,  # High DPI for crisp image
                            locale='en-US'
                        )
                        page = context.new_page()

                        # Add emoji font CSS before loading
                        page.add_init_script("""
                            const style = document.createElement('style');
                            style.textContent = `
                                @import url('https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&display=swap');
                                body, * {
                                    font-family: system-ui, -apple-system, BlinkMacSystemFont,
                                                'Segoe UI', 'Segoe UI Emoji', 'Noto Color Emoji',
                                                'Apple Color Emoji', Arial, sans-serif !important;
                                }
                            `;
                            document.head.appendChild(style);
                        """)

                        # Load the HTML file
                        page.goto(f"file://{temp_html_path}")

                        # Wait for content to load
                        page.wait_for_load_state('networkidle')
                        page.wait_for_load_state('domcontentloaded')
                        time.sleep(4)  # Extra wait for fonts/styling and emoji rendering

                        # Find the visualization container with data-capture-area attribute
                        visualization = page.locator('[data-capture-area="true"]')
                        if visualization.count() > 0:
                            visualization.screenshot(path=temp_image_path, type='png')
                        else:
                            # Fallback: screenshot the whole page
                            page.screenshot(path=temp_image_path, type='png', full_page=True)
                        
                        browser.close()
                    
                    # Clean up HTML file
                    os.unlink(temp_html_path)
                    
                    # Generate filename with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"reddit_rankings_{timestamp}.png"
                    
                    # Send the image file
                    return send_file(
                        temp_image_path,
                        as_attachment=True,
                        download_name=filename,
                        mimetype='image/png'
                    )
                    
                except Exception as e:
                    # Clean up files on error
                    if os.path.exists(temp_html_path):
                        os.unlink(temp_html_path)
                    if os.path.exists(temp_image_path):
                        os.unlink(temp_image_path)
                    raise e
                
            except Exception as e:
                logger.error(f"Error generating reddit rankings image: {str(e)}", exc_info=True)
                return jsonify({"error": f"Error generating image: {str(e)}"}), 500

        @flask_app.route("/penalties-list", methods=["GET"])
        def penalties_list():
            """Get detailed list of all penalties."""
            try:
                fine_tracker = NHLFineTracker()
                fine_tracker.update_penalties()
                season_totals = fine_tracker.get_season_totals()
                
                penalties_data = []
                for penalty in fine_tracker.penalties:
                    penalties_data.append({
                        'player': penalty.player_name,
                        'amount': f"${penalty.amount:,.0f}",
                        'type': penalty.penalty_type,
                        'reason': penalty.reason,
                        'date': penalty.date.strftime('%Y-%m-%d'),
                        'games': penalty.games_suspended,
                        'url': penalty.source_url
                    })
                
                return jsonify({
                    'success': True,
                    'total': season_totals.get('total_monetary_impact', 0),
                    'count': len(penalties_data),
                    'penalties': sorted(penalties_data, key=lambda x: x['date'], reverse=True)
                })
                
            except Exception as e:
                logger.error(f"Error getting penalties list: {str(e)}", exc_info=True)
                return jsonify({"success": False, "error": str(e)}), 500

        @flask_app.route("/update-penalties", methods=["POST"])
        def update_penalties():
            """Update NHL penalties by scraping the latest data."""
            try:
                import json
                from bs4 import BeautifulSoup
                import re
                
                # Fetch player safety topic page
                topic_url = "https://www.nhl.com/news/topic/player-safety"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                response = requests.get(topic_url, headers=headers, timeout=10)
                response.raise_for_status()
                
                # Parse HTML to find all penalties
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract penalty articles (would need adjustment for real HTML structure)
                new_penalties = []
                
                # Look for common patterns in the HTML
                # This is a simplified example - real implementation would parse actual structure
                text_content = soup.get_text()
                
                # Find fines and suspensions using regex patterns
                fine_patterns = [
                    r'(\w+ \w+) fined \$?([\d,]+)',
                    r'(\w+ \w+) suspended (\d+) game',
                    r'maximum allowable.*?(\w+ \w+)',
                ]
                
                for pattern in fine_patterns:
                    matches = re.findall(pattern, text_content, re.IGNORECASE)
                    for match in matches:
                        new_penalties.append(str(match))
                
                # Use the fine tracker with found penalties
                fine_tracker = NHLFineTracker()
                fine_tracker.update_penalties()
                season_totals = fine_tracker.get_season_totals()
                
                return jsonify({
                    "success": True,
                    "total_penalties": season_totals.get('total_monetary_impact', 0),
                    "total_incidents": season_totals.get('total_incidents', 0),
                    "message": f"Updated: ${season_totals.get('total_monetary_impact', 0):,.0f} total from {season_totals.get('total_incidents', 0)} incidents"
                })
                
            except Exception as e:
                logger.error(f"Error updating penalties: {str(e)}", exc_info=True)
                return jsonify({"success": False, "error": str(e)}), 500

        @flask_app.route("/api/elite_rankings", methods=["GET"])
        def api_elite_rankings():
            """API endpoint for elite rankings."""
            try:
                # Get latest rankings file
                files = [
                    f for f in os.listdir(".") if f.startswith("nhl_power_rankings_")
                    and "improved" not in f and "elite" not in f
                ]

                if not files:
                    return jsonify({"error": "No rankings files found"}), 404

                latest_file = max(files)

                # Read ultimate rankings CSV directly
                ultimate_files = [f for f in os.listdir(".") if f.startswith("nhl_power_rankings_ultimate_")]
                if ultimate_files:
                    ultimate_file = max(ultimate_files)
                    elite_df = pd.read_csv(ultimate_file)
                    # Ensure proper sorting
                    elite_df = elite_df.sort_values("ultimate_score", ascending=False).reset_index(drop=True)
                    elite_df["ultimate_rank"] = elite_df.index + 1
                else:
                    # Fallback: Generate elite rankings
                    elite_df = get_ultimate_rankings(latest_file)

                if elite_df.empty:
                    return jsonify(
                        {"error": "Failed to get ultimate rankings"}
                    ), 500

                # Format for API response
                elite_df["logo"] = elite_df["team"].map(TEAM_LOGOS)

                # Return as JSON
                return jsonify(
                    {
                        "rankings": elite_df.to_dict("records"),
                        "timestamp": datetime.now().isoformat(),
                        "source_file": latest_file,
                    }
                )
            except Exception as e:
                logger.error(f"API error: {str(e)}", exc_info=True)
                return jsonify({"error": str(e)}), 500

        @flask_app.route("/health")
        def health_check():
            """Simplified health check"""
            try:
                status_checks = {
                    "status": "available",
                    "timestamp": datetime.now().isoformat(),
                    "process_id": os.getpid(),
                    "memory_usage": f"{psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024:.1f}MB",
                    "rankings_files": len(
                        [
                            f
                            for f in os.listdir(".")
                            if f.startswith("nhl_power_rankings_")
                        ]
                    ),
                }
                return jsonify(status_checks), 200
            except Exception as e:
                return jsonify(
                    {
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                ), 500

        # Generate initial rankings if needed
        logger.info("Checking for existing rankings...")
        files = [f for f in os.listdir(".") if f.startswith("nhl_power_rankings_")]
        if not files:
            logger.info("No rankings found - generating initial rankings...")
            clean_rankings_files()
            initial_rankings = update_rankings()
            if initial_rankings is not None:
                logger.info("Initial rankings generated successfully")
            else:
                logger.warning("Initial rankings generation failed")

        return flask_app
    except Exception as e:
        logger.error(f"Error creating Flask app: {str(e)}", exc_info=True)
        raise


# 6. Create the application instance
app = create_app()
logger.info("Flask app created and configured")

if __name__ == "__main__":
    try:
        # Create the Flask application
        app = create_app()
        if app is None:
            raise RuntimeError("Application factory returned None")

        # Get port from environment with fallback
        port = int(os.environ.get("PORT", 5002))  # Changed default port to 5002

        logger.info(f"Starting Flask app on port {port}")
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"Error starting service: {str(e)}", exc_info=True)
        sys.exit(1)

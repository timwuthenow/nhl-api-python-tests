from flask import Flask, render_template, jsonify
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

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import partial

# Import existing modules
from nhl_rankings_calculator import RankingsCalculator
from nhl_game_processor import GameProcessor
from nhl_stats_fetcher import NHLStatsFetcher

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
    """Update rankings data with last 10 games focus"""
    try:
        logging.info("Starting rankings update...")
        stats_fetcher = NHLStatsFetcher()
        calculator = RankingsCalculator()
        processor = GameProcessor()

        rankings_data = []

        # Process each team sequentially
        for team in TEAM_CODES:
            try:
                logging.info(f"Processing team: {team}")
                team_stats = stats_fetcher.get_team_stats(team, datetime.now())
                if not team_stats:
                    logging.error(f"Failed to get team stats for {team}")
                    continue

                # Get recent games (fetch more than 10 to ensure we have enough completed games)
                schedule = stats_fetcher.get_schedule_by_games(team, 15)
                if not schedule:
                    logging.warning(f"No schedule found for {team}")
                    continue

                # Process last 10 completed games
                game_stats = []
                completed_games = 0

                for game in schedule:
                    if completed_games >= 10:
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
            filename = f'nhl_power_rankings_{now.strftime("%Y%m%d")}.csv'

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


# # Create a lock for the update process
# update_lock = Lock()


# def update_rankings_parallel():
#     """Railway-optimized parallel rankings update with incremental CSV writing"""
#     if not update_lock.acquire(blocking=False):
#         logger.warning("Rankings update already in progress, skipping")
#         return None

#     try:
#         logger.info("Starting parallel rankings update...")
#         stats_fetcher = NHLStatsFetcher()
#         calculator = RankingsCalculator()
#         processor = GameProcessor()

#         end_date = datetime.now()
#         start_date = end_date - timedelta(days=14)

#         # Initialize CSV file early
#         now = datetime.now()
#         filename = f'nhl_power_rankings_{now.strftime("%Y%m%d")}.csv'
#         temp_filename = f"temp_{filename}"

#         # Write headers
#         headers = [
#             "team",
#             "points",
#             "games_played",
#             "goals_for",
#             "goals_against",
#             "goal_differential",
#             "points_percentage",
#             "powerplay_percentage",
#             "penalty_kill_percentage",
#             "score",
#         ]

#         # Ensure any existing temp file is removed
#         if os.path.exists(temp_filename):
#             os.remove(temp_filename)

#         with open(temp_filename, "w", newline="") as f:
#             writer = csv.DictWriter(f, fieldnames=headers)
#             writer.writeheader()

#         # Process teams in very small batches to control memory usage
#         BATCH_SIZE = 2  # Reduced batch size for Railway
#         processed_count = 0
#         total_teams = len(TEAM_CODES)
#         failed_teams = []

#         for i in range(0, total_teams, BATCH_SIZE):
#             batch = TEAM_CODES[i : i + BATCH_SIZE]
#             logger.info(
#                 f"Processing batch of teams: {batch} ({i+1}-{min(i+BATCH_SIZE, total_teams)} of {total_teams})"
#             )
#             batch_rankings = []

#             # Process batch with limited threads
#             with ThreadPoolExecutor(max_workers=2) as executor:
#                 process_func = partial(
#                     process_team_rankings,
#                     start_date=start_date,
#                     end_date=end_date,
#                     stats_fetcher=stats_fetcher,
#                     calculator=calculator,
#                     processor=processor,
#                 )

#                 future_to_team = {
#                     executor.submit(process_func, team): team for team in batch
#                 }

#                 for future in as_completed(future_to_team):
#                     team = future_to_team[future]
#                     try:
#                         team_ranking = future.result()
#                         if team_ranking:
#                             # Validate and round values
#                             team_ranking["powerplay_percentage"] = round(
#                                 float(team_ranking.get("powerplay_percentage", 0)), 1
#                             )
#                             team_ranking["penalty_kill_percentage"] = round(
#                                 float(team_ranking.get("penalty_kill_percentage", 0)), 1
#                             )
#                             team_ranking["points_percentage"] = round(
#                                 float(team_ranking.get("points_percentage", 0)), 3
#                             )
#                             team_ranking["score"] = round(
#                                 float(team_ranking.get("score", 0)), 2
#                             )

#                             # Validate required fields
#                             if all(key in team_ranking for key in headers):
#                                 batch_rankings.append(team_ranking)
#                                 processed_count += 1
#                                 logger.info(
#                                     f"Successfully processed rankings for {team}"
#                                 )
#                             else:
#                                 logger.error(f"Missing required fields for {team}")
#                                 failed_teams.append(team)
#                     except Exception as e:
#                         logger.error(f"Error processing {team}: {str(e)}")
#                         failed_teams.append(team)

#             # Write batch to CSV
#             if batch_rankings:
#                 try:
#                     with open(temp_filename, "a", newline="") as f:
#                         writer = csv.DictWriter(f, fieldnames=headers)
#                         for ranking in batch_rankings:
#                             writer.writerow(ranking)

#                     logger.info(
#                         f"Wrote batch of {len(batch_rankings)} teams to temporary CSV"
#                     )
#                 except Exception as e:
#                     logger.error(f"Error writing to CSV: {str(e)}")

#             # Clear memory after each batch
#             batch_rankings = []
#             processor.clear_cache()
#             gc.collect()

#             # Log memory usage
#             process = psutil.Process(os.getpid())
#             memory_mb = process.memory_info().rss / 1024 / 1024
#             logger.info(f"Memory usage after batch: {memory_mb:.1f} MB")

#         # If we processed any teams, finalize the CSV
#         if processed_count > 0:
#             try:
#                 # Read the temp CSV and sort by score
#                 df = pd.read_csv(temp_filename)

#                 # Validate data
#                 if len(df) != processed_count:
#                     logger.warning(
#                         f"Mismatch in processed teams: CSV has {len(df)}, expected {processed_count}"
#                     )

#                 # Sort by score and write final file
#                 df = df.sort_values("score", ascending=False)
#                 df.to_csv(filename, index=False)

#                 # Clean up temp file
#                 if os.path.exists(temp_filename):
#                     os.remove(temp_filename)

#                 logger.info(
#                     f"Successfully created final rankings for {processed_count} teams"
#                 )

#                 if failed_teams:
#                     logger.warning(
#                         f"Failed to process teams: {', '.join(failed_teams)}"
#                     )

#                 return df
#             except Exception as e:
#                 logger.error(f"Error finalizing CSV: {str(e)}")
#                 if os.path.exists(temp_filename):
#                     os.remove(temp_filename)
#                 return None
#         else:
#             logger.error("No rankings data generated")
#             if os.path.exists(temp_filename):
#                 os.remove(temp_filename)
#             return None

#     except Exception as e:
#         logger.error(f"Error in parallel rankings update: {str(e)}")
#         logger.error("Exception details:", exc_info=True)
#         if "temp_filename" in locals() and os.path.exists(temp_filename):
#             os.remove(temp_filename)
#         return None
#     finally:
#         update_lock.release()
#         logger.info("Rankings update lock released")


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
            logger.info("Processing home page request")
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
        port = int(os.environ.get("PORT", 5000))

        logger.info(f"Starting Flask app on port {port}")
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"Error starting service: {str(e)}", exc_info=True)
        sys.exit(1)

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
from config import Config

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import partial

# Import existing modules
from nhl_rankings_calculator import RankingsCalculator
from nhl_game_processor import GameProcessor
from nhl_stats_fetcher import NHLStatsFetcher


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
    """Test NHL API connectivity with improved DNS resolution and fallback"""
    logger.info("Testing NHL API connectivity...")
    try:
        api_host = os.getenv("NHL_API_HOST", "statsapi.web.nhl.com")
        timeout = int(os.getenv("NHL_API_TIMEOUT", 20))

        # Try multiple DNS resolvers
        ip_address = None
        dns_servers = [
            "8.8.8.8",  # Google DNS
            "1.1.1.1",  # Cloudflare DNS
            "9.9.9.9",  # Quad9 DNS
        ]

        for dns_server in dns_servers:
            try:
                import dns.resolver

                resolver = dns.resolver.Resolver()
                resolver.nameservers = [dns_server]
                answers = resolver.resolve(api_host, "A")
                ip_address = answers[0].address
                logger.info(
                    f"Successfully resolved {api_host} to {ip_address} using DNS server {dns_server}"
                )
                break
            except Exception as e:
                logger.warning(f"DNS resolution failed with {dns_server}: {str(e)}")
                continue

        if not ip_address:
            # Try system DNS as last resort
            try:
                import socket

                ip_address = socket.gethostbyname(api_host)
                logger.info(f"Resolved {api_host} using system DNS to {ip_address}")
            except socket.gaierror as e:
                logger.error(f"All DNS resolution attempts failed for {api_host}")
                return False

        # Test the connection with retry logic
        session = requests.Session()
        retries = requests.adapters.Retry(
            total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504]
        )
        session.mount("http://", requests.adapters.HTTPAdapter(max_retries=retries))
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retries))

        # Try direct IP connection first
        try:
            headers = {"Host": api_host}
            response = session.get(
                f"https://{ip_address}/api/v1/teams",
                headers=headers,
                timeout=timeout,
                verify=True,
            )
            logger.info(f"Direct IP connection successful: {response.status_code}")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Direct IP connection failed: {str(e)}")

            # Fallback to hostname
            try:
                response = session.get(
                    f"https://{api_host}/api/v1/teams", timeout=timeout, verify=True
                )
                logger.info(f"Hostname connection successful: {response.status_code}")
                return response.status_code == 200
            except Exception as e:
                logger.error(f"All connection attempts failed: {str(e)}")
                return False

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
            "penalty_kill_percentage",
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
        output_df["powerplay_percentage"] = output_df["powerplay_percentage"].round(1)
        output_df["penalty_kill_percentage"] = output_df[
            "penalty_kill_percentage"
        ].round(1)
        output_df["points_percentage"] = output_df["points_percentage"].round(3)
        output_df["score"] = output_df["score"].round(2)

        # Ensure all numeric columns are float or int
        numeric_columns = columns[1:]  # All columns except 'team'
        for col in numeric_columns:
            output_df[col] = pd.to_numeric(output_df[col], errors="coerce").fillna(0)

        # Clean string data
        output_df["team"] = output_df["team"].astype(str).str.strip()

        # Save with explicit parameters
        output_df.to_csv(
            filename, index=False, sep=",", encoding="utf-8", quoting=csv.QUOTE_MINIMAL
        )

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
    """Update rankings data"""
    try:
        logging.info("Starting rankings update...")
        stats_fetcher = NHLStatsFetcher()
        calculator = RankingsCalculator()
        processor = GameProcessor()

        # Get current date for rankings
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)

        rankings_data = []

        # Process each team
        for team in TEAM_CODES:
            logging.info(f"Processing team: {team}")
            try:
                # Get team stats and schedule
                team_stats = stats_fetcher.get_team_stats(team, end_date)
                schedule = stats_fetcher.get_schedule(team, start_date, end_date)

                if schedule:
                    # Process games
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
                        total_pk_successes = sum(
                            g["penalty_kill_successes"] for g in game_stats
                        )
                        total_times_shorthanded = sum(
                            g["times_shorthanded"] for g in game_stats
                        )
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
                            "goals_against": sum(
                                g["goals_against"] for g in game_stats
                            ),
                            "shots_on_goal": sum(
                                g["shots_on_goal"] for g in game_stats
                            ),
                            "shots_against": sum(
                                g["shots_against"] for g in game_stats
                            ),
                            "powerplay_goals": total_pp_goals,
                            "powerplay_opportunities": total_pp_opportunities,
                            "penalty_kill_successes": total_pk_successes,
                            "times_shorthanded": total_times_shorthanded,
                            "powerplay_percentage": pp_percentage,
                            "penalty_kill_percentage": pk_percentage,
                            "road_wins": sum(g["road_wins"] for g in game_stats),
                            "scoring_first": sum(
                                g["scoring_first"] for g in game_stats
                            ),
                            "comeback_wins": sum(
                                g["comeback_wins"] for g in game_stats
                            ),
                            "one_goal_games": sum(
                                g["one_goal_games"] for g in game_stats
                            ),
                            "last_10_results": [
                                g.get("last_10", 0) for g in game_stats
                            ][-10:],
                        }

                        team_ranking = calculator.calculate_team_score(
                            aggregated_stats, team_stats, team
                        )
                        if team_ranking:
                            # Ensure special teams percentages are included in team_ranking
                            team_ranking["powerplay_percentage"] = pp_percentage
                            team_ranking["penalty_kill_percentage"] = pk_percentage

                            rankings_data.append(team_ranking)
                            logging.info(f"Successfully processed rankings for {team}")
                else:
                    logging.warning(f"No schedule found for {team}")

            except Exception as e:
                logging.error(f"Error processing {team}: {str(e)}")
                continue

        # Create and save DataFrame
        if rankings_data:
            df = pd.DataFrame(rankings_data)
            now = datetime.now()
            filename = f'nhl_power_rankings_{now.strftime("%Y%m%d")}.csv'

            # Log the data before saving to verify special teams stats
            logging.info(f"Special teams stats for verification:")
            for team_data in rankings_data:
                logging.info(
                    f"{team_data['team']}: PP% = {team_data['powerplay_percentage']:.1f}, PK% = {team_data['penalty_kill_percentage']:.1f}"
                )

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


def update_rankings_parallel():
    """Railway-optimized parallel rankings update with incremental CSV writing"""
    try:
        logger.info("Starting parallel rankings update...")
        stats_fetcher = NHLStatsFetcher()
        calculator = RankingsCalculator()
        processor = GameProcessor()

        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)

        # Initialize CSV file early
        now = datetime.now()
        filename = f'nhl_power_rankings_{now.strftime("%Y%m%d")}.csv'
        temp_filename = f"temp_{filename}"

        # Write headers
        headers = [
            "team",
            "points",
            "games_played",
            "goals_for",
            "goals_against",
            "goal_differential",
            "points_percentage",
            "powerplay_percentage",
            "penalty_kill_percentage",
            "score",
        ]

        with open(temp_filename, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

        # Process teams in very small batches to control memory usage
        BATCH_SIZE = 2  # Reduced batch size for Railway
        processed_count = 0

        for i in range(0, len(TEAM_CODES), BATCH_SIZE):
            batch = TEAM_CODES[i : i + BATCH_SIZE]
            logger.info(f"Processing batch of teams: {batch}")
            batch_rankings = []

            # Process batch with limited threads
            with ThreadPoolExecutor(max_workers=2) as executor:  # Reduced thread count
                process_func = partial(
                    process_team_rankings,
                    start_date=start_date,
                    end_date=end_date,
                    stats_fetcher=stats_fetcher,
                    calculator=calculator,
                    processor=processor,
                )

                future_to_team = {
                    executor.submit(process_func, team): team for team in batch
                }

                for future in as_completed(future_to_team):
                    team = future_to_team[future]
                    try:
                        team_ranking = future.result()
                        if team_ranking:
                            # Round values before writing
                            team_ranking["powerplay_percentage"] = round(
                                team_ranking.get("powerplay_percentage", 0), 1
                            )
                            team_ranking["penalty_kill_percentage"] = round(
                                team_ranking.get("penalty_kill_percentage", 0), 1
                            )
                            team_ranking["points_percentage"] = round(
                                team_ranking.get("points_percentage", 0), 3
                            )
                            team_ranking["score"] = round(
                                team_ranking.get("score", 0), 2
                            )

                            batch_rankings.append(team_ranking)
                            processed_count += 1
                            logger.info(f"Successfully processed rankings for {team}")
                    except Exception as e:
                        logger.error(f"Error processing {team}: {str(e)}")

            # Write batch to CSV
            if batch_rankings:
                with open(temp_filename, "a", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    for ranking in batch_rankings:
                        writer.writerow(ranking)

                logger.info(
                    f"Wrote batch of {len(batch_rankings)} teams to temporary CSV"
                )

            # Clear memory after each batch
            batch_rankings = []
            processor.clear_cache()
            gc.collect()

            # Log memory usage
            process = psutil.Process(os.getpid())
            logger.info(
                f"Memory usage after batch: {process.memory_info().rss / 1024 / 1024:.1f} MB"
            )

        # If we processed any teams, finalize the CSV
        if processed_count > 0:
            try:
                # Read the temp CSV and sort by score
                df = pd.read_csv(temp_filename)
                df = df.sort_values("score", ascending=False)
                df.to_csv(filename, index=False)

                # Clean up temp file
                os.remove(temp_filename)

                logger.info(
                    f"Successfully created final rankings for {processed_count} teams"
                )
                return df
            except Exception as e:
                logger.error(f"Error finalizing CSV: {str(e)}")
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                return None
        else:
            logger.error("No rankings data generated")
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            return None

    except Exception as e:
        logger.error(f"Error in parallel rankings update: {str(e)}")
        logger.error("Exception details:", exc_info=True)
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return None


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

        # Initialize scheduler with parallel update function
        scheduler = BackgroundScheduler(
            executors={"default": {"type": "threadpool", "max_workers": 4}}
        )
        scheduler.add_job(
            func=update_rankings_parallel,
            trigger="interval",
            minutes=Config.UPDATE_INTERVAL_MINUTES,
            max_instances=1,
            id="rankings_update",
        )
        scheduler.start()
        flask_app.config["scheduler_running"] = True
        flask_app.scheduler = scheduler
        logger.info(
            f"Scheduler started - updating every {Config.UPDATE_INTERVAL_MINUTES} minutes"
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
                if not files:
                    logger.warning("No rankings files found - initiating generation")
                    return render_template(
                        "error.html",
                        error="Generating initial rankings... Please refresh in a few moments.",
                    )

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
                            error="Rankings data corrupted. Regenerating...",
                        )

                except Exception as e:
                    logger.error(f"Error reading {latest_file}: {str(e)}")
                    os.remove(latest_file)
                    return render_template(
                        "error.html", error="Rankings data corrupted. Regenerating..."
                    )

                if df.empty:
                    logger.warning("Rankings DataFrame is empty")
                    return render_template(
                        "error.html",
                        error="No rankings data available yet. Please try again later.",
                    )

                # Process the DataFrame
                df.columns = df.columns.str.lower()
                df = df.sort_values("score", ascending=False).reset_index(drop=True)
                df["logo"] = df["team"].map(TEAM_LOGOS)

                # Round values
                df["powerplay_percentage"] = df["powerplay_percentage"].round(1)
                df["penalty_kill_percentage"] = df["penalty_kill_percentage"].round(1)
                df["points_percentage"] = df["points_percentage"].round(3)
                df["score"] = df["score"].round(2)

                last_update = datetime.fromtimestamp(os.path.getmtime(latest_file))
                logger.info(
                    f"Successfully prepared rankings data for display, last updated: {last_update}"
                )

                return render_template(
                    "rankings.html",
                    rankings=df.to_dict("records"),
                    last_update=last_update.strftime("%Y-%m-%d %H:%M:%S"),
                )
            except Exception as e:
                logger.error(f"Error rendering homepage: {str(e)}", exc_info=True)
                return render_template(
                    "error.html", error=f"Error loading rankings: {str(e)}"
                )

        pass

        @flask_app.route("/refresh_rankings", methods=["POST"])
        def refresh_rankings():
            logger.info("Manual rankings refresh requested")
            try:
                df = update_rankings_parallel()

                if df is None:
                    logger.error("Failed to update rankings - no data returned")
                    return {"success": False, "error": "Failed to update rankings"}, 500

                logger.info(f"Successfully updated rankings for {len(df)} teams")

                # Round the values
                df["powerplay_percentage"] = df["powerplay_percentage"].round(1)
                df["penalty_kill_percentage"] = df["penalty_kill_percentage"].round(1)
                df["points_percentage"] = df["points_percentage"].round(3)
                df["score"] = df["score"].round(2)

                df = df.sort_values("score", ascending=False).reset_index(drop=True)
                df["logo"] = df["team"].map(TEAM_LOGOS)

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
            """Simplified health check that won't timeout"""
            try:
                status_checks = {
                    "status": "available",
                    "timestamp": datetime.now().isoformat(),
                    "process_id": os.getpid(),
                    "memory_usage": f"{psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024:.1f}MB",
                }

                # Check if we can write to filesystem
                test_file = "health_check_test.txt"
                with open(test_file, "w") as f:
                    f.write("test")
                    os.remove(test_file)
                    status_checks["filesystem"] = "writable"

                # Check for rankings files
                rankings_files = [
                    f for f in os.listdir(".") if f.startswith("nhl_power_rankings_")
                ]
                status_checks["rankings_files"] = len(rankings_files)

                return jsonify(status_checks), 200
            except Exception as e:
                error_status = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
                return jsonify(error_status), 500
            pass

        # Perform initial rankings update
        logger.info("Performing initial rankings update...")
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

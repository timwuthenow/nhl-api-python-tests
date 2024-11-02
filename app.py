from flask import Flask, render_template, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import pandas as pd
import logging
from datetime import datetime, timedelta
import os
import sys
import csv
import requests
from config import Config

# Import existing modules
from nhl_rankings_calculator import RankingsCalculator
from nhl_game_processor import GameProcessor
from nhl_stats_fetcher import NHLStatsFetcher

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Ensure logs go to stdout for Railway
    ]
)

logger = logging.getLogger(__name__)
logger.info("Starting NHL Rankings application...")

app = Flask(__name__)
app.config.from_object(Config)
logger.info("Flask app created and configured")
# Team Codes
TEAM_CODES = [
    'ANA', 'BOS', 'BUF', 'CAR', 'CBJ', 'CGY', 'CHI', 'COL', 'DAL', 'DET', 
    'EDM', 'FLA', 'LAK', 'MIN', 'MTL', 'NJD', 'NSH', 'NYI', 'NYR', 'OTT', 
    'PHI', 'PIT', 'SEA', 'SJS', 'STL', 'TBL', 'TOR', 'UTA', 'VAN', 'VGK', 
    'WPG', 'WSH'
]

# Team logo mappings
TEAM_LOGOS = {
    'ANA': 'https://assets.nhle.com/logos/nhl/svg/ANA_light.svg',
    'BOS': 'https://assets.nhle.com/logos/nhl/svg/BOS_light.svg',
    'BUF': 'https://assets.nhle.com/logos/nhl/svg/BUF_light.svg',
    'CAR': 'https://assets.nhle.com/logos/nhl/svg/CAR_light.svg',
    'CBJ': 'https://assets.nhle.com/logos/nhl/svg/CBJ_light.svg',
    'CGY': 'https://assets.nhle.com/logos/nhl/svg/CGY_light.svg',
    'CHI': 'https://assets.nhle.com/logos/nhl/svg/CHI_light.svg',
    'COL': 'https://assets.nhle.com/logos/nhl/svg/COL_light.svg',
    'DAL': 'https://assets.nhle.com/logos/nhl/svg/DAL_light.svg',
    'DET': 'https://assets.nhle.com/logos/nhl/svg/DET_light.svg',
    'EDM': 'https://assets.nhle.com/logos/nhl/svg/EDM_light.svg',
    'FLA': 'https://assets.nhle.com/logos/nhl/svg/FLA_light.svg',
    'LAK': 'https://assets.nhle.com/logos/nhl/svg/LAK_light.svg',
    'MIN': 'https://assets.nhle.com/logos/nhl/svg/MIN_light.svg',
    'MTL': 'https://assets.nhle.com/logos/nhl/svg/MTL_light.svg',
    'NJD': 'https://assets.nhle.com/logos/nhl/svg/NJD_light.svg',
    'NSH': 'https://assets.nhle.com/logos/nhl/svg/NSH_light.svg',
    'NYI': 'https://assets.nhle.com/logos/nhl/svg/NYI_light.svg',
    'NYR': 'https://assets.nhle.com/logos/nhl/svg/NYR_light.svg',
    'OTT': 'https://assets.nhle.com/logos/nhl/svg/OTT_light.svg',
    'PHI': 'https://assets.nhle.com/logos/nhl/svg/PHI_light.svg',
    'PIT': 'https://assets.nhle.com/logos/nhl/svg/PIT_light.svg',
    'SEA': 'https://assets.nhle.com/logos/nhl/svg/SEA_light.svg',
    'SJS': 'https://assets.nhle.com/logos/nhl/svg/SJS_light.svg',
    'STL': 'https://assets.nhle.com/logos/nhl/svg/STL_light.svg',
    'TBL': 'https://assets.nhle.com/logos/nhl/svg/TBL_light.svg',
    'TOR': 'https://assets.nhle.com/logos/nhl/svg/TOR_light.svg',
    'UTA': 'https://assets.nhle.com/logos/nhl/svg/UTA_light.svg',  
    'VAN': 'https://assets.nhle.com/logos/nhl/svg/VAN_light.svg',
    'VGK': 'https://assets.nhle.com/logos/nhl/svg/VGK_light.svg',
    'WPG': 'https://assets.nhle.com/logos/nhl/svg/WPG_light.svg',
    'WSH': 'https://assets.nhle.com/logos/nhl/svg/WSH_light.svg'
}

def clean_rankings_files():
    """Clean up any corrupted rankings files"""
    try:
        files = [f for f in os.listdir('.') if f.startswith('nhl_power_rankings_')]
        for file in files:
            try:
                # Try to read the file and verify it has the correct structure
                df = pd.read_csv(file)
                required_columns = ['team', 'points', 'games_played', 'goals_for', 'goals_against']
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
            'team', 'points', 'games_played', 'goals_for', 'goals_against',
            'goal_differential', 'points_percentage', 'powerplay_percentage',
            'penalty_kill_percentage', 'score'
        ]
        
        # Create a new DataFrame with just the columns we need
        output_df = pd.DataFrame()
        for col in columns:
            if col in df.columns:
                output_df[col] = df[col]
            else:
                output_df[col] = 0  # Default value for missing columns
        
        # Round specific columns
        output_df['powerplay_percentage'] = output_df['powerplay_percentage'].round(1)
        output_df['penalty_kill_percentage'] = output_df['penalty_kill_percentage'].round(1)
        output_df['points_percentage'] = output_df['points_percentage'].round(3)
        output_df['score'] = output_df['score'].round(2)
        
        # Ensure all numeric columns are float or int
        numeric_columns = columns[1:]  # All columns except 'team'
        for col in numeric_columns:
            output_df[col] = pd.to_numeric(output_df[col], errors='coerce').fillna(0)
        
        # Clean string data
        output_df['team'] = output_df['team'].astype(str).str.strip()
        
        # Save with explicit parameters
        output_df.to_csv(filename, 
                        index=False, 
                        sep=',', 
                        encoding='utf-8',
                        quoting=csv.QUOTE_MINIMAL)
        
        # Verify the save
        test_df = pd.read_csv(filename)
        if test_df.shape[1] != len(columns):
            raise ValueError(f"Verification failed: Expected {len(columns)} columns, got {test_df.shape[1]}")
        
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
                        details = stats_fetcher.get_game_details(game['id'])
                        if details:
                            stats = processor.process_game(details, team)
                            if stats:
                                game_stats.append(stats)
                    
                    if game_stats:
                        # Calculate power play percentage
                        total_pp_goals = sum(g['powerplay_goals'] for g in game_stats)
                        total_pp_opportunities = sum(g['powerplay_opportunities'] for g in game_stats)
                        pp_percentage = (total_pp_goals / total_pp_opportunities * 100) if total_pp_opportunities > 0 else 0

                        # Calculate penalty kill percentage
                        total_pk_successes = sum(g['penalty_kill_successes'] for g in game_stats)
                        total_times_shorthanded = sum(g['times_shorthanded'] for g in game_stats)
                        pk_percentage = (total_pk_successes / total_times_shorthanded * 100) if total_times_shorthanded > 0 else 0
                        
                        # Aggregate stats
                        aggregated_stats = {
                            'total_points': sum(g['total_points'] for g in game_stats),
                            'games_played': len(game_stats),
                            'wins': sum(g['wins'] for g in game_stats),
                            'losses': sum(g['losses'] for g in game_stats),
                            'otl': sum(g['otl'] for g in game_stats),
                            'goals_for': sum(g['goals_for'] for g in game_stats),
                            'goals_against': sum(g['goals_against'] for g in game_stats),
                            'shots_on_goal': sum(g['shots_on_goal'] for g in game_stats),
                            'shots_against': sum(g['shots_against'] for g in game_stats),
                            'powerplay_goals': total_pp_goals,
                            'powerplay_opportunities': total_pp_opportunities,
                            'penalty_kill_successes': total_pk_successes,
                            'times_shorthanded': total_times_shorthanded,
                            'powerplay_percentage': pp_percentage,
                            'penalty_kill_percentage': pk_percentage,
                            'road_wins': sum(g['road_wins'] for g in game_stats),
                            'scoring_first': sum(g['scoring_first'] for g in game_stats),
                            'comeback_wins': sum(g['comeback_wins'] for g in game_stats),
                            'one_goal_games': sum(g['one_goal_games'] for g in game_stats),
                            'last_10_results': [g.get('last_10', 0) for g in game_stats][-10:]
                        }
                        
                        team_ranking = calculator.calculate_team_score(aggregated_stats, team_stats, team)
                        if team_ranking:
                            # Ensure special teams percentages are included in team_ranking
                            team_ranking['powerplay_percentage'] = pp_percentage
                            team_ranking['penalty_kill_percentage'] = pk_percentage
                            
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
                logging.info(f"{team_data['team']}: PP% = {team_data['powerplay_percentage']:.1f}, PK% = {team_data['penalty_kill_percentage']:.1f}")
            
            if save_rankings(df, filename):
                logging.info(f"Successfully created rankings for {len(rankings_data)} teams")
                return df
        
        logging.error("No rankings data generated")
        return None
        
    except Exception as e:
        logging.error(f"Error updating rankings: {str(e)}")
        logging.error("Exception details:", exc_info=True)
        return None

@app.route('/')
def home():
    logger.info("Processing home page request")
    try:
        # Clean up any corrupted files first
        clean_rankings_files()
        
        # Get latest rankings file
        files = [f for f in os.listdir('.') if f.startswith('nhl_power_rankings_')]
        if not files:
            logger.warning("No rankings files found - initiating generation")
            return render_template('error.html', 
                                error="Generating initial rankings... Please refresh in a few moments.")
            
        latest_file = max(files)
        logger.info(f"Found latest rankings file: {latest_file}")
        
        try:
            df = pd.read_csv(latest_file)
            logger.info(f"Successfully read rankings file with {len(df)} teams")
            
            if 'team' not in df.columns:
                logger.error(f"Invalid file format in {latest_file}")
                os.remove(latest_file)
                return render_template('error.html',
                                    error="Rankings data corrupted. Regenerating...")
                
        except Exception as e:
            logger.error(f"Error reading {latest_file}: {str(e)}")
            os.remove(latest_file)
            return render_template('error.html',
                                error="Rankings data corrupted. Regenerating...")
        
        if df.empty:
            logger.warning("Rankings DataFrame is empty")
            return render_template('error.html', 
                                error="No rankings data available yet. Please try again later.")
        
        # Process the DataFrame
        df.columns = df.columns.str.lower()
        df = df.sort_values('score', ascending=False).reset_index(drop=True)
        df['logo'] = df['team'].map(TEAM_LOGOS)
        
        # Round values
        df['powerplay_percentage'] = df['powerplay_percentage'].round(1)
        df['penalty_kill_percentage'] = df['penalty_kill_percentage'].round(1)
        df['points_percentage'] = df['points_percentage'].round(3)
        df['score'] = df['score'].round(2)
        
        last_update = datetime.fromtimestamp(os.path.getmtime(latest_file))
        logger.info(f"Successfully prepared rankings data for display, last updated: {last_update}")
        
        return render_template(
            'rankings.html',
            rankings=df.to_dict('records'),
            last_update=last_update.strftime("%Y-%m-%d %H:%M:%S")
        )
    except Exception as e:
        logger.error(f"Error rendering homepage: {str(e)}", exc_info=True)
        return render_template('error.html', 
                            error=f"Error loading rankings: {str(e)}")
        
@app.route('/refresh_rankings', methods=['POST'])
def refresh_rankings():
    logger.info("Manual rankings refresh requested")
    try:
        df = update_rankings()
        
        if df is None:
            logger.error("Failed to update rankings - no data returned")
            return {'success': False, 'error': 'Failed to update rankings'}, 500
            
        logger.info(f"Successfully updated rankings for {len(df)} teams")
        
        # Round the values
        df['powerplay_percentage'] = df['powerplay_percentage'].round(1)
        df['penalty_kill_percentage'] = df['penalty_kill_percentage'].round(1)
        df['points_percentage'] = df['points_percentage'].round(3)
        df['score'] = df['score'].round(2)
        
        df = df.sort_values('score', ascending=False).reset_index(drop=True)
        df['logo'] = df['team'].map(TEAM_LOGOS)
        
        rankings_data = df.to_dict('records')
        last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info("Rankings refresh completed successfully")
        return {
            'success': True,
            'rankings': rankings_data,
            'last_update': last_update
        }
        
    except Exception as e:
        logger.error(f"Error refreshing rankings: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}, 500
    
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check if we can make a basic NHL API call
        response = requests.get('https://statsapi.web.nhl.com/api/v1/teams')
        api_status = response.status_code == 200
        
        # Check if we can read rankings file
        rankings_files = [f for f in os.listdir('.') if f.startswith('nhl_power_rankings_')]
        file_status = len(rankings_files) > 0
        
        # Check scheduler
        scheduler_running = app.config.get('scheduler_running', False)
        
        status = {
            'status': 'healthy' if all([api_status, file_status, scheduler_running]) else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'checks': {
                'nhl_api': api_status,
                'rankings_file': file_status,
                'scheduler': scheduler_running
            }
        }
        
        logger.info(f"Health check: {status}")
        return jsonify(status)
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    try:
        logger.info("Starting NHL Power Rankings Service...")
        clean_rankings_files()
        
        # Initial rankings update
        logger.info("Performing initial rankings update...")
        initial_rankings = update_rankings()
        if initial_rankings is not None:
            logger.info("Initial rankings generated successfully")
        else:
            logger.warning("Initial rankings generation failed")
        
        # Set up scheduler
        logger.info("Initializing scheduler...")
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=update_rankings,
            trigger="interval",
            minutes=Config.UPDATE_INTERVAL_MINUTES,
            max_instances=1,
            id='rankings_update'
        )
        scheduler.start()
        app.config['scheduler_running'] = True
        logger.info(f"Scheduler started - updating every {Config.UPDATE_INTERVAL_MINUTES} minutes")
        
        # Run app
        port = int(os.environ.get('PORT', 5002))
        logger.info(f"Starting Flask app on port {port}")
        app.run(host='0.0.0.0', port=port)
        
    except Exception as e:
        logger.error(f"Error starting service: {str(e)}", exc_info=True)
        raise
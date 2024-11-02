import requests
from datetime import datetime, timedelta
import pandas as pd
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ... (keep all other functions the same) ...

def get_team_rankings(end_date):
    team_codes = ['ANA', 'BOS', 'BUF', 'CAR', 'CBJ', 'CGY', 'CHI', 'COL', 'DAL', 'DET', 'EDM', 'FLA', 'LAK', 'MIN', 'MTL', 'NJD', 'NSH', 'NYI', 'NYR', 'OTT', 'PHI', 'PIT', 'SEA', 'SJS', 'STL', 'TBL', 'TOR', 'VAN', 'VGK', 'WPG', 'WSH']
    
    start_date = end_date - timedelta(days=28)  # 4 weeks before the end date
    season = f"{start_date.year}{start_date.year + 1}"
    
    logging.info(f"Calculating rankings for the period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logging.info(f"Using season: {season}")
    
    rankings = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_team = {executor.submit(process_team, team, start_date, end_date, season): team for team in team_codes}
        for future in as_completed(future_to_team):
            team = future_to_team[future]
            try:
                data = future.result()
                rankings.append(data)
            except Exception as exc:
                logging.error(f'{team} generated an exception: {exc}')

    logging.info("Ranking teams...")
    if rankings:
        rankings_df = pd.DataFrame(rankings)
        rankings_df = rankings_df.sort_values('Score', ascending=False).reset_index(drop=True)
        rankings_df.index += 1  # Start ranking from 1 instead of 0
        rankings_df = rankings_df.reset_index()
        rankings_df.columns = ['Rank', 'Team', 'Score', 'Recent PP%', 'Recent PK%', 'Season PP%', 'Season PK%']
        
        logging.info(f"DataFrame columns: {rankings_df.columns}")
        logging.info(f"DataFrame shape: {rankings_df.shape}")
        logging.info(f"First few rows of DataFrame:\n{rankings_df.head()}")
        
        return rankings_df
    else:
        logging.error("No data collected for rankings")
        return pd.DataFrame(columns=['Rank', 'Team', 'Score', 'Recent PP%', 'Recent PK%', 'Season PP%', 'Season PK%'])

def download_team_logos(team_codes):
    logo_dir = os.path.join('static', 'logos')
    os.makedirs(logo_dir, exist_ok=True)
    
    for team in team_codes:
        url = f"https://assets.nhle.com/logos/nhl/svg/{team}_light.svg"
        file_path = os.path.join(logo_dir, f"{team}.svg")
        
        if not os.path.exists(file_path):
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                logging.info(f"Downloaded logo for {team}")
            except requests.RequestException as e:
                logging.error(f"Failed to download logo for {team}: {e}")
        else:
            logging.info(f"Logo for {team} already exists")

# ... (keep the rest of the file the same) ...

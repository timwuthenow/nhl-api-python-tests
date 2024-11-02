import requests
from datetime import datetime, timedelta
import pandas as pd
import logging
import time
import sqlite3
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Database setup
def init_db():
    conn = sqlite3.connect('nhl_rankings.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rankings
                 (date TEXT, team TEXT, score REAL, recent_pp REAL, recent_pk REAL, season_pp REAL, season_pk REAL)''')
    conn.commit()
    conn.close()

def save_rankings(rankings_df, date):
    conn = sqlite3.connect('nhl_rankings.db')
    for _, row in rankings_df.iterrows():
        conn.execute('''INSERT INTO rankings (date, team, score, recent_pp, recent_pk, season_pp, season_pk)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (date, row['Team'], row['Score'], row['Recent PP%'], row['Recent PK%'], row['Season PP%'], row['Season PK%']))
    conn.commit()
    conn.close()

def get_saved_rankings(date):
    conn = sqlite3.connect('nhl_rankings.db')
    df = pd.read_sql_query(f"SELECT * FROM rankings WHERE date = '{date}'", conn)
    conn.close()
    return df

# Logo download function
def download_team_logos(team_codes):
    logo_dir = 'static/logos'
    os.makedirs(logo_dir, exist_ok=True)
    for team in team_codes:
        url = f"https://www-league.nhlstatic.com/images/logos/teams-current-primary-light/{team}.svg"
        response = requests.get(url)
        if response.status_code == 200:
            with open(f"{logo_dir}/{team}.svg", 'wb') as f:
                f.write(response.content)
            logging.info(f"Downloaded logo for {team}")
        else:
            logging.error(f"Failed to download logo for {team}")

# Existing functions (get_team_schedule, get_team_stats, calculate_team_score) remain the same

def get_team_rankings(end_date):
    team_codes = ['ANA', 'ARI', 'BOS', 'BUF', 'CAR', 'CBJ', 'CGY', 'CHI', 'COL', 'DAL', 'DET', 'EDM', 'FLA', 'LAK', 'MIN', 'MTL', 'NJD', 'NSH', 'NYI', 'NYR', 'OTT', 'PHI', 'PIT', 'SEA', 'SJS', 'STL', 'TBL', 'TOR', 'VAN', 'VGK', 'WPG', 'WSH']
    
    # Check if we have saved rankings for this date
    saved_rankings = get_saved_rankings(end_date.strftime('%Y-%m-%d'))
    if not saved_rankings.empty:
        logging.info(f"Using saved rankings for {end_date.strftime('%Y-%m-%d')}")
        return saved_rankings

    start_date = end_date - timedelta(days=28)  # 4 weeks before the end date
    season = f"{start_date.year}{start_date.year + 1}"
    
    rankings = []
    
    logging.info(f"Calculating rankings for the period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logging.info(f"Using season: {season}")
    
    for i, team_code in enumerate(team_codes, 1):
        logging.info(f"Processing team {i} of {len(team_codes)}: {team_code}")
        
        try:
            # ... (rest of the team processing code remains the same)
            
        except Exception as e:
            logging.error(f"Error processing team {team_code}: {str(e)}")
        
        time.sleep(1)  # Add a 1-second delay between team processing to avoid rate limiting

    logging.info("Ranking teams...")
    logging.info(f"Rankings data: {rankings}")
    
    if rankings:
        rankings_df = pd.DataFrame(rankings)
        logging.info(f"DataFrame columns: {rankings_df.columns}")
        logging.info(f"DataFrame shape: {rankings_df.shape}")
        logging.info(f"First few rows of DataFrame:\n{rankings_df.head()}")
        
        if 'score' in rankings_df.columns:
            rankings_df = rankings_df.sort_values('score', ascending=False).reset_index(drop=True)
            rankings_df.index += 1  # Start ranking from 1 instead of 0
            rankings_df.columns = ['Rank', 'Team', 'Score', 'Recent PP%', 'Recent PK%', 'Season PP%', 'Season PK%']
            
            # Save the rankings to the database
            save_rankings(rankings_df, end_date.strftime('%Y-%m-%d'))
            
            return rankings_df
        else:
            logging.error("'score' column not found in DataFrame")
    else:
        logging.error("No data collected for rankings")
    
    return pd.DataFrame()  # Return an empty DataFrame if we couldn't create rankings

# Example usage
if __name__ == "__main__":
    # Initialize the database
    init_db()
    
    # Download team logos
    team_codes = ['ANA', 'ARI', 'BOS', 'BUF', 'CAR', 'CBJ', 'CGY', 'CHI', 'COL', 'DAL', 'DET', 'EDM', 'FLA', 'LAK', 'MIN', 'MTL', 'NJD', 'NSH', 'NYI', 'NYR', 'OTT', 'PHI', 'PIT', 'SEA', 'SJS', 'STL', 'TBL', 'TOR', 'VAN', 'VGK', 'WPG', 'WSH']
    download_team_logos(team_codes)
    
    # Set the date for which you want to calculate rankings
    target_date = datetime(2023, 12, 31)  # Example: December 31, 2023
    
    logging.info(f"Starting NHL Power Rankings calculation for {target_date.strftime('%Y-%m-%d')}")
    rankings = get_team_rankings(target_date)
    logging.info(f"\nNHL Power Rankings as of {target_date.strftime('%Y-%m-%d')}:")
    if not rankings.empty:
        print(rankings)
    else:
        print("Failed to generate rankings.")
    logging.info("Rankings calculation complete.")

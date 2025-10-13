#!/usr/bin/env python3
"""
Fetcher to get each team's actual last 10 regular season games
"""
import requests
import logging
from datetime import datetime
from season_config import GAME_TYPE_REGULAR, SEASON_START_DATE

class Last10Fetcher:
    def __init__(self):
        self.base_url = "https://api-web.nhle.com/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def get_team_last_10_games(self, team_code):
        """
        Get a team's actual last 10 completed regular season games.
        This will span different dates for different teams.
        """
        try:
            logging.info(f"Fetching last 10 regular season games for {team_code}")
            
            # Get team's full season schedule
            url = f"{self.base_url}/club-schedule-season/{team_code}/20252026"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logging.error(f"Failed to get season schedule for {team_code}: {response.status_code}")
                return []
            
            data = response.json()
            all_games = data.get('games', [])
            
            # Filter for completed regular season games only
            completed_regular_games = []
            for game in all_games:
                # Only regular season games
                if game.get('gameType', 0) != GAME_TYPE_REGULAR:
                    continue
                
                # Only completed games
                game_state = game.get('gameState', '')
                if game_state not in ['OFF', 'FINAL', 'FINAL/OT', 'FINAL/SO']:
                    continue
                
                # Only games from current season (no preseason dates)
                game_date = datetime.strptime(game.get('gameDate', '2000-01-01'), '%Y-%m-%d')
                if game_date < SEASON_START_DATE:
                    continue
                
                # Must have actual scores
                home_score = game.get('homeTeam', {}).get('score', 0)
                away_score = game.get('awayTeam', {}).get('score', 0)
                if home_score == 0 and away_score == 0:
                    continue
                
                completed_regular_games.append(game)
            
            # Sort by date descending (most recent first)
            completed_regular_games.sort(
                key=lambda x: datetime.strptime(x['gameDate'], '%Y-%m-%d'), 
                reverse=True
            )
            
            # Take the last 10 games
            last_10 = completed_regular_games[:10]
            
            logging.info(f"Found {len(completed_regular_games)} total completed regular season games for {team_code}")
            logging.info(f"Using last {len(last_10)} games for analysis")
            
            if last_10:
                first_game_date = last_10[0]['gameDate']
                last_game_date = last_10[-1]['gameDate']
                logging.info(f"{team_code} last 10 span: {last_game_date} to {first_game_date}")
            
            return last_10
            
        except Exception as e:
            logging.error(f"Error getting last 10 games for {team_code}: {str(e)}")
            return []

    def analyze_last_10_record(self, team_code, games):
        """
        Analyze the last 10 games to get wins/losses/OTL record
        """
        if not games:
            return "0-0-0"
        
        wins = 0
        losses = 0
        otl = 0
        
        for game in games:
            home_team = game.get('homeTeam', {}).get('abbrev', '')
            away_team = game.get('awayTeam', {}).get('abbrev', '')
            home_score = game.get('homeTeam', {}).get('score', 0)
            away_score = game.get('awayTeam', {}).get('score', 0)
            game_state = game.get('gameState', '')
            
            # Determine if team won or lost
            if home_team == team_code:
                team_score = home_score
                opponent_score = away_score
            else:
                team_score = away_score
                opponent_score = home_score
            
            if team_score > opponent_score:
                wins += 1
            elif team_score < opponent_score:
                # Check if it was overtime/shootout loss
                if game_state in ['FINAL/OT', 'FINAL/SO']:
                    otl += 1
                else:
                    losses += 1
        
        return f"{wins}-{losses}-{otl}"

# Test function
def test_last_10():
    """Test the last 10 fetcher with Rangers"""
    fetcher = Last10Fetcher()
    
    # Test with Rangers
    games = fetcher.get_team_last_10_games('NYR')
    record = fetcher.analyze_last_10_record('NYR', games)
    
    print(f"\nRANGERS LAST 10 REGULAR SEASON GAMES:")
    print(f"Record: {record}")
    print(f"Games analyzed: {len(games)}")
    
    if games:
        print("\nGame details:")
        for i, game in enumerate(games, 1):
            date = game.get('gameDate', 'Unknown')
            home = game.get('homeTeam', {}).get('abbrev', 'Unknown')
            away = game.get('awayTeam', {}).get('abbrev', 'Unknown')
            home_score = game.get('homeTeam', {}).get('score', 0)
            away_score = game.get('awayTeam', {}).get('score', 0)
            state = game.get('gameState', 'Unknown')
            
            print(f"  {i}. {date}: {away} {away_score} @ {home} {home_score} ({state})")
    
    print(f"\nThis should be much more accurate than just weekly games!")

if __name__ == "__main__":
    test_last_10()
# nhl_stats_fetcher.py
import requests
import logging
from datetime import datetime, timedelta
import time

class NHLStatsFetcher:
    def __init__(self):
        """Initialize the NHL Stats Fetcher."""
        self.base_url = "https://api-web.nhle.com/v1"
        
    def get_standings(self, date):
        """
        Fetch standings data for a specific date.
        
        Args:
            date (datetime): The date to fetch standings for
            
        Returns:
            dict: The standings data or None if request fails
        """
        url = f"{self.base_url}/standings/{date.strftime('%Y-%m-%d')}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if 'standings' not in data:
                logging.error("Invalid standings data format received")
                return None
                
            logging.debug(f"Successfully fetched standings for {len(data.get('standings', []))} teams")
            return data
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch standings: {str(e)}")
            return None
        except ValueError as e:
            logging.error(f"Failed to parse standings JSON: {str(e)}")
            return None

    def get_team_stats(self, team_code, date):
        """
        Get team stats from standings.
        
        Args:
            team_code (str): The team's code (e.g., 'TOR', 'NYR')
            date (datetime): The date to fetch stats for
            
        Returns:
            dict: Team statistics
        """
        logging.info(f"Fetching stats for {team_code} on {date.strftime('%Y-%m-%d')}")
        standings = self.get_standings(date)
        
        if not standings:
            logging.error(f"No standings data available for {date.strftime('%Y-%m-%d')}")
            return self._default_stats()
            
        try:
            for team in standings.get('standings', []):
                team_abbrev = team.get('teamAbbrev', {}).get('default')
                if team_abbrev == team_code:
                    stats = {
                        'powerPlayPct': self._safe_float(team.get('powerPlayPct')),
                        'penaltyKillPct': self._safe_float(team.get('penaltyKillPct')),
                        'faceoffWinPct': self._safe_float(team.get('faceoffWinPct', 50.0)),
                        'goalsPerGame': self._safe_float(team.get('goalsForPerGame')),
                        'goalsAgainstPerGame': self._safe_float(team.get('goalsAgainstPerGame')),
                        'shotsPerGame': self._safe_float(team.get('shotsForPerGame')),
                        'shotsAgainstPerGame': self._safe_float(team.get('shotsAgainstPerGame')),
                        'winPct': self._safe_float(team.get('winPct', 0.0))
                    }
                    
                    logging.info(f"Team stats for {team_code}:")
                    logging.info(f"Power Play %: {stats['powerPlayPct']}")
                    logging.info(f"Penalty Kill %: {stats['penaltyKillPct']}")
                    logging.info(f"Goals/Game: {stats['goalsPerGame']}")
                    return stats
            
            logging.warning(f"Team {team_code} not found in standings")
            return self._default_stats()
            
        except Exception as e:
            logging.error(f"Error processing stats for {team_code}: {str(e)}", exc_info=True)
            return self._default_stats()

    def get_schedule(self, team_code, start_date, end_date):
        """
        Fetch team schedule between dates.
        
        Args:
            team_code (str): The team's code
            start_date (datetime): Start date for schedule
            end_date (datetime): End date for schedule
            
        Returns:
            list: List of games in the date range
        """
        url = f"{self.base_url}/club-schedule/{team_code}/week/{start_date.strftime('%Y-%m-%d')}"
        all_games = []
        current_date = start_date
        
        while current_date <= end_date:
            try:
                logging.debug(f"Fetching schedule from: {url}")
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                
                games = data.get('games', [])
                filtered_games = [
                    game for game in games 
                    if (start_date <= datetime.strptime(game['gameDate'], '%Y-%m-%d') <= end_date and
                        game.get('gameType') == 2)  # Regular season games only
                ]
                
                logging.debug(f"Found {len(filtered_games)} games in current week")
                all_games.extend(filtered_games)
                
                next_date = data.get('nextStartDate')
                if not next_date or datetime.strptime(next_date, '%Y-%m-%d') > end_date:
                    break
                    
                current_date = datetime.strptime(next_date, '%Y-%m-%d')
                url = f"{self.base_url}/club-schedule/{team_code}/week/{current_date.strftime('%Y-%m-%d')}"
                time.sleep(0.1)  # Small delay to avoid rate limiting
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to fetch schedule for {team_code}: {str(e)}")
                break
            except ValueError as e:
                logging.error(f"Failed to parse schedule data: {str(e)}")
                break
                
        logging.info(f"Total games found for {team_code}: {len(all_games)}")
        return all_games

    def get_game_details(self, game_id):
        """
        Fetch details for a specific game.
        
        Args:
            game_id (str): The game ID to fetch details for
            
        Returns:
            dict: Game details or None if request fails
        """
        url = f"{self.base_url}/gamecenter/{game_id}/boxscore"
        logging.info(f"Fetching game details for game {game_id}")
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Log key game information
            home_team = data.get('homeTeam', {}).get('abbrev', 'Unknown')
            away_team = data.get('awayTeam', {}).get('abbrev', 'Unknown')
            home_score = data.get('homeTeam', {}).get('score', 0)
            away_score = data.get('awayTeam', {}).get('score', 0)
            
            logging.info(f"Game {game_id}: {away_team} ({away_score}) @ {home_team} ({home_score})")
            
            # Extract and validate shot data
            if 'boxscore' in data:
                home_shots = data['boxscore']['homeTeam'].get('totalShots', 0)
                away_shots = data['boxscore']['awayTeam'].get('totalShots', 0)
                logging.debug(f"Shot totals - Home: {home_shots}, Away: {away_shots}")
            
            # Get scoring summary
            if 'summary' in data and 'scoring' in data['summary']:
                first_goal = data['summary']['scoring'][0]
                logging.debug(f"First goal: {first_goal.get('teamAbbrev')} - {first_goal.get('period')} period")
            
            return data
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch game {game_id}: {str(e)}")
            return None
        except ValueError as e:
            logging.error(f"Failed to parse game data for {game_id}: {str(e)}")
            return None

    def _safe_float(self, value, default=0.0):
        """
        Safely convert value to float.
        
        Args:
            value: Value to convert
            default (float): Default value if conversion fails
            
        Returns:
            float: Converted value or default
        """
        try:
            if value is None or value == '':
                return default
            return float(value)
        except (ValueError, TypeError):
            return default

    def _default_stats(self):
        """
        Return default stats when actual stats can't be retrieved.
        
        Returns:
            dict: Default statistics
        """
        return {
            'powerPlayPct': 0.0,
            'penaltyKillPct': 0.0,
            'faceoffWinPct': 50.0,
            'goalsPerGame': 0.0,
            'goalsAgainstPerGame': 0.0,
            'shotsPerGame': 0.0,
            'shotsAgainstPerGame': 0.0,
            'winPct': 0.0
        }
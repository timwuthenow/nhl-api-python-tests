# nhl_stats_fetcher.py
import requests
import logging
from datetime import datetime, timedelta
import time


class NHLStatsFetcher:
    def __init__(self):
        """Initialize the NHL Stats Fetcher."""
        self.base_url = "https://api-web.nhle.com/v1"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def get_standings(self, date):
        """
        Fetch standings data for a specific date.
        """
        # Use the new NHL API endpoint
        url = f"{self.base_url}/standings/now"
        retries = 3

        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()

                if "standings" not in data:
                    logging.error("Invalid standings data format received")
                    return None

                logging.debug(
                    f"Successfully fetched standings for {len(data.get('standings', []))} teams"
                )
                return data

            except requests.exceptions.RequestException as e:
                logging.error(
                    f"Attempt {attempt + 1}/{retries} failed to fetch standings: {str(e)}"
                )
                if attempt < retries - 1:
                    time.sleep(1)  # Wait before retry
                continue

        return None

    def get_team_stats(self, team_code, date):
        """
        Get team stats from standings with retries and better error handling.
        """
        logging.info(f"Fetching stats for {team_code} on {date.strftime('%Y-%m-%d')}")

        # Try multiple times to get standings
        for attempt in range(3):
            standings = self.get_standings(date)
            if standings:
                break
            time.sleep(1)

        if not standings:
            logging.error(
                f"No standings data available for {date.strftime('%Y-%m-%d')}"
            )
            return self._default_stats()

        try:
            # Find team in standings
            team_data = None
            for team in standings.get("standings", []):
                if team.get("teamAbbrev", {}).get("default") == team_code:
                    team_data = team
                    break

            if team_data:
                # Extract stats with proper validation
                pp_goals = self._safe_float(team_data.get("ppGoals", 0))
                pp_opportunities = self._safe_float(team_data.get("ppOpportunities", 0))
                pk_goals_against = self._safe_float(team_data.get("pkGoalsAgainst", 0))
                times_shorthanded = self._safe_float(
                    team_data.get("timesShorthanded", 0)
                )

                # Calculate percentages properly
                pp_pct = (
                    (pp_goals / pp_opportunities * 100) if pp_opportunities > 0 else 0.0
                )
                pk_pct = (
                    ((times_shorthanded - pk_goals_against) / times_shorthanded * 100)
                    if times_shorthanded > 0
                    else 0.0
                )

                stats = {
                    "powerPlayPct": pp_pct,
                    "penaltyKillPct": pk_pct,
                    "faceoffWinPct": self._safe_float(
                        team_data.get("faceoffWinPct", 50.0)
                    ),
                    "goalsPerGame": self._safe_float(team_data.get("goalsForPerGame")),
                    "goalsAgainstPerGame": self._safe_float(
                        team_data.get("goalsAgainstPerGame")
                    ),
                    "shotsPerGame": self._safe_float(team_data.get("shotsForPerGame")),
                    "shotsAgainstPerGame": self._safe_float(
                        team_data.get("shotsAgainstPerGame")
                    ),
                    "winPct": self._safe_float(team_data.get("pointPct", 0.0)),
                }

                # Log actual values for debugging
                logging.info(f"Raw stats for {team_code}:")
                logging.info(
                    f"PP Goals: {pp_goals}, PP Opportunities: {pp_opportunities}"
                )
                logging.info(
                    f"PK Goals Against: {pk_goals_against}, Times Shorthanded: {times_shorthanded}"
                )
                logging.info(f"Calculated PP%: {pp_pct:.1f}, PK%: {pk_pct:.1f}")

                return stats

            logging.warning(f"Team {team_code} not found in standings")
            return self._default_stats()

        except Exception as e:
            logging.error(
                f"Error processing stats for {team_code}: {str(e)}", exc_info=True
            )
            return self._default_stats()

    def get_schedule(self, team_code, start_date, end_date):
        """
        Fetch team schedule between dates using new NHL API format.

        Args:
            team_code (str): The team's code
            start_date (datetime): Start date for schedule
            end_date (datetime): End date for schedule

        Returns:
            list: List of games in the date range
        """
        try:
            # Format dates for API
            start_str = start_date.strftime("%Y-%m-%d")

            # Use new NHL API endpoint for team schedule
            url = f"{self.base_url}/club-schedule/{team_code}/week/{start_str}"
            logging.debug(f"Fetching schedule from: {url}")

            all_games = []
            current_date = start_date

            while current_date <= end_date:
                try:
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                    data = response.json()

                    # Filter games within date range and regular season only
                    games = [
                        game
                        for game in data.get("games", [])
                        if (
                            datetime.strptime(game["gameDate"], "%Y-%m-%d") <= end_date
                            and game.get("gameType", 0) == 2
                        )  # 2 = Regular Season
                    ]

                    all_games.extend(games)

                    # Get next week's date from response
                    next_date = data.get("nextStartDate")
                    if (
                        not next_date
                        or datetime.strptime(next_date, "%Y-%m-%d") > end_date
                    ):
                        break

                    current_date = datetime.strptime(next_date, "%Y-%m-%d")
                    url = f"{self.base_url}/club-schedule/{team_code}/week/{next_date}"
                    time.sleep(0.1)  # Small delay to avoid rate limiting

                except requests.exceptions.RequestException as e:
                    logging.error(f"Failed to fetch schedule for {team_code}: {str(e)}")
                    break

            logging.info(f"Found {len(all_games)} games for {team_code}")
            return all_games

        except Exception as e:
            logging.error(f"Error getting schedule for {team_code}: {str(e)}")
            return []

    def get_game_details(self, game_id):
        """
        Fetch details for a specific game using new NHL API format.

        Args:
            game_id (str): The game ID to fetch details for

        Returns:
            dict: Game details or None if request fails
        """
        url = f"{self.base_url}/gamecenter/{game_id}/boxscore"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data:
                logging.error(f"No data returned for game {game_id}")
                return None

            # Extract basic game info for logging
            home_team = data.get("homeTeam", {}).get("abbrev", "Unknown")
            away_team = data.get("awayTeam", {}).get("abbrev", "Unknown")
            home_score = data.get("homeTeam", {}).get("score", 0)
            away_score = data.get("awayTeam", {}).get("score", 0)

            logging.info(
                f"Game {game_id}: {away_team} ({away_score}) @ {home_team} ({home_score})"
            )
            return data

        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch game {game_id}: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Error processing game {game_id}: {str(e)}")
            return None

    def _safe_float(self, value, default=0.0):
        """
        Safely convert value to float with better type checking.
        """
        if value is None:
            return default

        try:
            float_val = float(value)
            return float_val if float_val >= 0 else default
        except (ValueError, TypeError):
            return default

    def _default_stats(self):
        """Return default stats dictionary when actual stats can't be retrieved."""
        return {
            "powerPlayPct": 0.0,
            "penaltyKillPct": 0.0,
            "faceoffWinPct": 50.0,
            "goalsPerGame": 0.0,
            "goalsAgainstPerGame": 0.0,
            "shotsPerGame": 0.0,
            "shotsAgainstPerGame": 0.0,
            "winPct": 0.0,
        }

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

        # Get team season stats
        url = f"{self.base_url}/club-stats/{team_code}/now"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            team_stats = response.json()

            if not team_stats:
                return self._default_stats()

            stats = (
                team_stats.get("teamStats", {})
                .get("regularSeason", {})
                .get("statistics", {})
            )

            # Handle various possible paths for PP% and PK%
            pp_pct = 0.0
            pk_pct = 0.0

            # Try different paths for power play percentage
            if "powerPlayPct" in stats:
                pp_pct = float(stats["powerPlayPct"].replace("%", ""))
            elif "powerPlayPercentage" in stats:
                pp_pct = float(stats["powerPlayPercentage"].replace("%", ""))
            elif "ppPctg" in stats:
                pp_pct = float(stats["ppPctg"].replace("%", ""))

            # Try different paths for penalty kill percentage
            if "penaltyKillPct" in stats:
                pk_pct = float(stats["penaltyKillPct"].replace("%", ""))
            elif "penaltyKillPercentage" in stats:
                pk_pct = float(stats["penaltyKillPercentage"].replace("%", ""))
            elif "pkPctg" in stats:
                pk_pct = float(stats["pkPctg"].replace("%", ""))

            # If still no PK%, try calculating from scratch using timesShortHanded and powerPlayGoalsAgainst
            if pk_pct == 0.0:
                times_shorthanded = float(stats.get("timesShortHanded", 0))
                pp_goals_against = float(stats.get("powerPlayGoalsAgainst", 0))
                if times_shorthanded > 0:
                    pk_pct = (
                        (times_shorthanded - pp_goals_against) / times_shorthanded
                    ) * 100

            # Log actual values for debugging
            logging.info(f"Raw stats for {team_code}:")
            logging.info(
                f"PP%: {pp_pct:.1f}, PK%: {pk_pct:.1f}, TSH: {stats.get('timesShortHanded', 0)}, PPGA: {stats.get('powerPlayGoalsAgainst', 0)}"
            )

            return {
                "powerPlayPct": pp_pct,
                "penaltyKillPct": pk_pct,  # Make sure PK% is included in return
                "faceoffWinPct": float(
                    stats.get("faceoffWinPct", "0").replace("%", "")
                ),
                "goalsPerGame": float(stats.get("goalsPerGame", 0)),
                "goalsAgainstPerGame": float(stats.get("goalsAgainstPerGame", 0)),
                "shotsPerGame": float(stats.get("shotsPerGame", 0)),
                "shotsAgainstPerGame": float(stats.get("shotsAgainstPerGame", 0)),
                "winPct": float(stats.get("pointPct", "0").replace("%", "")),
            }

        except Exception as e:
            logging.error(f"Error getting team stats for {team_code}: {str(e)}")
            return self._default_stats()

    def get_schedule_by_games(self, team_code, num_games):
        """
        Fetch the last N games for a team using weekly schedule endpoints
        """
        try:
            all_games = []
            current_date = datetime.now()
            weeks_to_try = 4  # Try up to 4 weeks back

            # Start with current week
            url = f"{self.base_url}/club-schedule/{team_code}/week/now"
            logging.info(f"Fetching current week schedule from {url}")

            # Get games week by week
            for week in range(weeks_to_try):
                if week > 0:
                    # Format date for previous weeks
                    url = f"{self.base_url}/club-schedule/{team_code}/week/{current_date.strftime('%Y-%m-%d')}"
                    logging.info(f"Fetching schedule for week {week} from {url}")

                try:
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                    week_data = response.json()

                    if week_data and "games" in week_data:
                        # Add games from this week
                        all_games.extend(week_data["games"])
                        logging.info(
                            f"Found {len(week_data['games'])} games for week {week}"
                        )

                        # Debug log game states
                        for game in week_data["games"]:
                            logging.info(
                                f"Game date: {game.get('gameDate', 'Unknown')}, State: {game.get('gameState', 'Unknown')}"
                            )

                        # Get the previous week's start date
                        if "previousStartDate" in week_data:
                            current_date = datetime.strptime(
                                week_data["previousStartDate"], "%Y-%m-%d"
                            )
                        else:
                            current_date -= timedelta(days=7)

                except requests.exceptions.RequestException as e:
                    logging.error(f"Error fetching week {week} schedule: {str(e)}")
                    continue

                time.sleep(0.1)  # Small delay between requests

            # Filter for completed regular season games - any game with a final score
            completed_games = [
                game
                for game in all_games
                if (
                    game.get("gameType", 0) == 2  # Regular season games
                    and game.get("gameState", "")
                    in ["OFF", "FINAL", "FINAL/OT", "FINAL/SO"]
                    and (
                        game.get("homeTeam", {}).get("score", 0) > 0
                        or game.get("awayTeam", {}).get("score", 0) > 0
                    )
                )
            ]

            # Sort by date descending
            completed_games.sort(
                key=lambda x: datetime.strptime(x["gameDate"], "%Y-%m-%d"), reverse=True
            )

            # Take the most recent N games
            recent_games = completed_games[:num_games]

            # Log more details about filtered games
            logging.info(
                f"Found {len(completed_games)} completed games out of {len(all_games)} total games for {team_code}"
            )
            if recent_games:
                logging.info(
                    f"First game date: {recent_games[0].get('gameDate')}, Last game date: {recent_games[-1].get('gameDate')}"
                )
                logging.info(
                    f"Game states: {[game.get('gameState', '') for game in recent_games]}"
                )
                logging.info(
                    f"Sample scores: {[(game.get('homeTeam', {}).get('score', 0), game.get('awayTeam', {}).get('score', 0)) for game in recent_games[:3]]}"
                )

            return recent_games

        except Exception as e:
            logging.error(f"Error in get_schedule_by_games for {team_code}: {str(e)}")
            return []

    def get_game_details(self, game_id):
        """
        Fetch details for a specific game using updated NHL API format.
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

    def get_game_stats_detailed(self, game_id):
        """Fetch detailed game stats including shot locations and types."""
        try:
            # Get boxscore data
            boxscore_url = f"{self.base_url}/gamecenter/{game_id}/boxscore"
            boxscore = self._make_request(boxscore_url)

            # Get play-by-play data for shot details
            pbp_url = f"{self.base_url}/gamecenter/{game_id}/play-by-play"
            pbp = self._make_request(pbp_url)

            if not boxscore or not pbp:
                return None

            game_data = {
                "boxscore": boxscore,
                "plays": pbp.get("plays", []),
                "high_danger_chances": self._process_high_danger_chances(
                    pbp.get("plays", [])
                ),
            }

            return game_data
        except Exception as e:
            logging.error(f"Error fetching detailed game stats for {game_id}: {str(e)}")
            return None

    def _process_high_danger_chances(self, plays):
        """Process plays to identify high danger chances."""
        high_danger = {
            "home": {"chances": 0, "goals": 0},
            "away": {"chances": 0, "goals": 0},
        }

        for play in plays:
            if play.get("typeDescKey") in ["shot", "goal"]:
                details = play.get("details", {})
                shot_type = details.get("shotType", "")
                distance = details.get("shotDistance", 999)
                is_home = details.get("eventOwnerTeamType") == "home"

                # Classify as high danger if:
                # 1. Shot type is high danger
                # 2. Shot is from close range
                # 3. Shot is from the slot area
                is_high_danger = (
                    shot_type in ["Deflected", "Tip-In", "Wrap-around"]
                    or distance <= 15
                    or self._is_slot_shot(details.get("xCoord"), details.get("yCoord"))
                )

                if is_high_danger:
                    team_key = "home" if is_home else "away"
                    high_danger[team_key]["chances"] += 1
                    if play.get("typeDescKey") == "goal":
                        high_danger[team_key]["goals"] += 1

        return high_danger

    def _is_slot_shot(self, x, y):
        """Determine if shot is from the slot area."""
        if x is None or y is None:
            return False

        # Define slot area (approximate coordinates)
        slot_x_range = (-25, 25)  # feet from net
        slot_y_range = (0, 30)  # feet from goal line

        return (
            slot_x_range[0] <= x <= slot_x_range[1]
            and slot_y_range[0] <= y <= slot_y_range[1]
        )

    def _make_request(self, url):
        """Make API request with retries."""
        retries = 3
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if attempt == retries - 1:
                    logging.error(
                        f"Failed to fetch {url} after {retries} attempts: {str(e)}"
                    )
                    return None
                time.sleep(1)

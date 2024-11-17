# nhl_game_processor.py
import logging
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)  # Add this line at the top


class GameProcessor:
    def __init__(self):
        self._game_cache = {}

    @lru_cache(maxsize=128)
    def get_game_cache_key(self, game_id, team):
        """Create a unique cache key for game results"""
        return f"{game_id}_{team}"

    def process_game(self, game_details, team):
        """Process game with caching"""
        try:
            if not game_details.get("gamePk"):
                return self.process_game_static(game_details, team)

            cache_key = self.get_game_cache_key(game_details["gamePk"], team)

            # Check if we already processed this game
            if cache_key in self._game_cache:
                logger.debug(
                    f"Using cached results for game {game_details['gamePk']} and team {team}"
                )
                return self._game_cache[cache_key]

            # Process game normally
            stats = self.process_game_static(game_details, team)

            # Cache the results
            if stats:
                self._game_cache[cache_key] = stats

            return stats

        except Exception as e:
            logger.error(
                f"Error processing game {game_details.get('gamePk', 'unknown')}: {str(e)}"
            )
            return None

    def clear_cache(self):
        """Clear the game cache"""
        self._game_cache.clear()
        self.get_game_cache_key.cache_clear()  # Clear the lru_cache as well

    @staticmethod
    def _get_first_goal_team(game_id):
        """Get the team that scored first from play-by-play data."""
        try:
            url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
            response = requests.get(url)
            if response.ok:
                plays = response.json().get("plays", [])
                # Find first goal event
                first_goal = next(
                    (play for play in plays if play.get("typeDescKey") == "goal"), None
                )
                if first_goal:
                    return first_goal.get("details", {}).get("eventOwnerTeamId")
            return None
        except Exception as e:
            logger.error(f"Error getting first goal team: {str(e)}")
            return None

    @staticmethod
    def process_game_static(game_details, team_code):
        """Process individual game data and return statistics."""
        game_stats = {
            "total_points": 0,
            "games_played": 1,
            "wins": 0,
            "losses": 0,
            "otl": 0,
            "goals_for": 0,
            "goals_against": 0,
            "shots_on_goal": 0,
            "shots_against": 0,
            "even_strength_shots_for": 0,
            "even_strength_shots_against": 0,
            "powerplay_shots_for": 0,
            "powerplay_shots_against": 0,
            "shorthanded_shots_for": 0,
            "shorthanded_shots_against": 0,
            "high_danger_chances_for": 0,
            "high_danger_chances_against": 0,
            "last_10": 0,
            "road_wins": 0,
            "scoring_first": 0,
            "comeback_wins": 0,
            "one_goal_games": 0,
            "powerplay_goals": 0,
            "powerplay_opportunities": 0,
            "penalty_kill_successes": 0,
            "times_shorthanded": 0,
            "empty_net_goals": 0,
        }

        if not game_details:
            logger.warning(f"No game details available for team {team_code}")
            return game_stats

        try:
            logger.debug(f"Processing game details for {team_code}")

            # Determine home/away and get team data
            is_home = game_details.get("homeTeam", {}).get("abbrev") == team_code
            team_data = game_details.get("homeTeam" if is_home else "awayTeam", {})
            opponent_data = game_details.get("awayTeam" if is_home else "homeTeam", {})

            # Get team IDs
            team_id = team_data.get("id")
            opponent_id = opponent_data.get("id")

            # Extract basic stats
            game_stats["goals_for"] = int(team_data.get("score", 0))
            game_stats["goals_against"] = int(opponent_data.get("score", 0))
            game_stats["shots_on_goal"] = int(team_data.get("sog", 0))
            game_stats["shots_against"] = int(opponent_data.get("sog", 0))

            # Get player stats
            player_stats = game_details.get("playerByGameStats", {})
            team_players = player_stats.get("homeTeam" if is_home else "awayTeam", {})
            opponent_players = player_stats.get(
                "awayTeam" if is_home else "homeTeam", {}
            )

            # Process special teams stats
            for player_type in ["forwards", "defense"]:
                for player in team_players.get(player_type, []):
                    game_stats["powerplay_goals"] += int(
                        player.get("powerPlayGoals", 0)
                    )

            # Process goalie stats for shot breakdowns
            goalies = opponent_players.get("goalies", [])
            starter_goalie = next((g for g in goalies if g.get("starter", False)), None)
            if starter_goalie:
                es_shots = GameProcessor._parse_shot_string(
                    starter_goalie.get("evenStrengthShotsAgainst", "0/0")
                )
                pp_shots = GameProcessor._parse_shot_string(
                    starter_goalie.get("powerPlayShotsAgainst", "0/0")
                )
                sh_shots = GameProcessor._parse_shot_string(
                    starter_goalie.get("shorthandedShotsAgainst", "0/0")
                )

                game_stats["even_strength_shots_for"] = es_shots[1]
                game_stats["powerplay_shots_for"] = pp_shots[1]
                game_stats["shorthanded_shots_for"] = sh_shots[1]
                game_stats["powerplay_opportunities"] = pp_shots[1]

            # Process team's goalie stats
            our_goalies = team_players.get("goalies", [])
            our_starter = next(
                (g for g in our_goalies if g.get("starter", False)), None
            )
            if our_starter:
                es_shots = GameProcessor._parse_shot_string(
                    our_starter.get("evenStrengthShotsAgainst", "0/0")
                )
                pp_shots = GameProcessor._parse_shot_string(
                    our_starter.get("powerPlayShotsAgainst", "0/0")
                )
                sh_shots = GameProcessor._parse_shot_string(
                    our_starter.get("shorthandedShotsAgainst", "0/0")
                )

                game_stats["even_strength_shots_against"] = es_shots[1]
                game_stats["powerplay_shots_against"] = pp_shots[1]
                game_stats["shorthanded_shots_against"] = sh_shots[1]
                game_stats["times_shorthanded"] = pp_shots[1]

                # Calculate PK success using opponent PP goals
                opponent_pp_goals = int(our_starter.get("powerPlayGoalsAgainst", 0))
                game_stats["penalty_kill_successes"] = (
                    game_stats["times_shorthanded"] - opponent_pp_goals
                )

            # Process game outcome
            if game_stats["goals_for"] > game_stats["goals_against"]:
                game_stats["wins"] = 1
                game_stats["total_points"] = 2
                game_stats["last_10"] = 1
                if not is_home:
                    game_stats["road_wins"] = 1
                # Only count comeback if we didn't score first
                if game_stats["scoring_first"] == 0:
                    game_stats["comeback_wins"] = 1
            elif game_stats["goals_for"] < game_stats["goals_against"]:
                game_state = game_details.get("gameState", "")
                period_desc = game_details.get("periodDescriptor", {}).get(
                    "periodType", ""
                )
                if (
                    "OT" in game_state
                    or "SO" in game_state
                    or "OT" in period_desc
                    or "SO" in period_desc
                ):
                    game_stats["otl"] = 1
                    game_stats["total_points"] = 1
                    game_stats["last_10"] = 0.5
                else:
                    game_stats["losses"] = 1

            # Track empty net goals and one-goal games
            scoring = game_details.get("summary", {}).get("scoring", [])
            empty_net_goals = 0
            if scoring:
                for goal in scoring:
                    if goal.get("emptyNet", False):
                        empty_net_goals += 1

            game_stats["empty_net_goals"] = empty_net_goals

            # One goal games exclude empty netters
            score_diff = abs(game_stats["goals_for"] - game_stats["goals_against"])
            if score_diff == 1 or (score_diff - empty_net_goals == 1):
                game_stats["one_goal_games"] = 1

            logger.info(f"Processed game stats for {team_code}: {game_stats}")
            return game_stats

        except Exception as e:
            logger.error(
                f"Error processing game for {team_code}: {str(e)}", exc_info=True
            )
            return game_stats

    @staticmethod
    def _parse_shot_string(shot_string):
        """Parse shot strings like '24/26' into (saves, total_shots)."""
        try:
            if isinstance(shot_string, str) and "/" in shot_string:
                saves, total = shot_string.split("/")
                return int(saves), int(total)
            return 0, 0
        except (ValueError, AttributeError):
            return 0, 0

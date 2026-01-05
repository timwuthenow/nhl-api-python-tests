import logging
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)


class GameProcessor:
    def __init__(self):
        self._game_cache = {}

    @lru_cache(maxsize=128)
    def get_game_cache_key(self, game_id, team):
        """Create a unique cache key for game results"""
        return f"{game_id}_{team}"

    def process_game(self, game_details, team_code):
        """Process game with enhanced stats collection."""
        try:
            if not game_details.get("gamePk"):
                return self.process_game_static(game_details, team_code)

            cache_key = self.get_game_cache_key(game_details["gamePk"], team_code)

            # Check cache
            if cache_key in self._game_cache:
                return self._game_cache[cache_key]

            # Get processed game stats
            stats = self.process_game_static(game_details, team_code)

            if stats:
                self._game_cache[cache_key] = stats

            return stats

        except Exception as e:
            logger.error(f"Error processing game: {str(e)}")
            return None

    def clear_cache(self):
        """Clear the game cache"""
        self._game_cache.clear()
        self.get_game_cache_key.cache_clear()

    @staticmethod
    def process_game_static(game_details, team_code):
        """Process individual game data with improved stats tracking."""
        if not game_details:
            logger.warning(f"No game details available for team {team_code}")
            return None

        try:
            # Determine home/away and get team data
            is_home = game_details.get("homeTeam", {}).get("abbrev") == team_code
            team_data = game_details.get("homeTeam" if is_home else "awayTeam", {})
            opponent_data = game_details.get("awayTeam" if is_home else "homeTeam", {})

            # Initialize game stats
            game_stats = {
                "total_points": 0,
                "games_played": 1,
                "wins": 0,
                "losses": 0,
                "otl": 0,
                "goals_for": int(team_data.get("score", 0)),
                "goals_against": int(opponent_data.get("score", 0)),
                "shots_on_goal": int(team_data.get("sog", 0)),
                "shots_against": int(opponent_data.get("sog", 0)),
                "powerplay_goals": 0,
                "powerplay_opportunities": 0,
                "times_shorthanded": 0,
                "pk_goals_against": 0,
                "penalty_kill_successes": 0,
                "high_danger_chances_for": 0,
                "high_danger_chances_against": 0,
                "empty_net_goals": 0,
                "last_10": 0,
                "road_wins": 0,
                "scoring_first": 0,
                "comeback_wins": 0,
                "one_goal_games": 0,
                "blown_leads": 0,
                "max_lead_blown": 0,
            }

            # Get power play stats from player stats
            player_stats = game_details.get("playerByGameStats", {})
            our_team = player_stats.get("homeTeam" if is_home else "awayTeam", {})
            opp_team = player_stats.get("awayTeam" if is_home else "homeTeam", {})

            # Get power play stats from goalies
            opp_goalies = opp_team.get("goalies", [])
            our_goalies = our_team.get("goalies", [])
            opp_starter = next(
                (g for g in opp_goalies if g.get("starter", False)), None
            )
            our_starter = next(
                (g for g in our_goalies if g.get("starter", False)), None
            )

            if opp_starter:
                # Our power play stats come from opponent's goalie
                pp_shots = GameProcessor._parse_shot_string(
                    opp_starter.get("powerPlayShotsAgainst", "0/0")
                )
                game_stats["powerplay_opportunities"] = pp_shots[
                    1
                ]  # Total PP shots faced
                game_stats["powerplay_goals"] = int(
                    opp_starter.get("powerPlayGoalsAgainst", 0)
                )

            if our_starter:
                # Our PK stats come from our goalie's stats
                pk_shots = GameProcessor._parse_shot_string(
                    our_starter.get("powerPlayShotsAgainst", "0/0")
                )
                game_stats["times_shorthanded"] = pk_shots[1]  # Total PP shots we faced
                game_stats["pk_goals_against"] = int(
                    our_starter.get("powerPlayGoalsAgainst", 0)
                )

            # Calculate PK successes
            if game_stats["times_shorthanded"] > 0:
                game_stats["penalty_kill_successes"] = (
                    game_stats["times_shorthanded"] - game_stats["pk_goals_against"]
                )

            # Process power play goals from skaters as backup
            for section in ["forwards", "defense"]:
                for player in our_team.get(section, []):
                    pp_goals = int(player.get("powerPlayGoals", 0))
                    if pp_goals > game_stats["powerplay_goals"]:
                        game_stats["powerplay_goals"] = pp_goals

            # Process game outcome
            team_won = game_stats["goals_for"] > game_stats["goals_against"]
            if team_won:
                game_stats["wins"] = 1
                game_stats["total_points"] = 2
                game_stats["last_10"] = 1
                if not is_home:
                    game_stats["road_wins"] = 1
            else:
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

            # Analyze scoring timeline for blown leads and comeback wins
            team_score = 0
            opponent_score = 0
            max_lead = 0  # Maximum lead our team had
            max_deficit = 0  # Maximum deficit our team faced
            scored_first = False
            first_goal_scored = False

            # Process scoring by period to track lead changes
            scoring_summary = game_details.get("summary", {}).get("scoring", [])
            for period in scoring_summary:
                goals = period.get("goals", [])
                for goal in goals:
                    # Determine which team scored
                    goal_team = goal.get("teamAbbrev", {}).get("default", "")
                    if goal_team == team_code:
                        team_score += 1
                        if not first_goal_scored:
                            scored_first = True
                            first_goal_scored = True
                    else:
                        opponent_score += 1
                        if not first_goal_scored:
                            first_goal_scored = True

                    # Track lead/deficit
                    current_lead = team_score - opponent_score
                    if current_lead > max_lead:
                        max_lead = current_lead
                    if current_lead < -max_deficit:
                        max_deficit = -current_lead

            # Set scoring first stat
            if scored_first:
                game_stats["scoring_first"] = 1

            # Check for one-goal game
            if abs(game_stats["goals_for"] - game_stats["goals_against"]) == 1:
                game_stats["one_goal_games"] = 1

            # Blown lead: had a lead but lost the game
            if max_lead > 0 and not team_won:
                game_stats["blown_leads"] = 1
                game_stats["max_lead_blown"] = max_lead
                logger.info(f"{team_code} BLOWN LEAD: Had {max_lead}-goal lead but lost")

            # Comeback win: was behind but won the game
            if max_deficit > 0 and team_won:
                game_stats["comeback_wins"] = 1
                logger.info(f"{team_code} COMEBACK WIN: Was down {max_deficit} goals but won")

            # Process high danger chances and empty net goals
            for play in game_details.get("summary", {}).get("scoring", []):
                if play.get("typeDescKey") in ["shot", "goal"]:
                    details = play.get("details", {})
                    shot_type = details.get("shotType", "")
                    distance = details.get("shotDistance", 999)
                    is_team_shot = (
                        is_home and details.get("eventOwnerTeamType") == "home"
                    ) or (not is_home and details.get("eventOwnerTeamType") == "away")

                    if (
                        shot_type in ["Deflected", "Tip-In", "Wrap-around"]
                        or distance <= 15
                    ):
                        if is_team_shot:
                            game_stats["high_danger_chances_for"] += 1
                        else:
                            game_stats["high_danger_chances_against"] += 1

                    if play.get("emptyNet", False) and is_team_shot:
                        game_stats["empty_net_goals"] += 1

            logger.info(f"Final processed stats for {team_code}: {game_stats}")
            return game_stats

        except Exception as e:
            logger.error(
                f"Error processing game for {team_code}: {str(e)}", exc_info=True
            )
            return None

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

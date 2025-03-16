import logging
import pandas as pd
import requests
from datetime import datetime, timedelta
import csv
import os
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ImprovedRankingsCalculator:
    def __init__(self):
        """Initialize the Improved Rankings Calculator."""
        self.team_codes = [
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
        self.team_logos = {
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

    def get_nhl_standings(self):
        """Fetch current NHL standings from NHL API."""
        try:
            url = "https://api-web.nhle.com/v1/standings/now"

            # Create session with retry logic
            session = requests.Session()
            retries = requests.adapters.Retry(
                total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504]
            )
            session.mount("http://", requests.adapters.HTTPAdapter(max_retries=retries))
            session.mount(
                "https://", requests.adapters.HTTPAdapter(max_retries=retries)
            )

            response = session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            standings = []

            if "standings" in data:
                for team in data["standings"]:
                    team_abbrev = team.get("teamAbbrev", {}).get("default", "")

                    # Skip if team abbreviation is not in our list
                    if team_abbrev not in self.team_codes:
                        continue

                    last_10 = "0-0-0"
                    if "l10" in team:
                        l10_wins = team.get("l10Wins", 0)
                        l10_losses = team.get("l10Losses", 0)
                        l10_otl = team.get("l10OtLosses", 0)
                        last_10 = f"{l10_wins}-{l10_losses}-{l10_otl}"

                    # NHL API sometimes uses pointPctg, sometimes pointPct
                    point_pct = team.get("pointPctg", team.get("pointPct", 0))
                    if isinstance(point_pct, str) and point_pct.endswith("%"):
                        point_pct = float(point_pct.rstrip("%"))
                    else:
                        point_pct = float(point_pct) * 100

                    # Get the streak information
                    streak_type = team.get("streakType", "")
                    streak_count = team.get("streakCount", 0)
                    streak = (
                        f"{streak_type}{streak_count}"
                        if streak_type and streak_count
                        else ""
                    )

                    standings.append(
                        {
                            "team": team_abbrev,
                            "gp": team.get("gamesPlayed", 0),
                            "w": team.get("wins", 0),
                            "l": team.get("losses", 0),
                            "ot": team.get("otLosses", 0),
                            "pts": team.get("points", 0),
                            "p_pct": point_pct,
                            "gf": team.get("goalFor", team.get("goalsFor", 0)),
                            "ga": team.get("goalAgainst", team.get("goalsAgainst", 0)),
                            "diff": team.get("goalDifferential", 0),
                            "home": f"{team.get('homeWins', 0)}-{team.get('homeLosses', 0)}-{team.get('homeOtLosses', 0)}",
                            "away": f"{team.get('roadWins', 0)}-{team.get('roadLosses', 0)}-{team.get('roadOtLosses', 0)}",
                            "l10": last_10,
                            "streak": streak,
                        }
                    )

            # Sort by points percentage
            standings = sorted(standings, key=lambda x: x["p_pct"], reverse=True)

            # Add rank
            for i, team in enumerate(standings, 1):
                team["rank"] = i

            logger.info(
                f"Successfully fetched NHL standings for {len(standings)} teams"
            )

            # Debug output for top 5 teams
            for team in standings[:5]:
                logger.debug(
                    f"Team: {team['team']}, Rank: {team['rank']}, P%: {team['p_pct']:.1f}, Diff: {team['diff']}, Streak: {team['streak']}"
                )

            return standings

        except Exception as e:
            logger.error(f"Error fetching NHL standings: {str(e)}")
            return []

    def parse_last_10_record(self, record_str):
        """Parse last 10 record string to get wins, losses, and OTL."""
        if not record_str:
            return 0, 0, 0

        parts = record_str.split("-")
        if len(parts) != 3:
            return 0, 0, 0

        try:
            wins = int(parts[0])
            losses = int(parts[1])
            otl = int(parts[2])
            return wins, losses, otl
        except ValueError:
            return 0, 0, 0

    def calculate_winning_streak_bonus(self, standings_team):
        """Calculate bonus for winning streak."""
        streak = standings_team.get("streak", "")

        # Extract the type (W, L, OT) and count from the streak
        match = re.match(r"([WLO]+)(\d+)", streak)
        if not match:
            return 0

        streak_type, streak_count = match.groups()
        streak_count = int(streak_count)

        # Only give bonus for winning streaks
        if streak_type != "W":
            return 0

        # Scale the bonus based on streak length
        # Start giving bonuses for streaks of 3 or more
        if streak_count < 3:
            return 0
        elif streak_count <= 5:
            return streak_count * 0.5  # 0.5 points per win for streaks 3-5
        else:
            return 2.5 + (streak_count - 5) * 1.0  # More points for longer streaks

    def calculate_team_score_improved(self, team_data, standings_data):
        """
        Calculate improved team score with better balance of recent vs. season performance.

        Args:
            team_data: Dictionary with team's recent performance data
            standings_data: List of dictionaries with NHL standings

        Returns:
            Dictionary with team data including improved score
        """
        try:
            # Find team in standings
            team_code = team_data.get("team")
            team_standing = next(
                (team for team in standings_data if team["team"] == team_code), None
            )

            if not team_standing:
                logger.warning(f"No standings data found for {team_code}")
                team_data["improved_score"] = team_data.get("score", 0)
                return team_data

            # Recent performance (from original rankings) - 45% weight
            recent_performance_weight = 0.45
            recent_performance = team_data.get("score", 0)

            # Season standings - 30% weight
            season_standings_weight = 0.30
            points_pct = team_standing.get("p_pct", 0)
            goal_diff = team_standing.get("diff", 0)

            # Normalize goal differential to a similar scale as percentage
            normalized_diff = min(30, max(-30, goal_diff)) / 30 * 50

            # Parse last 10 record from standings
            wins, losses, otl = self.parse_last_10_record(team_standing.get("l10", ""))
            last_10_points_pct = (
                ((wins * 2) + otl) / ((wins + losses + otl) * 2) * 100
                if (wins + losses + otl) > 0
                else 0
            )

            season_performance = (
                (points_pct * 0.6)
                + (normalized_diff * 0.2)
                + (last_10_points_pct * 0.2)
            )

            # Special teams component - 25% weight
            special_teams_weight = 0.25
            pp_pct = team_data.get("powerplay_percentage", 0)
            pk_pct = team_data.get("penalty_kill_percentage", 0)

            special_teams_score = (pp_pct * 0.5) + (pk_pct * 0.5)

            # Calculate winning streak bonus
            streak_bonus = self.calculate_winning_streak_bonus(team_standing)

            # Calculate final score
            final_score = (
                (recent_performance * recent_performance_weight)
                + (season_performance * season_standings_weight)
                + (special_teams_score * special_teams_weight)
                + streak_bonus  # Add streak bonus directly
            )

            # Round the score
            final_score = round(final_score, 1)

            # Log the calculation for debugging
            logger.debug(
                f"{team_code}: Recent={recent_performance:.1f}*{recent_performance_weight}, "
                f"Season={season_performance:.1f}*{season_standings_weight}, "
                f"SpecialTeams={special_teams_score:.1f}*{special_teams_weight}, "
                f"StreakBonus={streak_bonus}, "
                f"Final={final_score:.1f}"
            )

            # Update team data with improved score
            team_data["improved_score"] = final_score

            return team_data

        except Exception as e:
            logger.error(
                f"Error calculating improved score for {team_data.get('team')}: {str(e)}"
            )
            # Return original data if calculation fails
            team_data["improved_score"] = team_data.get("score", 0)
            return team_data


def get_improved_rankings(current_rankings_file=None):
    """
    Get improved rankings based on current rankings file.

    Args:
        current_rankings_file: Path to current rankings CSV file. If None, uses most recent file.

    Returns:
        DataFrame with improved rankings
    """
    try:
        # Find most recent rankings file if none provided
        if not current_rankings_file:
            files = [f for f in os.listdir(".") if f.startswith("nhl_power_rankings_")]
            if not files:
                logger.error("No rankings files found")
                return pd.DataFrame()
            current_rankings_file = max(files)

        logger.info(f"Generating improved rankings based on: {current_rankings_file}")

        # Read current rankings
        original_df = pd.read_csv(current_rankings_file)
        logger.info(f"Read {len(original_df)} teams from {current_rankings_file}")

        # Get NHL standings
        calculator = ImprovedRankingsCalculator()
        standings = calculator.get_nhl_standings()

        if not standings:
            logger.error("Failed to fetch NHL standings data")
            return pd.DataFrame()

        # Process each team with improved algorithm
        rankings_data = []
        for _, row in original_df.iterrows():
            team_data = row.to_dict()
            improved_team = calculator.calculate_team_score_improved(
                team_data, standings
            )

            # Add streak information if available
            team_code = team_data.get("team")
            team_standing = next(
                (team for team in standings if team["team"] == team_code), None
            )
            if team_standing:
                streak = team_standing.get("streak", "")
                improved_team["streak"] = streak

            rankings_data.append(improved_team)

        # Create DataFrame with improved scores
        improved_df = pd.DataFrame(rankings_data)

        # Sort by improved score
        improved_df = improved_df.sort_values(
            "improved_score", ascending=False
        ).reset_index(drop=True)
        improved_df["rank"] = improved_df.index + 1

        # Create output filename
        now = datetime.now()
        output_file = f"nhl_power_rankings_improved_{now.strftime('%Y%m%d')}.csv"

        # Save to file
        improved_df.to_csv(output_file, index=False)
        logger.info(f"Saved improved rankings to {output_file}")

        # Show top 5 teams in improved rankings for verification
        logger.info("Top 5 teams in improved rankings:")
        for i in range(min(5, len(improved_df))):
            team = improved_df.iloc[i]
            streak_info = team.get("streak", "")
            streak_display = f", Streak: {streak_info}" if streak_info else ""
            logger.info(
                f"{i + 1}. {team['team']}: {team['improved_score']:.1f}{streak_display}"
            )

        return improved_df

    except Exception as e:
        logger.error(f"Error generating improved rankings: {str(e)}")
        return pd.DataFrame()


# Example usage if run directly
if __name__ == "__main__":
    # Set debug level for more detailed output
    logging.getLogger().setLevel(logging.DEBUG)

    # Get improved rankings
    rankings = get_improved_rankings()

    if not rankings.empty:
        print("\nImproved Rankings:")
        print(rankings[["rank", "team", "improved_score"]].head(10))
    else:
        print("Failed to generate improved rankings")

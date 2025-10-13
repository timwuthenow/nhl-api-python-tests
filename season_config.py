"""
NHL Season Configuration for 2025-26
"""
from datetime import datetime, timedelta

# 2025-26 NHL Regular Season
# Note: Some teams started playing regular season games as early as Oct 2
SEASON_START_DATE = datetime(2025, 10, 1)  # October 1, 2025 (to catch all October games)
CURRENT_SEASON = "20252026"
SEASON_YEAR = 2025

# Game Type codes in NHL API
GAME_TYPE_PRESEASON = 1
GAME_TYPE_REGULAR = 2
GAME_TYPE_PLAYOFFS = 3
GAME_TYPE_ALLSTAR = 4

# Only use regular season games
ALLOWED_GAME_TYPES = [GAME_TYPE_REGULAR]

# Date range for rankings calculation
# Only look at games since season start
def get_ranking_date_range():
    """Get the date range for rankings calculation"""
    end_date = datetime.now()
    # Only go back to season start, not before
    start_date = max(SEASON_START_DATE, end_date - timedelta(days=14))
    return start_date, end_date

def is_regular_season_game(game_type):
    """Check if a game is a regular season game"""
    return game_type == GAME_TYPE_REGULAR

def get_season_string():
    """Get season string for API calls"""
    return CURRENT_SEASON
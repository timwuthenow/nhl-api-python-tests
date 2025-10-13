"""
Weekly period configuration for NHL rankings
"""
from datetime import datetime, timedelta

def get_current_week_period():
    """
    Get the Monday-Sunday period for rankings.
    Rankings are always for the most recent complete or current week.
    """
    today = datetime.now()
    days_since_monday = today.weekday()  # Monday = 0, Sunday = 6
    
    # Get this week's Monday
    monday = today - timedelta(days=days_since_monday)
    sunday = monday + timedelta(days=6)
    
    return monday.date(), sunday.date()

def get_last_complete_week():
    """
    Get the last complete Monday-Sunday period.
    Used when we want only fully completed weeks.
    """
    today = datetime.now()
    days_since_monday = today.weekday()
    
    # If today is Sunday, this week is complete
    if days_since_monday == 6:
        monday = today - timedelta(days=6)
        sunday = today
    else:
        # Otherwise, get last week
        monday = today - timedelta(days=days_since_monday + 7)
        sunday = monday + timedelta(days=6)
    
    return monday.date(), sunday.date()

def filter_games_by_week(games, start_date, end_date):
    """
    Filter games to only include those within the specified week period.
    """
    filtered = []
    for game in games:
        game_date = datetime.strptime(game.get('gameDate', '2000-01-01'), '%Y-%m-%d').date()
        if start_date <= game_date <= end_date:
            filtered.append(game)
    return filtered
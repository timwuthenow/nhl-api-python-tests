#!/usr/bin/env python3
"""
Simple script to add new NHL penalties to the tracker.
Usage: python add_penalty.py
"""

import json
from datetime import datetime

def add_penalty():
    """Add a new penalty to the JSON file"""
    
    print("=== Add New NHL Penalty ===")
    
    # Get penalty details
    player_name = input("Player name (e.g., Connor McDavid): ").strip()
    if not player_name:
        print("Player name required!")
        return
        
    penalty_type = input("Type (fine/suspension): ").lower().strip()
    if penalty_type not in ['fine', 'suspension']:
        print("Must be 'fine' or 'suspension'")
        return
    
    if penalty_type == 'fine':
        amount = float(input("Fine amount (e.g., 5000): $"))
        games = None
    else:
        games = int(input("Number of games suspended: "))
        salary = float(input("Daily salary forfeited (or press Enter for $20,833 default): $") or 20833.33)
        amount = games * salary
    
    reason = input("Reason (e.g., Cross-checking, Boarding): ").strip()
    date_str = input("Date (YYYY-MM-DD) or press Enter for today: ").strip()
    
    if date_str:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        date = datetime.now()
    
    url_slug = player_name.lower().replace(' ', '-')
    
    # Create the penalty entry
    new_penalty = {
        'title': f'{player_name} {"fined" if penalty_type == "fine" else f"suspended {games} games"} for {reason}',
        'summary': f'{player_name} {"fined $" + str(int(amount)) if penalty_type == "fine" else f"suspended {games} games"} for {reason}',
        'url': f'https://www.nhl.com/news/{url_slug}-{penalty_type}',
        'date': date.isoformat(),
        'amount': amount,
        'games': games,
        'reason': reason,
        'player_name': player_name
    }
    
    # Load existing penalties
    try:
        with open('nhl_penalties_2025.json', 'r') as f:
            penalties = json.load(f)
    except:
        penalties = []
    
    # Add new penalty
    penalties.append(new_penalty)
    
    # Save back
    with open('nhl_penalties_2025.json', 'w') as f:
        json.dump(penalties, f, indent=2, default=str)
    
    print(f"\n✅ Added: {player_name} - ${amount:,.0f} ({penalty_type})")
    print(f"Total penalties in file: {len(penalties)}")

if __name__ == "__main__":
    add_penalty()
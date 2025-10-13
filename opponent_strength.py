#!/usr/bin/env python3
"""
Opponent strength calculator to weight wins/losses by opponent quality
"""
import requests
import logging
from datetime import datetime

class OpponentStrengthCalculator:
    def __init__(self):
        self.base_url = "https://api-web.nhle.com/v1"
        self.session = requests.Session()
        self.team_strengths = {}  # Cache team strengths
        
    def get_team_strength(self, team_code):
        """
        Get a team's strength based on their points percentage
        Returns a value between 0.5 (worst) and 1.5 (best)
        """
        if team_code in self.team_strengths:
            return self.team_strengths[team_code]
        
        try:
            # Get current standings to determine team strength
            url = f"{self.base_url}/standings/now"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                standings = data.get('standings', [])
                
                # Find the team in standings
                for team in standings:
                    if team.get('team', {}).get('abbrev', '') == team_code:
                        points_pct = float(team.get('p_pct', 0.5))
                        
                        # Convert points percentage to strength multiplier
                        # 0.000 pts% = 0.5 strength (bottom teams)
                        # 0.500 pts% = 1.0 strength (average teams) 
                        # 1.000 pts% = 1.5 strength (top teams)
                        strength = 0.5 + (points_pct * 1.0)
                        
                        self.team_strengths[team_code] = strength
                        return strength
                
                # If team not found, default to average
                logging.warning(f"Team {team_code} not found in standings, using average strength")
                self.team_strengths[team_code] = 1.0
                return 1.0
                
        except Exception as e:
            logging.error(f"Error getting team strength for {team_code}: {str(e)}")
            self.team_strengths[team_code] = 1.0
            return 1.0
    
    def calculate_quality_adjusted_record(self, team_code, games):
        """
        Calculate a quality-adjusted record based on opponent strength
        """
        if not games:
            return 0, 0, 0, 0.0  # wins, losses, otl, quality_score
        
        total_quality_points = 0
        wins = 0
        losses = 0
        otl = 0
        
        for game in games:
            home_team = game.get('homeTeam', {}).get('abbrev', '')
            away_team = game.get('awayTeam', {}).get('abbrev', '')
            home_score = game.get('homeTeam', {}).get('score', 0)
            away_score = game.get('awayTeam', {}).get('score', 0)
            game_state = game.get('gameState', '')
            
            # Determine opponent
            if home_team == team_code:
                opponent = away_team
                team_score = home_score
                opponent_score = away_score
            else:
                opponent = home_team
                team_score = away_score
                opponent_score = home_score
            
            # Get opponent strength
            opponent_strength = self.get_team_strength(opponent)
            
            # Calculate quality points based on result and opponent strength
            if team_score > opponent_score:
                # Win: 2 points * opponent strength
                quality_points = 2.0 * opponent_strength
                wins += 1
            elif team_score < opponent_score:
                if game_state in ['FINAL/OT', 'FINAL/SO']:
                    # OT/SO Loss: 1 point * opponent strength  
                    quality_points = 1.0 * opponent_strength
                    otl += 1
                else:
                    # Regulation Loss: 0 points (but factor in opponent strength)
                    # Losing to a good team is "less bad" than losing to a bad team
                    quality_points = 0.0
                    losses += 1
            
            total_quality_points += quality_points
            
            logging.debug(f"{team_code} vs {opponent} (strength: {opponent_strength:.2f}): "
                         f"{team_score}-{opponent_score} = {quality_points:.2f} quality points")
        
        # Calculate quality-adjusted points percentage
        max_possible_points = len(games) * 2.0 * 1.5  # Max if beating all top teams
        quality_score = (total_quality_points / max_possible_points) * 100 if max_possible_points > 0 else 0
        
        return wins, losses, otl, quality_score

# Test function  
def test_quality_adjustment():
    """Test quality adjustment with Rangers vs different opponents"""
    calc = OpponentStrengthCalculator()
    
    # Test individual team strengths
    print("🔍 TEAM STRENGTH ANALYSIS:")
    test_teams = ['PIT', 'BUF', 'FLA', 'BOS', 'NYR']
    
    for team in test_teams:
        strength = calc.get_team_strength(team)
        print(f"  {team}: {strength:.3f} strength")
    
    print(f"\nThis shows Rangers beating weak teams (PIT, BUF) vs strong teams (FLA, BOS)")
    print(f"Quality-adjusted scoring will reduce the value of wins over weak opponents")

if __name__ == "__main__":
    test_quality_adjustment()
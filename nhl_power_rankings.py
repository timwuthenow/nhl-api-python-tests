# nhl_power_rankings.py
import logging
from datetime import datetime, timedelta
import pandas as pd
from nhl_stats_fetcher import NHLStatsFetcher
from nhl_game_processor import GameProcessor
from nhl_rankings_calculator import RankingsCalculator

class NHLPowerRankings:
    def __init__(self, days_back=14):
        """
        Initialize NHL Power Rankings calculator.
        
        Args:
            days_back (int): Number of days to look back for games
        """
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=days_back)
        self.fetcher = NHLStatsFetcher()
        self.processor = GameProcessor()
        self.calculator = RankingsCalculator()
        self.team_codes = [
            'ANA', 'BOS', 'BUF', 'CAR', 'CBJ', 'CGY', 'CHI', 'COL', 'DAL', 'DET', 
            'EDM', 'FLA', 'LAK', 'MIN', 'MTL', 'NJD', 'NSH', 'NYI', 'NYR', 'OTT', 
            'PHI', 'PIT', 'SEA', 'SJS', 'STL', 'TBL', 'TOR', 'UTA', 'VAN', 'VGK', 
            'WPG', 'WSH'
        ]

    def calculate_rankings(self):
        """Calculate power rankings for all teams."""
        rankings = []
        
        for team_code in self.team_codes:
            try:
                # Get team stats and schedule
                team_stats = self.fetcher.get_team_stats(team_code, self.end_date)
                schedule = self.fetcher.get_schedule(team_code, self.start_date, self.end_date)
                
                if not schedule:
                    logging.warning(f"No games found for {team_code}")
                    continue
                    
                # Process each game
                game_stats = []
                for game in schedule:
                    details = self.fetcher.get_game_details(game['id'])
                    if details:
                        game_stats.append(self.processor.process_game(details, team_code))
                
                # Aggregate stats and calculate score
                if game_stats:
                    aggregated_stats = self.processor.aggregate_stats(game_stats)
                    team_score = self.calculator.calculate_team_score(
                        aggregated_stats, team_stats, team_code
                    )
                    if team_score:
                        rankings.append(team_score)
                        
            except Exception as e:
                logging.error(f"Error processing {team_code}: {str(e)}")
                continue
                
        return rankings

    def run(self):
        """Execute power rankings calculation and display results."""
        logging.info(f"Calculating NHL Power Rankings from {self.start_date.strftime('%Y-%m-%d')} "
                    f"to {self.end_date.strftime('%Y-%m-%d')}")
        
        # Calculate rankings
        rankings = self.calculate_rankings()
        
        # Create DataFrame
        df = self.calculator.create_rankings_dataframe(rankings)
        
        if not df.empty:
            # Display results
            print(f"\nNHL Power Rankings ({self.start_date.strftime('%Y-%m-%d')} to "
                  f"{self.end_date.strftime('%Y-%m-%d')}):")
            print(df.to_string())
            
            # Save to CSV
            filename = f"nhl_power_rankings_{self.end_date.strftime('%Y%m%d')}.csv"
            self.calculator.save_rankings(df, filename)
        else:
            logging.error("No valid data to create rankings")

def main():
    """Main entry point for the NHL Power Rankings program."""
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(
                f"nhl_power_rankings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            ),
            logging.StreamHandler()
        ]
    )
    
    try:
        # Run rankings
        rankings = NHLPowerRankings(days_back=14)
        rankings.run()
    except Exception as e:
        logging.error(f"Program failed: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
import re
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RedditPowerRankingsParser:
    def __init__(self):
        # Previous week rankings for proper delta calculation
        self.last_week_rankings = {
            "FLA": 1,  # Florida Panthers
            "CAR": 2,  # Carolina Hurricanes  
            "COL": 3,  # Colorado Avalanche
            "DAL": 4,  # Dallas Stars
            "EDM": 5,  # Edmonton Oilers
            "WPG": 6,  # Winnipeg Jets
            "MTL": 7,  # Montreal Canadiens
            "VGK": 8,  # Vegas Golden Knights
            "BOS": 9,  # Boston Bruins
            "WSH": 10, # Washington Capitals
            "TOR": 11, # Toronto Maple Leafs
            "NYR": 12, # New York Rangers
            "NJD": 13, # New Jersey Devils
            "MIN": 14, # Minnesota Wild
            "SEA": 15, # Seattle Kraken
            "PIT": 16, # Pittsburgh Penguins
            "OTT": 17, # Ottawa Senators
            "DET": 18, # Detroit Red Wings
            "LAK": 19, # Los Angeles Kings
            "CBJ": 20, # Columbus Blue Jackets
            "VAN": 21, # Vancouver Canucks
            "STL": 22, # St. Louis Blues
            "UTA": 23, # Utah
            "TBL": 24, # Tampa Bay Lightning
            "NSH": 25, # Nashville Predators
            "ANA": 26, # Anaheim Ducks
            "CGY": 27, # Calgary Flames
            "PHI": 28, # Philadelphia Flyers
            "NYI": 29, # New York Islanders
            "CHI": 30, # Chicago Blackhawks
            "SJS": 31, # San Jose Sharks
            "BUF": 32  # Buffalo Sabres
        }
        
        # NHL team logos (using ESPN or NHL.com URLs)
        self.team_logos = {
            "FLA": "https://a.espncdn.com/i/teamlogos/nhl/500/fla.png",
            "CAR": "https://a.espncdn.com/i/teamlogos/nhl/500/car.png",
            "DAL": "https://a.espncdn.com/i/teamlogos/nhl/500/dal.png",
            "COL": "https://a.espncdn.com/i/teamlogos/nhl/500/col.png",
            "EDM": "https://a.espncdn.com/i/teamlogos/nhl/500/edm.png",
            "BOS": "https://a.espncdn.com/i/teamlogos/nhl/500/bos.png",
            "MTL": "https://a.espncdn.com/i/teamlogos/nhl/500/mtl.png",
            "NYR": "https://a.espncdn.com/i/teamlogos/nhl/500/nyr.png",
            "WPG": "https://a.espncdn.com/i/teamlogos/nhl/500/wpg.png",
            "VGK": "https://a.espncdn.com/i/teamlogos/nhl/500/vgk.png",
            "MIN": "https://a.espncdn.com/i/teamlogos/nhl/500/min.png",
            "TOR": "https://a.espncdn.com/i/teamlogos/nhl/500/tor.png",
            "NJD": "https://a.espncdn.com/i/teamlogos/nhl/500/njd.png",
            "WSH": "https://a.espncdn.com/i/teamlogos/nhl/500/wsh.png",
            "SEA": "https://a.espncdn.com/i/teamlogos/nhl/500/sea.png",
            "OTT": "https://a.espncdn.com/i/teamlogos/nhl/500/ott.png",
            "PIT": "https://a.espncdn.com/i/teamlogos/nhl/500/pit.png",
            "CBJ": "https://a.espncdn.com/i/teamlogos/nhl/500/cbj.png",
            "LAK": "https://a.espncdn.com/i/teamlogos/nhl/500/la.png",
            "DET": "https://a.espncdn.com/i/teamlogos/nhl/500/det.png",
            "STL": "https://a.espncdn.com/i/teamlogos/nhl/500/stl.png",
            "NSH": "https://a.espncdn.com/i/teamlogos/nhl/500/nsh.png",
            "VAN": "https://a.espncdn.com/i/teamlogos/nhl/500/van.png",
            "TBL": "https://a.espncdn.com/i/teamlogos/nhl/500/tb.png",
            "UTA": "https://a.espncdn.com/i/teamlogos/nhl/500/utah.png",
            "CGY": "https://a.espncdn.com/i/teamlogos/nhl/500/cgy.png",
            "ANA": "https://a.espncdn.com/i/teamlogos/nhl/500/ana.png",
            "PHI": "https://a.espncdn.com/i/teamlogos/nhl/500/phi.png",
            "SJS": "https://a.espncdn.com/i/teamlogos/nhl/500/sj.png",
            "NYI": "https://a.espncdn.com/i/teamlogos/nhl/500/nyi.png",
            "CHI": "https://a.espncdn.com/i/teamlogos/nhl/500/chi.png",
            "BUF": "https://a.espncdn.com/i/teamlogos/nhl/500/buf.png"
        }
        
        # NHL team primary colors
        self.team_colors = {
            "FLA": "#041E42",  # Navy Blue
            "CAR": "#CC0000",  # Red
            "DAL": "#006847",  # Victory Green
            "COL": "#6F263D",  # Burgundy
            "EDM": "#041E42",  # Navy Blue
            "BOS": "#FFB81C",  # Gold
            "MTL": "#AF1E2D",  # Red
            "NYR": "#0038A8",  # Blue
            "WPG": "#041E42",  # Navy Blue
            "VGK": "#B4975A",  # Gold
            "MIN": "#A6192E",  # Red
            "TOR": "#003E7E",  # Blue
            "NJD": "#CE1126",  # Red
            "WSH": "#C8102E",  # Red
            "SEA": "#99D9D9",  # Ice Blue
            "OTT": "#E31837",  # Red
            "PIT": "#FCB514",  # Gold
            "CBJ": "#002654",  # Navy Blue
            "LAK": "#111111",  # Black
            "DET": "#CE1126",  # Red
            "STL": "#002F87",  # Blue
            "NSH": "#FFB81C",  # Gold
            "VAN": "#00205B",  # Navy Blue
            "TBL": "#002868",  # Blue
            "UTA": "#6C2C2F",  # Burgundy
            "CGY": "#C8102E",  # Red
            "ANA": "#F47A38",  # Orange
            "PHI": "#F74902",  # Orange
            "SJS": "#006D75",  # Teal
            "NYI": "#00539B",  # Blue
            "CHI": "#CF0A2C",  # Red
            "BUF": "#002654"   # Navy Blue
        }
        
        self.team_abbrev_map = {
            "Florida Panthers": "FLA",
            "Carolina Hurricanes": "CAR", 
            "Dallas Stars": "DAL",
            "Colorado Avalanche": "COL",
            "Edmonton Oilers": "EDM",
            "Boston Bruins": "BOS",
            "Montreal Canadiens": "MTL",
            "New York Rangers": "NYR",
            "Winnipeg Jets": "WPG",
            "Vegas Golden Knights": "VGK",
            "Minnesota Wild": "MIN",
            "Toronto Maple Leafs": "TOR",
            "New Jersey Devils": "NJD",
            "Washington Capitals": "WSH",
            "Seattle Kraken": "SEA",
            "Ottawa Senators": "OTT",
            "Pittsburgh Penguins": "PIT",
            "Columbus Blue Jackets": "CBJ",
            "Los Angeles Kings": "LAK",
            "Detroit Red Wings": "DET",
            "St. Louis Blues": "STL",
            "Nashville Predators": "NSH",
            "Vancouver Canucks": "VAN",
            "Tampa Bay Lightning": "TBL",
            "Utah Mammoth": "UTA",  # Utah Hockey Club
            "Calgary Flames": "CGY",
            "Anaheim Ducks": "ANA",
            "Philadelphia Flyers": "PHI",
            "San Jose Sharks": "SJS",
            "New York Islanders": "NYI",
            "Chicago Blackhawks": "CHI",
            "Buffalo Sabres": "BUF"
        }

    def parse_markdown(self, markdown_text):
        """Parse r/hockey power rankings markdown into structured data."""
        try:
            lines = markdown_text.strip().split('\n')
            
            # Extract week dates from title
            week_info = self.extract_week_info(lines[0] if lines else "")
            
            # Find the rankings table
            rankings_data = []
            in_table = False
            
            for line in lines:
                # Check if we've reached the rankings table
                if 'Ranking (avg)' in line and 'Team' in line:
                    in_table = True
                    continue
                
                # Skip header separator
                if in_table and line.startswith(':---:'):
                    continue
                
                # Parse ranking rows
                if in_table and line.strip():
                    if line.startswith('1 (') or re.match(r'^\d+\s*\(', line):
                        parsed_row = self.parse_ranking_row(line)
                        if parsed_row:
                            rankings_data.append(parsed_row)
            
            if not rankings_data:
                logger.warning("No rankings data found in markdown")
                return None
            
            # Create DataFrame
            df = pd.DataFrame(rankings_data)
            df['week_start'] = week_info.get('start_date')
            df['week_end'] = week_info.get('end_date')
            df['parsed_date'] = datetime.now()
            
            logger.info(f"Parsed {len(df)} teams from r/hockey rankings")
            return df
            
        except Exception as e:
            logger.error(f"Error parsing markdown: {e}")
            return None

    def extract_week_info(self, title_line):
        """Extract week date range from title."""
        # Pattern: Week Oct 6, 2025 - Oct 12, 2025
        date_pattern = r'Week (\w+ \d+, \d+) - (\w+ \d+, \d+)'
        match = re.search(date_pattern, title_line)
        
        if match:
            try:
                start_str = match.group(1)
                end_str = match.group(2)
                
                start_date = datetime.strptime(start_str, "%b %d, %Y").strftime("%Y-%m-%d")
                end_date = datetime.strptime(end_str, "%b %d, %Y").strftime("%Y-%m-%d")
                
                return {
                    'start_date': start_date,
                    'end_date': end_date
                }
            except:
                pass
        
        return {'start_date': None, 'end_date': None}

    def parse_ranking_row(self, line):
        """Parse a single ranking row."""
        try:
            # Split by | and clean up
            parts = [p.strip() for p in line.split('|')]
            
            if len(parts) < 4:
                return None
            
            # Extract ranking and average
            rank_avg = parts[0].strip()
            rank_match = re.match(r'(\d+)\s*\(([\d.]+)\)', rank_avg)
            if not rank_match:
                return None
            
            rank = int(rank_match.group(1))
            avg_score = float(rank_match.group(2))
            
            # Extract team name from markdown link
            team_cell = parts[1].strip()
            team_match = re.search(r'\[([^\]]+)\]', team_cell)
            team_name = team_match.group(1) if team_match else team_cell
            
            # Get team abbreviation
            team_abbrev = self.team_abbrev_map.get(team_name, team_name[:3].upper())

            # Extract delta from the markdown (parts[2])
            delta = 0
            if len(parts) > 2:
                delta_str = parts[2].strip()
                if delta_str and delta_str != '-':
                    try:
                        delta = int(delta_str)
                    except ValueError:
                        logger.warning(f"Could not parse delta '{delta_str}' for {team_name}")
                        delta = 0

            # Extract overall record
            overall_record = parts[3].strip() if len(parts) > 3 else ""
            
            # Extract week record  
            week_record = parts[4].strip() if len(parts) > 4 else ""
            
            return {
                'rank': rank,
                'avg_score': avg_score,
                'team_name': team_name,
                'team_abbrev': team_abbrev,
                'delta': delta,
                'overall_record': overall_record,
                'week_record': week_record
            }
            
        except Exception as e:
            logger.warning(f"Error parsing ranking row: {line[:50]}... - {e}")
            return None

    def format_for_display(self, df):
        """Format the parsed data for display."""
        if df is None or df.empty:
            return []
        
        # Sort by rank to ensure proper ordering
        df = df.sort_values('rank')
        
        display_data = []
        for _, row in df.iterrows():
            # Determine change indicator
            change_indicator = ""
            change_class = "no-change"
            
            if row['delta'] > 0:
                change_indicator = f"⬆️{row['delta']}"
                change_class = "rank-up"
            elif row['delta'] < 0:
                change_indicator = f"⬇️{abs(row['delta'])}"
                change_class = "rank-down"
            else:
                change_indicator = "—"
            
            display_data.append({
                'rank': row['rank'],
                'team_name': row['team_name'],
                'team_abbrev': row['team_abbrev'],
                'avg_score': f"{row['avg_score']:.2f}",
                'change_indicator': change_indicator,
                'change_class': change_class,
                'overall_record': row['overall_record'],
                'week_record': row['week_record'],
                'logo_url': self.team_logos.get(row['team_abbrev'], ""),
                'team_color': self.team_colors.get(row['team_abbrev'], "#FFB81C")
            })
        
        # Calculate biggest movers
        biggest_riser = None
        biggest_faller = None
        
        for team in display_data:
            # Extract delta from the data
            delta = 0
            for _, row in df.iterrows():
                if row['team_abbrev'] == team['team_abbrev']:
                    delta = row['delta']
                    break
            
            # Check for biggest riser (most positive delta)
            if delta > 0:
                if biggest_riser is None or delta > biggest_riser['delta']:
                    biggest_riser = {
                        'team': team,
                        'delta': delta
                    }
            
            # Check for biggest faller (most negative delta)
            if delta < 0:
                if biggest_faller is None or abs(delta) > biggest_faller['delta']:
                    biggest_faller = {
                        'team': team,
                        'delta': abs(delta)
                    }
        
        return {
            'teams': display_data,
            'biggest_riser': biggest_riser,
            'biggest_faller': biggest_faller
        }
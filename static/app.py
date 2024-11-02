from flask import Flask, render_template, request, jsonify
from datetime import datetime
import pandas as pd
from nhl_power_rankings import get_team_rankings, download_team_logos
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Download logos when the app starts, but don't block if it fails
team_codes = ['ANA', 'BOS', 'BUF', 'CAR', 'CBJ', 'CGY', 'CHI', 'COL', 'DAL', 'DET', 'EDM', 'FLA', 'LAK', 'MIN', 'MTL', 'NJD', 'NSH', 'NYI', 'NYR', 'OTT', 'PHI', 'PIT', 'SEA', 'SJS', 'STL', 'TBL', 'TOR', 'VAN', 'VGK', 'WPG', 'WSH']
try:
    download_team_logos(team_codes)
except Exception as e:
    app.logger.error(f"Error downloading logos: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_rankings')
def get_rankings():
    try:
        date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        rankings = get_team_rankings(target_date)
        
        if rankings.empty:
            return jsonify({'error': 'No rankings data available'}), 404
        
        return jsonify(rankings.to_dict(orient='records'))
    except Exception as e:
        app.logger.error(f"Error in get_rankings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/update_score', methods=['POST'])
def update_score():
    data = request.json
    team = data['team']
    adjustment = data['adjustment']
    # Here you would update the rankings based on the adjustment
    # For now, we'll just return a success message
    return jsonify({'status': 'success', 'message': f'Updated {team} score by {adjustment}%'})

if __name__ == '__main__':
    app.run(debug=True)

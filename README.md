# NHL Power Rankings

A Flask-based web application that calculates and displays NHL team power rankings based on recent performance, statistical analysis, and season standings. The rankings update automatically every 30 minutes using the official NHL Stats API. I built this as a learn Python and the NHL APIs project since I partake in Reddit's NHL Powerrankings. I figured being someone who works in Open Source Software, this is a great way for transparency for how my methods work this year. 

## Features

- Real-time power rankings calculation
- Weighted scoring system considering:
  - Recent performance (last 14 days)
  - Season standings
  - Special teams performance
  - Goal and shot differentials
  - Quality wins (comebacks, close games)
  - Road performance
- Automatic updates every 30 minutes
- Mobile-responsive web interface
- Color-coded rankings (top 3 teams in green, bottom 3 in red)
- Manual refresh capability

## NHL API Integration

This project uses the unofficial NHL Stats API endpoints:

```
Base URL: https://statsapi.web.nhl.com/api/v1
```

Key endpoints used:
- Team Stats: `/teams/{teamId}/stats`
- Schedule: `/schedule?teamId={teamId}&startDate={date}&endDate={date}`
- Game Details: `/game/{gameId}/feed/live`

Note: While these APIs are publicly available, they are not officially documented by the NHL. The endpoints may change without notice.

## Setup Instructions

### Prerequisites

- Python 3.9+
- pip
- Virtual environment (recommended)

### Local Development Setup

1. Clone the repository:
```bash
https://github.com/timwuthenow/nhl-api-pyton-tests.git
cd nhl-power-rankings
```

2. Create and activate virtual environment:
```bash
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Generate a secret key:
```bash
python generate_key.py
```

5. Create `.env` file (on Mac you can't use port 5000 which is fun so I use 5002):
```
FLASK_ENV=development
PORT=5002
UPDATE_INTERVAL_MINUTES=30
LOG_LEVEL=INFO
SECRET_KEY=<your-generated-key>
```

6. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:5002`

### Deployment

This application can be deployed to Railway:

1. Create a Railway account
2. Connect your GitHub repository
3. Set environment variables in Railway dashboard:
```
FLASK_ENV=production
PORT=5002
UPDATE_INTERVAL_MINUTES=30
LOG_LEVEL=INFO
SECRET_KEY=<your-generated-key>
```

## Project Structure

```
nhl-rankings/
│
├── app.py                      # Main Flask application
├── config.py                   # Configuration settings
├── nhl_rankings_calculator.py  # Rankings calculation logic
├── nhl_game_processor.py       # Game data processing
├── nhl_stats_fetcher.py       # NHL API interaction
│
├── templates/
│   ├── base.html              # Base template
│   └── rankings.html          # Rankings display template
│
├── static/                     # Static assets
│   ├── css/
│   └── js/
│
├── requirements.txt           # Python dependencies
├── Procfile                  # Deployment configuration
├── .env                      # Local environment variables
└── .gitignore
```

## Ranking Algorithm

The power rankings are calculated using a weighted scoring system:

1. Recent Performance (75 points max):
   - Points percentage in last 14 days
   - Road wins bonus

2. Season Impact (25 points max):
   - Regulation wins (2.0x weight)
   - Overtime wins (1.5x weight)
   - Shootout wins (1.0x weight)

3. Performance Metrics (50 points max):
   - Goal differential per game
   - Shot differential per game
   - Save percentage above 85%
   - Shooting percentage above 8%

4. Special Teams (30 points max):
   - Power play efficiency
   - Penalty kill efficiency

5. Quality Wins (20 points max):
   - Close game performance
   - Comeback wins
   - First goal percentage

## API Response Examples

### Team Stats Response
```json
{
  "stats": [{
    "type": {
      "displayName": "statsSingleSeason"
    },
    "splits": [{
      "stat": {
        "gamesPlayed": 82,
        "wins": 50,
        "losses": 25,
        "ot": 7,
        "pts": 107,
        "ptPctg": "65.2",
        "goalsPerGame": 3.562,
        "goalsAgainst": 2.562
        // ... additional stats
      }
    }]
  }]
}
```

### Game Data Response
```json
{
  "gameData": {
    "status": {
      "detailedState": "Final"
    },
    "teams": {
      "away": {
        "id": 123,
        "name": "Team Name"
      },
      "home": {
        "id": 456,
        "name": "Team Name"
      }
    }
  },
  "liveData": {
    "boxscore": {
      "teams": {
        "away": {
          "teamStats": {
            "teamSkaterStats": {
              "goals": 3,
              "shots": 30,
              "powerPlayGoals": 1,
              "powerPlayOpportunities": 4
              // ... additional stats
            }
          }
        }
      }
    }
  }
}
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Acknowledgments

- NHL Stats API (unofficial)
- Team logos provided by NHL
- Rankings algorithm inspired by various sports analytics approaches

## Disclaimer

This project is not affiliated with or endorsed by the National Hockey League (NHL).
Team logos and statistics are property of the NHL and their respective teams.
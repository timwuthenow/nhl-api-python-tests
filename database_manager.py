import sqlite3
import pandas as pd
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path="nhl_rankings.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Rankings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rankings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team TEXT NOT NULL,
                    ranking_type TEXT NOT NULL,
                    ultimate_rank INTEGER,
                    ultimate_score REAL,
                    points INTEGER,
                    games_played INTEGER,
                    goals_for INTEGER,
                    goals_against INTEGER,
                    goal_differential INTEGER,
                    points_percentage REAL,
                    powerplay_percentage REAL,
                    penalty_kill_percentage REAL,
                    last_10_record TEXT,
                    score REAL,
                    sos_grade TEXT,
                    schedule_difficulty REAL,
                    expected_goals REAL,
                    corsi_for_pct REAL,
                    fenwick_for_pct REAL,
                    pdo REAL,
                    goal_dominance REAL,
                    win_quality REAL,
                    clutch_performance REAL,
                    momentum REAL,
                    last_10_results TEXT,
                    logo TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for faster queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_team_type_created ON rankings(team, ranking_type, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON rankings(created_at)")
    
    def save_rankings(self, rankings_df, ranking_type="ultimate"):
        """Save rankings to database."""
        try:
            # Add metadata
            rankings_df = rankings_df.copy()
            rankings_df['ranking_type'] = ranking_type
            rankings_df['created_at'] = datetime.now()
            
            with sqlite3.connect(self.db_path) as conn:
                # Delete old rankings of this type (keep only latest)
                conn.execute("DELETE FROM rankings WHERE ranking_type = ?", (ranking_type,))
                
                # Insert new rankings
                rankings_df.to_sql('rankings', conn, if_exists='append', index=False)
                
            logger.info(f"Saved {len(rankings_df)} {ranking_type} rankings to database")
            return True
            
        except Exception as e:
            logger.error(f"Error saving rankings to database: {e}")
            return False
    
    def get_latest_rankings(self, ranking_type="ultimate"):
        """Get the latest rankings from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT * FROM rankings 
                    WHERE ranking_type = ? 
                    ORDER BY created_at DESC
                    LIMIT 32
                """
                df = pd.read_sql_query(query, conn, params=(ranking_type,))
                
                if df.empty:
                    logger.warning(f"No {ranking_type} rankings found in database")
                    return pd.DataFrame()
                
                # Sort by ultimate_rank for display
                df = df.sort_values('ultimate_rank').reset_index(drop=True)
                logger.info(f"Retrieved {len(df)} {ranking_type} rankings from database")
                return df
                
        except Exception as e:
            logger.error(f"Error retrieving rankings from database: {e}")
            return pd.DataFrame()
    
    def get_rankings_metadata(self, ranking_type="ultimate"):
        """Get metadata about the latest rankings."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT created_at, COUNT(*) as team_count
                    FROM rankings 
                    WHERE ranking_type = ?
                    GROUP BY created_at
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                result = conn.execute(query, (ranking_type,)).fetchone()
                
                if result:
                    return {
                        'last_updated': result[0],
                        'team_count': result[1]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error getting rankings metadata: {e}")
            return None
    
    def cleanup_old_rankings(self, keep_days=7):
        """Clean up old rankings data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    DELETE FROM rankings 
                    WHERE created_at < datetime('now', '-{} days')
                """.format(keep_days)
                
                cursor = conn.execute(query)
                deleted_count = cursor.rowcount
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old ranking records")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old rankings: {e}")
    
    def export_to_csv(self, ranking_type="ultimate", filename=None):
        """Export current rankings to CSV for backup."""
        try:
            df = self.get_latest_rankings(ranking_type)
            if df.empty:
                return None
                
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d")
                filename = f"nhl_power_rankings_{ranking_type}_{timestamp}.csv"
            
            # Remove database metadata columns for CSV export
            export_columns = [col for col in df.columns if col not in ['id', 'ranking_type', 'created_at']]
            df[export_columns].to_csv(filename, index=False)
            
            logger.info(f"Exported {ranking_type} rankings to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return None
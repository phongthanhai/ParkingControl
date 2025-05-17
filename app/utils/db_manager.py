import sqlite3
import os
import json
import time
from datetime import datetime
import threading

class DBManager:
    """
    Singleton database manager for local SQLite operations during offline mode.
    Manages a schema similar to the backend database.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path=None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DBManager, cls).__new__(cls)
                cls._instance._db_path = db_path or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'local_data.db')
                cls._instance._connection = None
                cls._instance._initialize_db()
            return cls._instance
    
    def _initialize_db(self):
        """Initialize the database schema if it doesn't exist."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Check if tables already exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_status'")
            tables_exist = cursor.fetchone() is not None
            
            if not tables_exist:
                print("Initializing database schema...")
                
                # Create vehicle table
                cursor.execute('''
                    CREATE TABLE vehicle (
                        plate_id TEXT PRIMARY KEY,
                        is_blacklisted INTEGER DEFAULT 0 NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        synced INTEGER DEFAULT 0
                    )
                ''')
                
                # Create parking_session table - removed foreign key to parking_lot
                cursor.execute('''
                    CREATE TABLE parking_session (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plate_id TEXT NOT NULL,
                        lot_id INTEGER NOT NULL,
                        entry_time TIMESTAMP NOT NULL,
                        entry_img TEXT,
                        entry_confidence REAL,
                        exit_time TIMESTAMP,
                        exit_img TEXT,
                        exit_confidence REAL,
                        status TEXT DEFAULT 'pending' CHECK (
                            status IN ('pending', 'finished')
                        ),
                        synced INTEGER DEFAULT 0,
                        remote_id INTEGER DEFAULT NULL,
                        FOREIGN KEY (plate_id) REFERENCES vehicle(plate_id)
                    )
                ''')
                
                # Create barrier_action table
                cursor.execute('''
                    CREATE TABLE barrier_action (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER,
                        action_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        action_type TEXT CHECK (action_type IN ('entry', 'exit')),
                        trigger_type TEXT CHECK (trigger_type IN ('auto', 'manual')),
                        synced INTEGER DEFAULT 0,
                        remote_id INTEGER DEFAULT NULL,
                        FOREIGN KEY (session_id) REFERENCES parking_session(id)
                    )
                ''')
                
                # Create sync_status table to track last sync times
                cursor.execute('''
                    CREATE TABLE sync_status (
                        table_name TEXT PRIMARY KEY,
                        last_sync_time TIMESTAMP DEFAULT 0
                    )
                ''')
                
                # Insert initial sync_status records
                tables = ['vehicle', 'parking_session', 'barrier_action']
                for table in tables:
                    cursor.execute('INSERT INTO sync_status (table_name) VALUES (?)', (table,))
                
                # Create local_log table for activity tracking with synced column
                cursor.execute('''
                    CREATE TABLE local_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        lane TEXT NOT NULL,
                        plate_id TEXT NOT NULL,
                        confidence REAL,
                        type TEXT NOT NULL,
                        synced INTEGER DEFAULT 0,
                        image_path TEXT
                    )
                ''')
                
                # Create an index for sync status
                cursor.execute('CREATE INDEX idx_vehicle_sync ON vehicle(synced)')
                cursor.execute('CREATE INDEX idx_session_sync ON parking_session(synced)')
                cursor.execute('CREATE INDEX idx_action_sync ON barrier_action(synced)')
                cursor.execute('CREATE INDEX idx_log_sync ON local_log(synced)')
                
                conn.commit()
                print("Database initialized successfully")
            else:
                # Check if local_log table has synced column
                try:
                    cursor.execute("PRAGMA table_info(local_log)")
                    columns = cursor.fetchall()
                    column_names = [col[1] for col in columns]
                    
                    # If synced column doesn't exist, add it
                    if 'synced' not in column_names:
                        print("Adding synced column to local_log table...")
                        cursor.execute("ALTER TABLE local_log ADD COLUMN synced INTEGER DEFAULT 0")
                        conn.commit()
                        print("Added synced column to local_log table")
                        
                        # Create index for the new column
                        cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_sync ON local_log(synced)')
                        conn.commit()
                        print("Created index for synced column")
                except Exception as e:
                    print(f"Error checking or updating local_log table: {str(e)}")
                    
        except Exception as e:
            print(f"Database initialization error: {str(e)}")
            if conn:
                conn.rollback()
    
    def _get_connection(self):
        """Get a SQLite connection with thread safety."""
        if self._connection is None:
            self._connection = sqlite3.connect(self._db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    def close(self):
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    # Vehicle methods
    def add_vehicle(self, plate_id, is_blacklisted=False):
        """Add a vehicle to the local database."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO vehicle (plate_id, is_blacklisted, synced) VALUES (?, ?, ?)',
                (plate_id, 1 if is_blacklisted else 0, 0)
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error adding vehicle: {str(e)}")
            conn.rollback()
            return None
    
    def get_vehicle(self, plate_id):
        """Get vehicle information by plate ID."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM vehicle WHERE plate_id = ?', (plate_id,))
            result = cursor.fetchone()
            if result:
                return dict(result)
            return None
        except Exception as e:
            print(f"Error getting vehicle: {str(e)}")
            return None
    
    def is_blacklisted(self, plate_id):
        """Check if a vehicle is blacklisted."""
        try:
            vehicle = self.get_vehicle(plate_id)
            if vehicle:
                return bool(vehicle['is_blacklisted'])
            return False
        except Exception as e:
            print(f"Error checking blacklist: {str(e)}")
            return False
    
    def update_blacklist(self, vehicles_data):
        """Update the local blacklist with data from the API."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Start transaction
            conn.execute('BEGIN TRANSACTION')
            
            # Get current time for sync status
            now = time.time()
            
            # Update each vehicle in the list
            for vehicle in vehicles_data:
                plate_id = vehicle['plate_id']
                is_blacklisted = vehicle.get('is_blacklisted', False)
                
                # Check if vehicle exists
                cursor.execute('SELECT plate_id FROM vehicle WHERE plate_id = ?', (plate_id,))
                if cursor.fetchone():
                    cursor.execute(
                        'UPDATE vehicle SET is_blacklisted = ?, synced = 1 WHERE plate_id = ?',
                        (1 if is_blacklisted else 0, plate_id)
                    )
                else:
                    cursor.execute(
                        'INSERT INTO vehicle (plate_id, is_blacklisted, synced) VALUES (?, ?, 1)',
                        (plate_id, 1 if is_blacklisted else 0)
                    )
            
            # Update sync status
            cursor.execute('UPDATE sync_status SET last_sync_time = ? WHERE table_name = ?', (now, 'vehicle'))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating blacklist: {str(e)}")
            if conn:
                conn.rollback()
            return False
    
    def get_all_blacklisted(self):
        """Get all blacklisted vehicles."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM vehicle WHERE is_blacklisted = 1')
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting blacklisted vehicles: {str(e)}")
            return []
    
    # Log methods
    def add_log_entry(self, lane, plate_id, confidence, entry_type, image_path=None, synced=False):
        """Add a log entry to the local database."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            # Debug print to show what we're adding
            print(f"Adding log entry to database: {lane}, {plate_id}, {entry_type}, synced={synced}")
            
            # Check if synced parameter is supported in the current schema
            try:
                cursor.execute(
                    'INSERT INTO local_log (lane, plate_id, confidence, type, image_path, synced) VALUES (?, ?, ?, ?, ?, ?)',
                    (lane, plate_id, confidence, entry_type, image_path, 1 if synced else 0)
                )
            except sqlite3.OperationalError as e:
                if "no such column" in str(e).lower() and "synced" in str(e).lower():
                    # Handle older schema without synced column
                    print("Using legacy schema without synced column")
                    cursor.execute(
                        'INSERT INTO local_log (lane, plate_id, confidence, type, image_path) VALUES (?, ?, ?, ?, ?)',
                        (lane, plate_id, confidence, entry_type, image_path)
                    )
                else:
                    raise e
                    
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error adding log entry: {str(e)}")
            if conn:
                conn.rollback()
            return None
    
    def get_log_entry_count(self, only_unsynced=False):
        """Get count of log entries, optionally only unsynced ones."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if only_unsynced:
                try:
                    cursor.execute('SELECT COUNT(*) as count FROM local_log WHERE synced = 0')
                except sqlite3.OperationalError as e:
                    if "no such column" in str(e).lower() and "synced" in str(e).lower():
                        # Fall back to counting all logs if synced column doesn't exist
                        cursor.execute('SELECT COUNT(*) as count FROM local_log')
                    else:
                        raise e
            else:
                cursor.execute('SELECT COUNT(*) as count FROM local_log')
            
            result = cursor.fetchone()
            return result['count'] if result else 0
        except Exception as e:
            print(f"Error getting log count: {str(e)}")
            return 0
    
    def get_recent_logs(self, limit=100):
        """Get recent log entries."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM local_log ORDER BY timestamp DESC LIMIT ?',
                (limit,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting logs: {str(e)}")
            return []
    
    def get_unsynced_logs(self, limit=50):
        """Get log entries that need to be synced."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            print(f"Fetching up to {limit} unsynced logs from database")
            
            # First, try to query with the synced column
            try:
                cursor.execute(
                    'SELECT * FROM local_log WHERE synced = 0 ORDER BY timestamp ASC LIMIT ?',
                    (limit,)
                )
                rows = cursor.fetchall()
                if rows:
                    results = [dict(row) for row in rows]
                    print(f"Found {len(results)} unsynced logs in the database")
                    return results
                else:
                    print("No unsynced logs found in the database")
                    return []
                    
            except sqlite3.OperationalError as e:
                if "no such column" in str(e).lower() and "synced" in str(e).lower():
                    # Fall back to getting all logs if the synced column doesn't exist
                    print("Warning: 'synced' column not found in local_log table, falling back to all logs")
                    cursor.execute(
                        'SELECT * FROM local_log ORDER BY timestamp ASC LIMIT ?',
                        (limit,)
                    )
                    results = [dict(row) for row in cursor.fetchall()]
                    return results
                else:
                    print(f"Database error while querying unsynced logs: {str(e)}")
                    raise e
                
        except Exception as e:
            print(f"Error getting unsynced logs: {str(e)}")
            return []
    
    def mark_log_synced(self, log_id):
        """Mark a log entry as synced."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE local_log SET synced = 1 WHERE id = ?',
                (log_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"Error marking log as synced: {str(e)}")
            if conn:
                conn.rollback()
            return False
    
    # Parking session methods
    def start_parking_session(self, plate_id, lot_id, entry_confidence, entry_img=None):
        """Start a new parking session."""
        try:
            # First, ensure the vehicle exists
            self.add_vehicle(plate_id, self.is_blacklisted(plate_id))
            
            conn = self._get_connection()
            cursor = conn.cursor()
            entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute(
                '''INSERT INTO parking_session 
                   (plate_id, lot_id, entry_time, entry_confidence, entry_img, status)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (plate_id, lot_id, entry_time, entry_confidence, entry_img, 'pending')
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error starting parking session: {str(e)}")
            if conn:
                conn.rollback()
            return None
    
    def end_parking_session(self, plate_id, lot_id, exit_confidence, exit_img=None):
        """End an existing parking session."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            exit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Find the most recent pending session for this vehicle
            cursor.execute(
                '''SELECT id FROM parking_session 
                   WHERE plate_id = ? AND lot_id = ? AND exit_time IS NULL 
                   ORDER BY entry_time DESC LIMIT 1''',
                (plate_id, lot_id)
            )
            result = cursor.fetchone()
            
            if result:
                session_id = result['id']
                cursor.execute(
                    '''UPDATE parking_session 
                       SET exit_time = ?, exit_confidence = ?, exit_img = ?, 
                           status = 'finished', synced = 0
                       WHERE id = ?''',
                    (exit_time, exit_confidence, exit_img, session_id)
                )
                conn.commit()
                return session_id
            else:
                print(f"No open parking session found for plate {plate_id}")
                return None
                
        except Exception as e:
            print(f"Error ending parking session: {str(e)}")
            if conn:
                conn.rollback()
            return None
    
    def get_active_sessions(self, lot_id):
        """Get active parking sessions for a lot."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT * FROM parking_session 
                   WHERE lot_id = ? AND exit_time IS NULL''',
                (lot_id,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting active sessions: {str(e)}")
            return []
    
    def get_unsynced_sessions(self, limit=50):
        """Get parking sessions that need to be synced."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM parking_session WHERE synced = 0 ORDER BY entry_time ASC LIMIT ?',
                (limit,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting unsynced sessions: {str(e)}")
            return []
    
    def mark_session_synced(self, session_id, remote_id=None):
        """Mark a parking session as synced with optional remote ID."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if remote_id:
                cursor.execute(
                    'UPDATE parking_session SET synced = 1, remote_id = ? WHERE id = ?',
                    (remote_id, session_id)
                )
            else:
                cursor.execute(
                    'UPDATE parking_session SET synced = 1 WHERE id = ?',
                    (session_id,)
                )
                
            conn.commit()
            return True
        except Exception as e:
            print(f"Error marking session as synced: {str(e)}")
            if conn:
                conn.rollback()
            return False
    
    # Barrier action methods
    def add_barrier_action(self, session_id, action_type, trigger_type):
        """Record a barrier action."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            action_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute(
                '''INSERT INTO barrier_action 
                   (session_id, action_time, action_type, trigger_type)
                   VALUES (?, ?, ?, ?)''',
                (session_id, action_time, action_type, trigger_type)
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error recording barrier action: {str(e)}")
            if conn:
                conn.rollback()
            return None
    
    def get_unsynced_actions(self, limit=50):
        """Get barrier actions that need to be synced."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM barrier_action WHERE synced = 0 ORDER BY action_time ASC LIMIT ?',
                (limit,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting unsynced actions: {str(e)}")
            return []
    
    def mark_action_synced(self, action_id, remote_id=None):
        """Mark a barrier action as synced with optional remote ID."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if remote_id:
                cursor.execute(
                    'UPDATE barrier_action SET synced = 1, remote_id = ? WHERE id = ?',
                    (remote_id, action_id)
                )
            else:
                cursor.execute(
                    'UPDATE barrier_action SET synced = 1 WHERE id = ?',
                    (action_id,)
                )
                
            conn.commit()
            return True
        except Exception as e:
            print(f"Error marking action as synced: {str(e)}")
            if conn:
                conn.rollback()
            return False
    
    # Occupancy methods
    def get_lot_occupancy(self, lot_id):
        """Get current occupancy for a parking lot."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Try to get capacity from API first
            capacity = self._get_lot_capacity_from_api(lot_id)
                
            # Count active sessions
            cursor.execute(
                'SELECT COUNT(*) as occupied FROM parking_session WHERE lot_id = ? AND exit_time IS NULL',
                (lot_id,)
            )
            occupied_result = cursor.fetchone()
            occupied = occupied_result['occupied'] if occupied_result else 0
            
            # Calculate available spots and occupancy rate
            available = max(0, capacity - occupied)
            occupancy_rate = round((occupied / capacity) * 100) if capacity > 0 else 0
            
            return {
                'capacity': capacity,
                'occupied': occupied,
                'available': available,
                'occupancy_rate': occupancy_rate
            }
        except Exception as e:
            print(f"Error getting lot occupancy: {str(e)}")
            return None
    
    def _get_lot_capacity_from_api(self, lot_id):
        """Get lot capacity from API with caching and fallback to config"""
        # Check if we have a recent cached value (cache for 1 hour)
        cache_attr = f"_lot_{lot_id}_capacity_cache"
        cache_time_attr = f"_lot_{lot_id}_capacity_cache_time"
        
        current_time = time.time()
        cache_valid = (
            hasattr(self, cache_time_attr) and 
            hasattr(self, cache_attr) and
            current_time - getattr(self, cache_time_attr) < 3600  # 1 hour cache
        )
        
        if cache_valid:
            return getattr(self, cache_attr)
            
        try:
            # Import API client
            from app.controllers.api_client import ApiClient
            from app.utils.auth_manager import AuthManager
            from config import API_BASE_URL, LOT_CAPACITY
            
            # Create API client
            api_client = ApiClient(base_url=API_BASE_URL)
            auth_manager = AuthManager()
            
            # Only proceed if we have authentication
            if auth_manager.access_token:
                # Try to get lot capacity from API
                success, data = api_client.get(f'parking-lots/{lot_id}', timeout=(2.0, 3.0))
                
                if success and 'capacity' in data:
                    # Cache the result
                    setattr(self, cache_attr, data['capacity'])
                    setattr(self, cache_time_attr, current_time)
                    print(f"Retrieved lot capacity from API: {data['capacity']}")
                    return data['capacity']
            else:
                print("Not authenticated, using default lot capacity")
        except Exception as e:
            print(f"Error fetching lot capacity from API: {str(e)}")
        
        # Fallback to config value if API fails or not authenticated
        from config import LOT_CAPACITY
        return LOT_CAPACITY
    
    def save_lot_info(self, lot_id, name, capacity, location):
        """
        This method is deprecated as parking_lot table is no longer created.
        Information is now taken directly from config.
        """
        print("Warning: save_lot_info is deprecated as parking_lot table no longer exists")
        return True
    
    # Utility methods
    def get_last_sync_time(self, table_name):
        """Get the last synchronization time for a table."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT last_sync_time FROM sync_status WHERE table_name = ?', (table_name,))
            result = cursor.fetchone()
            return result['last_sync_time'] if result else 0
        except Exception as e:
            print(f"Error getting last sync time: {str(e)}")
            return 0
    
    def update_sync_time(self, table_name):
        """Update the last synchronization time for a table."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = time.time()
            cursor.execute('UPDATE sync_status SET last_sync_time = ? WHERE table_name = ?', (now, table_name))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating sync time: {str(e)}")
            if conn:
                conn.rollback()
            return False 
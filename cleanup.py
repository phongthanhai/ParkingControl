# cleanup_corrupted_logs.py
import sqlite3
import os
import sys

# Path to your database file - adjust as needed
db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'local_data.db')

def cleanup_unsynced_logs():
    print(f"Connecting to database at {db_path}")
    if not os.path.exists(db_path):
        print("Database file not found!")
        return False
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check how many unsynced logs exist
        cursor.execute("SELECT COUNT(*) FROM local_log WHERE synced = 0")
        unsynced_count = cursor.fetchone()[0]
        print(f"Found {unsynced_count} unsynced logs")
        
        # Mark all current unsynced logs as synced to fix the corruption
        cursor.execute("UPDATE local_log SET synced = 1 WHERE synced = 0")
        rows_updated = cursor.rowcount
        
        # Commit the changes
        conn.commit()
        
        print(f"Updated {rows_updated} records, marking them as synced")
        return True
        
    except Exception as e:
        print(f"Error cleaning up logs: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    cleanup_unsynced_logs()
    input("Press Enter to exit...")
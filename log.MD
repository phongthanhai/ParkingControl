QStandardPaths: wrong permissions on runtime directory /run/user/1000, 0770 instead of 0700
No unsynced logs found, no cleanup needed
AuthManager instance created
ConnectionManager initialized - Circuit CLOSED (online)
Config: consecutive_threshold=5, rate_threshold=0.8, window=60s
SimpleApiClient initialized with circuit breaker integration
Starting sync worker thread
Setting up health monitoring timer
Scheduling initial sync check with 30-second delay

=== SYNC WORKER: STARTING LOG SYNC ===
Fetching up to 20 unsynced logs from database
No unsynced logs found in the database
SYNC WORKER: No logs to sync
Sync logs: success - No logs to sync
Attempting login at URL: http://192.168.1.13:8000/api/v1/login/access-token
Clearing authentication token
Access token set: present
Token type set to: bearer
Refresh token set: present
Username set to: guard
Password set (value hidden)
Login successful. Token type: bearer
Refresh token set: present
Refresh token stored successfully for future authentication
User assigned lots: [1]
Configured lot ID: 1
SimpleApiClient initialized with circuit breaker integration
Setting up log_signal for sync service
GPIO pin 17 initialized to HIGH (relay inactive)
GPIO pin 27 initialized to HIGH (relay inactive)
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Warning: Could not locate log frame layout, creating alternate filter display
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Database stats - Total logs: 0, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
No unsynced logs found in the database
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
Connecting control_screen.log_signal to sync_service
Triggering initial sync after successful login
Initial sync scheduled in background thread
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Occupancy updated: 0.0% (0/100)

=== INITIAL SYNC AFTER LOGIN STARTED ===
UI blocked for 2481 ms
Updating blacklist cache - current entries: 0

==== SYNC OPERATION STARTED (startup) ====
Triggered sync_now for entity_type: all
Sending blacklist API request...
Database stats - Total logs: 0, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
No unsynced logs found in the database
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
Nothing to sync
Error fetching logs: []
Database stats - Total logs: 0, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
No unsynced logs found in the database
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
Blacklist API response - success: True, data: [{'plate_id': '99a99999', 'is_blacklisted': True, 'created_at': '2025-05-13T11:23:01.515455'}, {'plate_id': '76a07676', 'is_blacklisted': True, 'created_at': '2025-05-13T20:39:18.219271'}]
Adding blacklisted plate: 99A99999
Adding blacklisted plate: 76A07676
Updating blacklist: old count=0, new count=2
Blacklist updated: 2 vehicles
Occupancy updated: 0.0% (0/100)
UI blocked for 1109 ms
Health check result: PASS
UI blocked for 1009 ms
UI blocked for 962 ms
UI blocked for 1000 ms
UI blocked for 999 ms
UI blocked for 1007 ms
Health check result: PASS
UI blocked for 991 ms
UI blocked for 1000 ms
UI blocked for 993 ms
UI blocked for 999 ms
UI blocked for 998 ms
Health check result: PASS
UI blocked for 1001 ms
UI blocked for 997 ms
UI blocked for 999 ms
UI blocked for 999 ms
UI blocked for 1003 ms
Health check result: PASS
UI blocked for 996 ms

=== SYNC WORKER: STARTING LOG SYNC ===
Fetching up to 20 unsynced logs from database
No unsynced logs found in the database
SYNC WORKER: No logs to sync
Sync logs: success - No logs to sync

=== CHECKING FOR INITIAL SYNC ===
API available, checking for unsynced items...
UI blocked for 1000 ms
Database stats - Total logs: 0, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
No unsynced logs found in the database
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
No items to sync at startup
Database stats - Total logs: 0, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
No unsynced logs found in the database
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 1043 ms
Health check result: PASS
UI blocked for 955 ms
UI blocked for 1000 ms
UI blocked for 999 ms
UI blocked for 1002 ms
UI blocked for 996 ms
Health check result: PASS
UI blocked for 1000 ms
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 998 ms
UI blocked for 1003 ms
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check connection error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
Circuit staying CLOSED: consecutive=1/5, rate=1/12 attempts
Health check result: FAIL
UI blocked for 996 ms
UI blocked for 1003 ms
UI blocked for 996 ms
UI blocked for 999 ms
UI blocked for 1001 ms
Health check result: PASS
UI blocked for 998 ms
UI blocked for 1000 ms
UI blocked for 996 ms
UI blocked for 998 ms
UI blocked for 999 ms
Health check result: PASS
UI blocked for 1000 ms
UI blocked for 999 ms
UI blocked for 1002 ms
UI blocked for 996 ms
UI blocked for 996 ms
Health check result: PASS
UI blocked for 997 ms

=== SYNC WORKER: STARTING LOG SYNC ===
Fetching up to 20 unsynced logs from database
No unsynced logs found in the database
SYNC WORKER: No logs to sync
Sync logs: success - No logs to sync
UI blocked for 997 ms
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 1002 ms
Health check result: PASS
UI blocked for 997 ms
UI blocked for 999 ms
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 999 ms
Health check result: PASS
Occupancy updated: 0.0% (0/100)
UI blocked for 996 ms
UI blocked for 997 ms
UI blocked for 1010 ms
Starting main application shutdown...
Database check timer stopped
DEBUG: About to check for unsynced data...
Database stats - Total logs: 0, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
No unsynced logs found in the database
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
DEBUG: Found 0 items that need sync before exit
Error checking for unsynced data: 'SyncService' object has no attribute 'api_available'
Closing control screen and its threads...
Starting application shutdown and thread cleanup...
UI monitor timer stopped
Health check timer stopped
Stopping 0 API worker threads...
All API workers stopped successfully
Stopping DB worker thread...
Stopping DB worker thread...
Error in DB worker thread: 'NoneType' object has no attribute 'get'
DB worker thread stopped
DB worker thread stopped
Stopping entry camera worker...
Stopping entry lane worker thread...
Error cleaning up recognizer in entry lane: disconnect() failed between 'result_signal' and all its connections
Waiting for entry lane thread to finish...
entry lane worker thread stopped
Stopping exit camera worker...
Stopping exit lane worker thread...
Error cleaning up recognizer in exit lane: disconnect() failed between 'result_signal' and all its connections
Waiting for exit lane thread to finish...
exit lane worker thread stopped
All camera workers stopped successfully
Application shutdown complete
Control screen threads cleaned up
Cleared temporary blacklist logs
Stopping sync service...
Stopping sync service...
Stopping sync worker thread...
WARNING: Sync worker thread did not stop gracefully, forcing termination
Sync worker thread stopped
Sync service stopped
Closing database connection...
Database connection closed
Application shutdown complete

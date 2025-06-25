QStandardPaths: wrong permissions on runtime directory /run/user/1000, 0770 instead of 0700
Found 1 unsynced logs, checking for potential corruption...
All 1 unsynced logs are recent (within 24 hours), not cleaning up
AuthManager instance created
ConnectionManager initialized - Circuit CLOSED (online)
Config: consecutive_threshold=5, rate_threshold=0.8, window=60s
SimpleApiClient initialized with circuit breaker integration
Setting up health monitoring timer
SyncService initialized - sync only on demand
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
Database stats - Total logs: 3, Unsynced logs: 1
Fetching up to 1000 unsynced logs from database
Found 1 unsynced logs in the database
Found 1 unsynced logs in the database
  Log 1: ID=3, Type=manual, Plate=30g69999
After filtering for auto/manual entries: 1 logs need to be synced
Connecting control_screen.log_signal to sync_service
Triggering initial sync after successful login
=== INITIAL SYNC AFTER LOGIN STARTED ===
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
Updating blacklist cache - current entries: 0
Sending blacklist API request...
Blacklist API response - success: True, data: [{'plate_id': '99a99999', 'is_blacklisted': True, 'created_at': '2025-05-13T11:23:01.515455'}, {'plate_id': '76a07676', 'is_blacklisted': True, 'created_at': '2025-05-13T20:39:18.219271'}]
Adding blacklisted plate: 99A99999
Adding blacklisted plate: 76A07676
Updating blacklist: old count=0, new count=2
Blacklist updated: 2 vehicles
UI blocked for 2150 ms
Occupancy updated: 0.0% (0/100)

==== SYNC OPERATION STARTED (startup) ====
Triggered sync_now for entity_type: all
Database stats - Total logs: 3, Unsynced logs: 1
Fetching up to 1000 unsynced logs from database
Found 1 unsynced logs in the database
Found 1 unsynced logs in the database
  Log 1: ID=3, Type=manual, Plate=30g69999
After filtering for auto/manual entries: 1 logs need to be synced
Found 1 items to sync
Sync requested for entity_type: logs
Updating blacklist cache - current entries: 2
Sending blacklist API request...
Blacklist API response - success: True, data: [{'plate_id': '99a99999', 'is_blacklisted': True, 'created_at': '2025-05-13T11:23:01.515455'}, {'plate_id': '76a07676', 'is_blacklisted': True, 'created_at': '2025-05-13T20:39:18.219271'}]
Adding blacklisted plate: 99A99999
Adding blacklisted plate: 76A07676
Updating blacklist: old count=2, new count=2
Blacklist updated: 2 vehicles
Health check result: PASS
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check connection error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
Circuit staying CLOSED: consecutive=1/5, rate=1/8 attempts
Health check result: FAIL
Health check result: PASS
Health check result: PASS
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check connection error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
Circuit staying CLOSED: consecutive=1/5, rate=2/11 attempts
Health check result: FAIL
Health check result: PASS
Starting main application shutdown...
Database check timer stopped
DEBUG: About to check for unsynced data...
Database stats - Total logs: 3, Unsynced logs: 1
Fetching up to 1000 unsynced logs from database
Found 1 unsynced logs in the database
Found 1 unsynced logs in the database
  Log 1: ID=3, Type=manual, Plate=30g69999
After filtering for auto/manual entries: 1 logs need to be synced
DEBUG: Found 1 items that need sync before exit
DEBUG: Will show exit dialog for 1 items
DEBUG: Showing exit sync dialog
DEBUG: Processing events to display dialog
DEBUG: Starting final exit sync operation

==== SYNC OPERATION STARTED (shutdown) ====
Triggered sync_now for entity_type: all
Database stats - Total logs: 3, Unsynced logs: 1
Fetching up to 1000 unsynced logs from database
Found 1 unsynced logs in the database
Found 1 unsynced logs in the database
  Log 1: ID=3, Type=manual, Plate=30g69999
After filtering for auto/manual entries: 1 logs need to be synced
Found 1 items to sync
Sync requested for entity_type: logs
DEBUG: About to execute sync dialog
Health check result: PASS
Health check result: PASS
DEBUG: Dialog finished with result: 0 (took 10.7s)
User forced exit during sync
Closing control screen and its threads...
Starting application shutdown and thread cleanup...
Stopping DB worker thread...
Stopping DB worker thread...
Error in DB worker thread: 'NoneType' object has no attribute 'get'
DB worker thread stopped
DB worker thread stopped
Stopping entry camera worker...
Stopping entry lane worker thread...
Waiting for entry lane thread to finish...
entry lane worker thread stopped
Stopping exit camera worker...
Stopping exit lane worker thread...
Waiting for exit lane thread to finish...
exit lane worker thread stopped
All camera workers stopped successfully
Application shutdown complete
Control screen threads cleaned up
Cleared temporary blacklist logs
Stopping sync service...
Stopping sync service...
Sync service stopped
Stopping sync service...
Closing database connection...
Database connection closed
Application shutdown complete
UI blocked for 2010 ms
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check connection error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
Circuit staying CLOSED: consecutive=1/5, rate=3/16 attempts
Health check result: FAIL

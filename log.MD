QStandardPaths: wrong permissions on runtime directory /run/user/1000, 0770 instead of 0700
No unsynced logs found, no cleanup needed
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
Database stats - Total logs: 2, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
No unsynced logs found in the database
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
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
UI blocked for 2073 ms
Occupancy updated: 0.0% (0/100)

==== SYNC OPERATION STARTED (startup) ====
Triggered sync_now for entity_type: all
Database stats - Total logs: 2, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
No unsynced logs found in the database
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
Nothing to sync
Database stats - Total logs: 2, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
No unsynced logs found in the database
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
Updating blacklist cache - current entries: 2
Sending blacklist API request...
Blacklist API response - success: True, data: [{'plate_id': '99a99999', 'is_blacklisted': True, 'created_at': '2025-05-13T11:23:01.515455'}, {'plate_id': '76a07676', 'is_blacklisted': True, 'created_at': '2025-05-13T20:39:18.219271'}]
Adding blacklisted plate: 99A99999
Adding blacklisted plate: 76A07676
Updating blacklist: old count=2, new count=2
Blacklist updated: 2 vehicles
Health check result: PASS
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check read timeout
Circuit staying CLOSED: consecutive=1/5, rate=1/7 attempts
Health check result: FAIL
UI blocked for 1211 ms
Circuit failure recorded: consecutive=2, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f94281c50>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Circuit staying CLOSED: consecutive=2/5, rate=2/8 attempts
Health check result: FAIL
Circuit failure recorded: consecutive=3, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f942829d0>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Circuit staying CLOSED: consecutive=3/5, rate=3/9 attempts
Health check result: FAIL
Circuit failure recorded: consecutive=4, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f94283850>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Circuit staying CLOSED: consecutive=4/5, rate=4/10 attempts
Circuit failure recorded: consecutive=5, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f94391e50>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Consecutive failure threshold reached: 5/5
Circuit transition: closed -> OPEN (offline)
  Consecutive failures: 5
  Recent failures: 5 in 60s
  Recent failure types: ['health-check', 'health-check', 'health-check']
UI updated: API status set to DISCONNECTED
Health check result: FAIL
PlateRecognizer API Error: PlateRecognizer error: HTTPSConnectionPool(host='api.platerecognizer.com', port=443): Max retries exceeded with url: /v1/plate-reader (Caused by NameResolutionError("<urllib3.connection.HTTPSConnection object at 0x7f94282150>: Failed to resolve 'api.platerecognizer.com' ([Errno -3] Temporary failure in name resolution)"))
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Health check skipped - circuit breaker OPEN
Health check result: FAIL
Health check skipped - circuit breaker OPEN
Health check result: FAIL
Unknown property transition
Vehicle skipped in entry lane - only shown in UI, not stored in database
Skipping vehicle in entry lane
Unknown property transition
Vehicle skipped in exit lane - only shown in UI, not stored in database
Skipping vehicle in exit lane
Health check skipped - circuit breaker OPEN
Health check result: FAIL
Health check skipped - circuit breaker OPEN
Health check result: FAIL
PlateRecognizer API Error: PlateRecognizer error: HTTPSConnectionPool(host='api.platerecognizer.com', port=443): Max retries exceeded with url: /v1/plate-reader (Caused by NameResolutionError("<urllib3.connection.HTTPSConnection object at 0x7f94290610>: Failed to resolve 'api.platerecognizer.com' ([Errno -3] Temporary failure in name resolution)"))
Unknown property transition
Unknown property transition
Health check skipped - circuit breaker OPEN
Health check result: FAIL
Health check skipped - circuit breaker OPEN
Health check skipped - circuit breaker OPEN
Health check result: FAIL
Circuit transition: open -> HALF_OPEN (testing)
Circuit failure recorded: consecutive=6, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f94291210>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Consecutive failure threshold reached: 6/5
HALF_OPEN test failed (health-check), returning to OPEN
Circuit transition: half_open -> OPEN (offline)
  Consecutive failures: 6
  Recent failures: 6 in 60s
  Recent failure types: ['health-check', 'health-check', 'health-check']
UI updated: API status set to DISCONNECTED
Health check result: FAIL
Health check skipped - circuit breaker OPEN
Health check result: FAIL
Unknown property transition
GPIO 17 set LOW for entry lane (relay ACTIVE)
Auto-close timer started for entry lane: 10 seconds
Log entry created: {'lane': 'entry', 'plate': '30g69999', 'confidence': 1.0, 'timestamp': 1750835648.847606, 'formatted_time': '2025-06-25 14:14:08.847606', 'type': 'manual', 'processed': False}
Using offline storage for entry lane, manual type
Error saving image: 'DBWorker' object has no attribute 'update_operation'
Queued log entry operation log_entry_1750835648.854636_548332217536 for entry lane
Received log entry for sync: 30g69999 - manual
Entry for 30g69999 already stored in database, only updating sync service
Database stats - Total logs: 2, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
Adding log entry to database: entry, 30g69999, manual, synced=False, timestamp=1750835648.854616
No unsynced logs found in the database
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
Database operation log_entry_1750835648.854636_548332217536 completed successfully
Health check skipped - circuit breaker OPEN
Health check result: FAIL
Health check skipped - circuit breaker OPEN
Health check result: FAIL
GPIO 17 set HIGH for entry lane (relay INACTIVE)
Unknown property transition
Unknown property transition
entry lane UI reset - resuming detection
Health check skipped - circuit breaker OPEN
Health check result: FAIL
Health check skipped - circuit breaker OPEN
Health check skipped - circuit breaker OPEN
Health check result: FAIL
Circuit transition: open -> HALF_OPEN (testing)
Circuit HALF_OPEN: Success 1/2 (health-check)
Health check result: PASS
Circuit HALF_OPEN: Success 2/2 (health-check)
Circuit transition: half_open -> CLOSED (online)
UI updated: API status set to CONNECTED
Health check result: PASS
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
qt.qpa.wayland: Wayland does not support QWindow::requestActivate()
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
Health check result: PASS
Health check result: PASS
Health check result: PASS
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check connection error: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
Circuit staying CLOSED: consecutive=1/5, rate=1/10 attempts
Health check result: FAIL
qt.qpa.wayland: Wayland does not support QWindow::requestActivate()
DEBUG: Dialog finished with result: 0
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
Health check result: PASS
UI blocked for 1536 ms

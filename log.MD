QStandardPaths: wrong permissions on runtime directory /run/user/1000, 0770 instead of 0700
No unsynced logs found, no cleanup needed
AuthManager instance created
ConnectionManager initialized - Circuit CLOSED (online)
Config: consecutive_threshold=5, rate_threshold=0.8, window=60s
SimpleApiClient initialized with circuit breaker integration
Starting sync worker thread
Setting up health monitoring timer

=== SYNC WORKER: STARTING LOG SYNC ===
Fetching up to 20 unsynced logs from database
Scheduling initial sync check with 30-second delay
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
Backend API call exception: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
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
Detected possible connection failure: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Failed to execute occupancy API call: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Health check error: 'ControlScreen' object has no attribute 'last_api_check_time'

=== INITIAL SYNC AFTER LOGIN STARTED ===

==== SYNC OPERATION STARTED (startup) ====
Triggered sync_now for entity_type: all
Database stats - Total logs: 0, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
UI blocked for 4124 ms
No unsynced logs found in the database
Updating blacklist cache - current entries: 0
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
Nothing to sync
Sending blacklist API request...
Backend API call exception: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Error fetching logs: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Backend API call exception: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Database stats - Total logs: 0, Unsynced logs: 0
Fetching up to 1000 unsynced logs from database
No unsynced logs found in the database
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
Detected possible connection failure: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Failed to execute blacklist API call: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Detected possible connection failure: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Failed to execute occupancy API call: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Health check error: 'ControlScreen' object has no attribute 'last_api_check_time'
Health check error: 'ControlScreen' object has no attribute 'last_api_check_time'
Health check result: PASS
UI blocked for 950 ms
UI blocked for 950 ms
UI blocked for 981 ms
UI blocked for 945 ms
UI blocked for 999 ms
Health check result: PASS
UI blocked for 999 ms
UI blocked for 999 ms
UI blocked for 1030 ms
UI blocked for 1022 ms
UI blocked for 944 ms
Health check result: PASS
UI blocked for 998 ms
UI blocked for 1003 ms
UI blocked for 997 ms
UI blocked for 998 ms
Unknown property transition
UI blocked for 996 ms
Error fetching logs: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Backend API call exception: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Detected possible connection failure: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Failed to execute occupancy API call: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Health check error: 'ControlScreen' object has no attribute 'last_api_check_time'
Health check result: PASS
UI blocked for 1057 ms
UI blocked for 944 ms
UI blocked for 1000 ms
UI blocked for 997 ms

=== CHECKING FOR INITIAL SYNC ===
API available, checking for unsynced items...

=== SYNC WORKER: STARTING LOG SYNC ===
Fetching up to 20 unsynced logs from database
No unsynced logs found in the database
SYNC WORKER: No logs to sync
Sync logs: success - No logs to sync
UI blocked for 999 ms
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
Health check result: PASS
UI blocked for 1002 ms
UI blocked for 999 ms
UI blocked for 996 ms
UI blocked for 1001 ms
UI blocked for 999 ms
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check connection error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
Circuit staying CLOSED: consecutive=1/5, rate=1/7 attempts
Health check result: FAIL
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 999 ms
UI blocked for 999 ms
UI blocked for 999 ms
Health check result: PASS
UI blocked for 1000 ms
UI blocked for 999 ms
UI blocked for 999 ms
UI blocked for 999 ms
UI blocked for 1000 ms
Health check result: PASS
UI blocked for 1000 ms
UI blocked for 998 ms
UI blocked for 1000 ms
UI blocked for 999 ms
UI blocked for 1000 ms
Health check result: PASS
UI blocked for 1001 ms
UI blocked for 997 ms
UI blocked for 999 ms
UI blocked for 999 ms
UI blocked for 1001 ms
Health check result: PASS
UI blocked for 998 ms
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 997 ms

=== SYNC WORKER: STARTING LOG SYNC ===
Fetching up to 20 unsynced logs from database
No unsynced logs found in the database
SYNC WORKER: No logs to sync
Sync logs: success - No logs to sync
UI blocked for 999 ms
Health check result: PASS
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 998 ms
Backend API call exception: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Health check result: PASS
Detected possible connection failure: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Failed to execute occupancy API call: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Health check error: 'ControlScreen' object has no attribute 'last_api_check_time'
UI blocked for 1000 ms
UI blocked for 998 ms
UI blocked for 1002 ms
UI blocked for 997 ms
UI blocked for 999 ms
Health check result: PASS
UI blocked for 997 ms
UI blocked for 999 ms
UI blocked for 998 ms
UI blocked for 999 ms
UI blocked for 999 ms
Health check result: PASS
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 998 ms
UI blocked for 999 ms
UI blocked for 1000 ms
Health check result: PASS
UI blocked for 997 ms
UI blocked for 1003 ms
UI blocked for 997 ms
UI blocked for 996 ms
UI blocked for 999 ms
Health check result: PASS
UI blocked for 1000 ms
UI blocked for 998 ms
UI blocked for 999 ms
UI blocked for 1000 ms

=== SYNC WORKER: STARTING LOG SYNC ===
Fetching up to 20 unsynced logs from database
No unsynced logs found in the database
SYNC WORKER: No logs to sync
Sync logs: success - No logs to sync
UI blocked for 999 ms
Health check result: PASS
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 998 ms
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check connection error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
Circuit staying CLOSED: consecutive=1/5, rate=1/14 attempts
Health check result: FAIL
UI blocked for 998 ms
UI blocked for 1000 ms
UI blocked for 1002 ms
UI blocked for 996 ms
UI blocked for 1000 ms
Health check result: PASS
UI blocked for 999 ms
UI blocked for 997 ms
UI blocked for 999 ms
UI blocked for 1008 ms
UI blocked for 993 ms
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Read timed out.
Circuit staying CLOSED: consecutive=1/5, rate=2/14 attempts
Health check result: FAIL
UI blocked for 2580 ms
UI blocked for 946 ms
UI blocked for 964 ms
Circuit failure recorded: consecutive=2, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f771b06d0>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Circuit staying CLOSED: consecutive=2/5, rate=3/15 attempts
Health check result: FAIL
UI blocked for 1011 ms
UI blocked for 991 ms
UI blocked for 1001 ms
UI blocked for 992 ms
UI blocked for 999 ms
Circuit failure recorded: consecutive=3, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f771b1310>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Circuit staying CLOSED: consecutive=3/5, rate=4/15 attempts
Health check result: FAIL
UI blocked for 1006 ms
UI blocked for 989 ms
UI blocked for 1000 ms
UI blocked for 999 ms
Circuit failure recorded: consecutive=4, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f771b0290>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Circuit staying CLOSED: consecutive=4/5, rate=5/15 attempts
UI blocked for 1012 ms

=== SYNC WORKER: STARTING LOG SYNC ===
Fetching up to 20 unsynced logs from database
No unsynced logs found in the database
SYNC WORKER: No logs to sync
Sync logs: success - No logs to sync
Circuit failure recorded: consecutive=5, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f771b2c90>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Consecutive failure threshold reached: 5/5
Circuit transition: closed -> OPEN (offline)
  Consecutive failures: 5
  Recent failures: 6 in 60s
  Recent failure types: ['health-check', 'health-check', 'health-check']
Connection transition: closed -> open
UI updated: API status set to DISCONNECTED
UI blocked for 1005 ms
Health check result: FAIL
UI blocked for 977 ms
UI blocked for 998 ms
UI blocked for 998 ms
UI blocked for 1000 ms
Backend API call exception: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Health check skipped - circuit breaker OPEN
Health check result: FAIL
UI blocked for 1014 ms
Detected possible connection failure: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Failed to execute occupancy API call: SimpleApiClient.get() got an unexpected keyword argument 'timeout'
Health check error: 'ControlScreen' object has no attribute 'last_api_check_time'
UI blocked for 985 ms
UI blocked for 999 ms
UI blocked for 998 ms
UI blocked for 997 ms
Health check skipped - circuit breaker OPEN
Health check result: FAIL
UI blocked for 1003 ms
UI blocked for 997 ms
UI blocked for 999 ms
UI blocked for 993 ms
UI blocked for 998 ms
Health check skipped - circuit breaker OPEN
Health check result: FAIL
UI blocked for 1002 ms
UI blocked for 999 ms
UI blocked for 996 ms
UI blocked for 997 ms
UI blocked for 998 ms
Health check skipped - circuit breaker OPEN
Health check result: FAIL
UI blocked for 1000 ms
UI blocked for 1002 ms
UI blocked for 998 ms
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

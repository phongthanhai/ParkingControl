QStandardPaths: wrong permissions on runtime directory /run/user/1000, 0770 instead of 0700
No unsynced logs found, no cleanup needed
AuthManager instance created
ConnectionManager initialized - Circuit CLOSED (online)
Config: consecutive_threshold=5, rate_threshold=0.8, window=60s
SimpleApiClient initialized with circuit breaker integration
Starting sync worker thread
Setting up health monitoring timer
SyncService initialized - sync only on demand
Attempting login at URL: http://192.168.1.13:8000/api/v1/login/access-token
Clearing authentication token
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
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Unknown property transition
Occupancy updated: 0.0% (0/100)
UI blocked for 2496 ms
Updating blacklist cache - current entries: 0
Sending blacklist API request...
Blacklist API response - success: True, data: [{'plate_id': '99a99999', 'is_blacklisted': True, 'created_at': '2025-05-13T11:23:01.515455'}, {'plate_id': '76a07676', 'is_blacklisted': True, 'created_at': '2025-05-13T20:39:18.219271'}]
Adding blacklisted plate: 99A99999
Adding blacklisted plate: 76A07676
Updating blacklist: old count=0, new count=2
Blacklist updated: 2 vehicles
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
UI blocked for 971 ms
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check read timeout
Circuit staying CLOSED: consecutive=1/5, rate=1/5 attempts
Health check result: FAIL
UI blocked for 3013 ms
UI blocked for 963 ms
UI blocked for 999 ms
Circuit failure recorded: consecutive=2, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7fa5eaaed0>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Circuit staying CLOSED: consecutive=2/5, rate=2/6 attempts
Health check result: FAIL
UI blocked for 1014 ms
UI blocked for 987 ms
UI blocked for 997 ms
UI blocked for 999 ms
UI blocked for 999 ms
Circuit failure recorded: consecutive=3, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7fa5eab9d0>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Circuit staying CLOSED: consecutive=3/5, rate=3/7 attempts
Health check result: FAIL
UI blocked for 1008 ms
Circuit failure recorded: consecutive=4, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7fa5ea72d0>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Circuit staying CLOSED: consecutive=4/5, rate=4/8 attempts
UI blocked for 1006 ms
Error in entry lane: API Error: Connection error: HTTPSConnectionPool(host='api.platerecognizer.com', port=443): Max retries exceeded with url: /v1/plate-reader (Caused by NameResolutionError("<urllib3.connection.HTTPSConnection object at 0x7fa5ebcb90>: Failed to resolve 'api.platerecognizer.com' ([Errno -3] Temporary failure in name resolution)"))
Unknown property transition
Unknown property transition
UI blocked for 984 ms
UI blocked for 1000 ms
UI blocked for 999 ms
Circuit failure recorded: consecutive=5, operation=health-check, error=Health check connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7fa5ebd810>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Consecutive failure threshold reached: 5/5
Circuit transition: closed -> OPEN (offline)
  Consecutive failures: 5
  Recent failures: 5 in 60s
  Recent failure types: ['health-check', 'health-check', 'health-check']
Connection transition: closed -> open
UI updated: API status set to DISCONNECTED
UI blocked for 1009 ms
Health check result: FAIL
Stopping entry lane worker thread...
Error cleaning up recognizer in entry lane: disconnect() failed between 'result_signal' and all its connections
entry lane worker thread stopped
UI blocked for 1032 ms
UI blocked for 915 ms
UI blocked for 753 ms
UI blocked for 1000 ms
Health check skipped - circuit breaker OPEN
Health check result: FAIL
UI blocked for 999 ms
UI blocked for 999 ms
UI blocked for 998 ms
UI blocked for 1102 ms
UI blocked for 893 ms
Health check skipped - circuit breaker OPEN
Health check result: FAIL
UI blocked for 1001 ms
UI blocked for 999 ms
UI blocked for 1003 ms
UI blocked for 994 ms
UI blocked for 1000 ms
Health check skipped - circuit breaker OPEN
Health check result: FAIL
UI blocked for 1000 ms
UI blocked for 999 ms
UI blocked for 999 ms
UI blocked for 996 ms
UI blocked for 1000 ms
Health check skipped - circuit breaker OPEN
Health check result: FAIL
UI blocked for 999 ms
UI blocked for 999 ms
UI blocked for 1000 ms
UI blocked for 1002 ms
UI blocked for 997 ms
Health check skipped - circuit breaker OPEN
Health check result: FAIL
UI blocked for 1001 ms
Health check skipped - circuit breaker OPEN
UI blocked for 1005 ms
^CTraceback (most recent call last):
  File "/home/raspberrypi/Documents/ParkingControl/app/ui/control_screen.py", line 577, in _handle_detection
    def _handle_detection(self, lane, frame, text, confidence, valid):

KeyboardInterrupt
Aborted


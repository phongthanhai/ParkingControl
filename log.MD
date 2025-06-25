QStandardPaths: wrong permissions on runtime directory /run/user/1000, 0770 instead of 0700
No unsynced logs found, no cleanup needed
AuthManager instance created
ConnectionManager initialized - Circuit CLOSED (online)
Config: consecutive_threshold=3, rate_threshold=0.8, window=60s
SimpleApiClient initialized with circuit breaker integration
Sync worker thread started
Setting up health monitoring timer
SyncService initialized - auto-sync enabled on connection restore
Access token set: present
Token type set to: bearer
Refresh token set: present
Username set to: guard
Password set (value hidden)
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
API is online - performing initial smart data refresh...
📱 Loaded 2 blacklist entries from cache
📱 Loaded 5 history records from cache
🔄 Initial smart data refresh...
📊 Fetching occupancy data...
🚫 Fetching blacklist data...
📋 Fetching vehicle history (limit: 50)...
Fetching up to 1000 unsynced logs from database
No unsynced logs found in the database
Database query returned 0 unsynced logs
No unsynced logs found in the database
After filtering for auto/manual entries: 0 logs need to be synced
Connecting control_screen.log_signal to sync_service
Control screen ready - auto-sync enabled
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
Occupancy updated: 1.0% (1/100)
Occupancy updated: 1.0% (1/100)
✅ Smart occupancy updated at 18:23:09
✅ Smart blacklist updated at 18:23:09: 2 entries
💾 Blacklist cached locally: 2 entries
✅ Smart history updated at 18:23:09: 5 records
💾 History cached locally: 5 records
Updating blacklist cache - current entries: 2
Sending blacklist API request...
UI blocked for 2280 ms
Blacklist API response - success: True, data: [{'plate_id': '99a99999', 'is_blacklisted': True, 'created_at': '2025-05-13T11:23:01.515455'}, {'plate_id': '76a07676', 'is_blacklisted': True, 'created_at': '2025-05-13T20:39:18.219271'}]
Adding blacklisted plate: 99A99999
Adding blacklisted plate: 76A07676
Updating blacklist: old count=2, new count=2
Blacklist updated: 2 vehicles
🔄 Initial smart data refresh...
📊 Fetching occupancy data...
🚫 Fetching blacklist data...
📋 Fetching vehicle history (limit: 50)...
Occupancy updated: 1.0% (1/100)
✅ Smart occupancy updated at 18:23:09
✅ Smart blacklist updated at 18:23:09: 2 entries
💾 Blacklist cached locally: 2 entries
✅ Smart history updated at 18:23:10: 5 records
💾 History cached locally: 5 records
🔍 OCR Request URL: https://api.platerecognizer.com/v1/plate-reader/
🔑 API Key present: Yes
📸 Image size: (114, 296, 3)
📡 Response status: 201
📋 Response content: {"processing_time":200.514,"results":[],"filename":"1123_axwIf_image.jpg","version":1,"camera_id":null,"timestamp":"2025-06-25T11:23:30.417602Z","image_width":296,"image_height":114}...
❌ No plate detected in image
OCR Service Error: No plate detected
Unknown property transition
Unknown property transition
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check read timeout
Circuit staying CLOSED: consecutive=1/3, rate=1/25 attempts
UI blocked for 1205 ms
Unknown property transition
Unknown property transition
GPIO 27 set LOW for exit lane (relay ACTIVE)
Auto-close timer started for exit lane: 10 seconds
Log entry created: {'lane': 'exit', 'plate': '51g99999', 'confidence': 1.0, 'timestamp': 1750850626.963282, 'formatted_time': '2025-06-25 18:23:46.963282', 'type': 'manual', 'processed': False}
🚗 Vehicle event: exit - 51g99999
🔄 Triggering smart data refresh...
📊 Fetching occupancy data...
🚫 Fetching blacklist data...
📋 Fetching vehicle history (limit: 50)...
✅ Smart data refresh triggered by vehicle event
Making guard-control API call for exit lane, manual type
Guard-control proceeding - circuit breaker allows operation
Circuit failure recorded: consecutive=2, operation=guard-control, error=Guard-control error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/guard-control/ (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f6cec5c90>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Circuit staying CLOSED: consecutive=2/3, rate=2/26 attempts
Guard-control API failed: Guard-control error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/guard-control/ (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f6cec5c90>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Using offline storage for exit lane, manual type
Image saved locally: /home/raspberrypi/Documents/ParkingControl/offline_images/exit/20250625_182347_51g99999_c70fa7bd.png
Queued log entry operation log_entry_1750850627.012896_547674051776 for exit lane
Adding log entry to database: exit, 51g99999, manual, synced=False, timestamp=1750850627.000881
Received log entry for sync: 51g99999 - manual
Entry for 51g99999 already stored in database, only updating sync service
Fetching up to 1000 unsynced logs from database
Found 1 unsynced logs in the database
Database query returned 1 unsynced logs
  Log 1: ID=4, Type=manual, Plate=51g99999, Synced=0
After filtering for auto/manual entries: 1 logs need to be synced
Circuit failure recorded: consecutive=3, operation=api-call, error=Connection error: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/lot-occupancy/1 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f6cec7250>: Failed to establish a new connection: [Errno 101] Network is unreachable'))
Consecutive failure threshold reached: 3/3
Circuit transition: closed -> OPEN (offline)
  Consecutive failures: 3
  Recent failures: 3 in 60s
  Recent failure types: ['health-check', 'guard-control', 'api-call']
Connection lost - will auto-sync when restored
UI updated: API status set to DISCONNECTED
^CTraceback (most recent call last):
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/urllib3/connection.py", line 198, in _new_conn
    sock = connection.create_connection(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/urllib3/util/connection.py", line 85, in create_connection
    raise err
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/urllib3/util/connection.py", line 73, in create_connection
    sock.connect(sa)
OSError: [Errno 101] Network is unreachable

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/urllib3/connectionpool.py", line 787, in urlopen
    response = self._make_request(
               ^^^^^^^^^^^^^^^^^^^
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/urllib3/connectionpool.py", line 493, in _make_request
    conn.request(
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/urllib3/connection.py", line 445, in request
    self.endheaders()
  File "/usr/lib/python3.11/http/client.py", line 1277, in endheaders
    self._send_output(message_body, encode_chunked=encode_chunked)
  File "/usr/lib/python3.11/http/client.py", line 1037, in _send_output
    self.send(msg)
  File "/usr/lib/python3.11/http/client.py", line 975, in send
    self.connect()
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/urllib3/connection.py", line 276, in connect
    self.sock = self._new_conn()
                ^^^^^^^^^^^^^^^^
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/urllib3/connection.py", line 213, in _new_conn
    raise NewConnectionError(
urllib3.exceptions.NewConnectionError: <urllib3.connection.HTTPConnection object at 0x7f6cec7250>: Failed to establish a new connection: [Errno 101] Network is unreachable

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/requests/adapters.py", line 667, in send
    resp = conn.urlopen(
           ^^^^^^^^^^^^^
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/urllib3/connectionpool.py", line 841, in urlopen
    retries = retries.increment(
              ^^^^^^^^^^^^^^^^^^
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/urllib3/util/retry.py", line 519, in increment
    raise MaxRetryError(_pool, url, reason) from reason  # type: ignore[arg-type]
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
urllib3.exceptions.MaxRetryError: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/lot-occupancy/1 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f6cec7250>: Failed to establish a new connection: [Errno 101] Network is unreachable'))

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/raspberrypi/Documents/ParkingControl/app/controllers/simple_api_client.py", line 252, in get
    response = self.session.get(
               ^^^^^^^^^^^^^^^^^
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/requests/sessions.py", line 602, in get
    return self.request("GET", url, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/requests/sessions.py", line 589, in request
    resp = self.send(prep, **send_kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/requests/sessions.py", line 703, in send
    r = adapter.send(request, **kwargs)
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/raspberrypi/Documents/ParkingControl/venv/lib/python3.11/site-packages/requests/adapters.py", line 700, in send
    raise ConnectionError(e, request=request)
requests.exceptions.ConnectionError: HTTPConnectionPool(host='192.168.1.13', port=8000): Max retries exceeded with url: /api/v1/services/lot-occupancy/1 (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f6cec7250>: Failed to establish a new connection: [Errno 101] Network is unreachable'))

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/raspberrypi/Documents/ParkingControl/app/controllers/simple_api_client.py", line 499, in _perform_request
    success, result = self.get(endpoint, params)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/raspberrypi/Documents/ParkingControl/app/controllers/simple_api_client.py", line 244, in get
    if not self.connection_manager.should_attempt_operation("api-call"):
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/raspberrypi/Documents/ParkingControl/app/utils/connection_state.py", line 109, in should_attempt_operation
    with self.state_lock:
KeyboardInterrupt
Aborted

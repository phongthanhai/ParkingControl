QStandardPaths: wrong permissions on runtime directory /run/user/1000, 0770 instead of 0700
No unsynced logs found, no cleanup needed
AuthManager instance created
ConnectionManager initialized - Circuit CLOSED (online)
Config: consecutive_threshold=5, rate_threshold=0.8, window=60s
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
🔄 Initial smart data refresh...
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
Occupancy updated: 0.0% (0/100)
Occupancy updated: 0.0% (0/100)
✅ Smart occupancy updated: 0/0
✅ Smart blacklist updated: 2 entries
💾 Blacklist cached locally: 2 entries
❌ Failed to fetch history: [{'date': '2025-06-25', 'time': '17:11:55.119987', 'lane': 'exit', 'license_plate': '51g99999', 'type': 'manual', 'lot_id': 1}, {'date': '2025-06-25', 'time': '14:40:22.801332', 'lane': 'entry', 'license_plate': '51g99999', 'type': 'manual', 'lot_id': 1}, {'date': '2025-06-25', 'time': '13:05:11.634261', 'lane': 'exit', 'license_plate': '30g69999', 'type': 'manual', 'lot_id': 1}, {'date': '2025-06-25', 'time': '13:04:40.702011', 'lane': 'entry', 'license_plate': '30g69999', 'type': 'manual', 'lot_id': 1}]
Updating blacklist cache - current entries: 2
Sending blacklist API request...
UI blocked for 2283 ms
Blacklist API response - success: True, data: [{'plate_id': '99a99999', 'is_blacklisted': True, 'created_at': '2025-05-13T11:23:01.515455'}, {'plate_id': '76a07676', 'is_blacklisted': True, 'created_at': '2025-05-13T20:39:18.219271'}]
Adding blacklisted plate: 99A99999
Adding blacklisted plate: 76A07676
Updating blacklist: old count=2, new count=2
Blacklist updated: 2 vehicles
🔄 Initial smart data refresh...
Occupancy updated: 0.0% (0/100)
✅ Smart occupancy updated: 0/0
✅ Smart blacklist updated: 2 entries
💾 Blacklist cached locally: 2 entries
❌ Failed to fetch history: [{'date': '2025-06-25', 'time': '17:11:55.119987', 'lane': 'exit', 'license_plate': '51g99999', 'type': 'manual', 'lot_id': 1}, {'date': '2025-06-25', 'time': '14:40:22.801332', 'lane': 'entry', 'license_plate': '51g99999', 'type': 'manual', 'lot_id': 1}, {'date': '2025-06-25', 'time': '13:05:11.634261', 'lane': 'exit', 'license_plate': '30g69999', 'type': 'manual', 'lot_id': 1}, {'date': '2025-06-25', 'time': '13:04:40.702011', 'lane': 'entry', 'license_plate': '30g69999', 'type': 'manual', 'lot_id': 1}]
🔍 OCR Request URL: https://api.platerecognizer.com/v1/plate-reader/
🔑 API Key present: Yes
📸 Image size: (83, 174, 3)
📡 Response status: 201
📋 Response content: {"processing_time":150.053,"results":[],"filename":"1056_XbIas_image.jpg","version":1,"camera_id":null,"timestamp":"2025-06-25T10:56:03.550307Z","image_width":174,"image_height":83}...
❌ No plate detected in image
OCR Service Error: No plate detected
Unknown property transition
Unknown property transition
Circuit failure recorded: consecutive=1, operation=health-check, error=Health check connect timeout
Circuit staying CLOSED: consecutive=1/5, rate=1/11 attempts
Error handling health check result: 'ControlScreen' object has no attribute 'consecutive_failures'
UI blocked for 505 ms
Error handling health check result: 'ControlScreen' object has no attribute 'api_available'
Error handling health check result: 'ControlScreen' object has no attribute 'api_available'
Unknown property transition
Vehicle skipped in entry lane - only shown in UI, not stored in database
Skipping vehicle in entry lane
🔍 OCR Request URL: https://api.platerecognizer.com/v1/plate-reader/
🔑 API Key present: Yes
📸 Image size: (82, 200, 3)
📡 Response status: 201
📋 Response content: {"processing_time":79.285,"results":[{"box":{"xmin":4,"ymin":15,"xmax":197,"ymax":72},"plate":"76a07676","region":{"code":"vn","score":0.513},"score":0.997,"candidates":[{"score":0.997,"plate":"76a076...
✅ OCR Success: 76a07676 (confidence: 0.997)
Log entry created: {'lane': 'entry', 'plate': '76a07676', 'confidence': 0.997, 'timestamp': 1750849059.0883582, 'formatted_time': '2025-06-25 17:57:39.088358', 'type': 'denied-blacklist', 'processed': False}
Blacklisted vehicle entry - stored only in local UI, not sending to server
Blacklisted vehicle in entry lane, will skip automatically
GPIO 17 set HIGH for entry lane (relay INACTIVE)
Unknown property transition
Unknown property transition
entry lane UI reset - resuming detection
Error handling health check result: 'ControlScreen' object has no attribute 'api_available'
Starting application shutdown...
Database check timer stopped
Cleaning up control screen...
Cleaning up control screen...
Stopping entry lane worker thread...
Waiting for entry lane thread to finish...
entry lane worker thread stopped
Stopping exit lane worker thread...
Waiting for exit lane thread to finish...
exit lane worker thread stopped
Control screen cleanup complete
Stopping sync service...
Stopping sync service...
Stopping sync worker thread...
Sync worker thread stopped
Stopping sync service...
Sync service stopped
Database connection closed
Application shutdown complete

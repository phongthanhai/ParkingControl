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
Circuit failure recorded: consecutive=1, operation=api-call, error=API error: HTTP 404
Circuit staying CLOSED: consecutive=1/5, rate=1/3 attempts
❌ Failed to fetch occupancy: API error: HTTP 404
Circuit failure recorded: consecutive=2, operation=api-call, error=API error: HTTP 404
Circuit staying CLOSED: consecutive=2/5, rate=2/4 attempts
❌ Failed to fetch blacklist: API error: HTTP 404
Circuit failure recorded: consecutive=3, operation=api-call, error=API error: HTTP 404
Circuit staying CLOSED: consecutive=3/5, rate=3/5 attempts
❌ Failed to fetch history: API error: HTTP 404
Updating blacklist cache - current entries: 0
Sending blacklist API request...
UI blocked for 2227 ms
Blacklist API response - success: True, data: [{'plate_id': '99a99999', 'is_blacklisted': True, 'created_at': '2025-05-13T11:23:01.515455'}, {'plate_id': '76a07676', 'is_blacklisted': True, 'created_at': '2025-05-13T20:39:18.219271'}]
Adding blacklisted plate: 99A99999
Adding blacklisted plate: 76A07676
Updating blacklist: old count=0, new count=2
Blacklist updated: 2 vehicles
🔄 Initial smart data refresh...
Circuit failure recorded: consecutive=1, operation=api-call, error=API error: HTTP 404
Circuit staying CLOSED: consecutive=1/5, rate=4/7 attempts
❌ Failed to fetch occupancy: API error: HTTP 404
Circuit failure recorded: consecutive=2, operation=api-call, error=API error: HTTP 404
Circuit staying CLOSED: consecutive=2/5, rate=5/8 attempts
❌ Failed to fetch blacklist: API error: HTTP 404
Circuit failure recorded: consecutive=3, operation=api-call, error=API error: HTTP 404
Circuit staying CLOSED: consecutive=3/5, rate=6/9 attempts
❌ Failed to fetch history: API error: HTTP 404
Health check error: 'ControlScreen' object has no attribute 'last_api_check_time'
🔍 OCR Request URL: https://api.platerecognizer.com/v1/plate-reader/
🔑 API Key present: Yes
📸 Image size: (88, 188, 3)
📡 Response status: 201
📋 Response content: {"processing_time":44.533,"results":[{"box":{"xmin":6,"ymin":10,"xmax":179,"ymax":72},"plate":"76a07676","region":{"code":"vn","score":0.178},"score":0.948,"candidates":[{"score":0.948,"plate":"76a076...
❌ PlateRecognizer error: PlateRecognizer HTTP 201: {"processing_time":44.533,"results":[{"box":{"xmin":6,"ymin":10,"xmax":179,"ymax":72},"plate":"76a07676","region":{"code":"vn","score":0.178},"score":0.948,"candidates":[{"score":0.948,"plate":"76a07676"},{"score":0.848,"plate":"75a07676"},{"score":0.84,"plate":"76k07676"},{"score":0.83,"plate":"76ao7676"},{"score":0.739,"plate":"75k07676"},{"score":0.729,"plate":"75ao7676"},{"score":0.722,"plate":"76ko7676"},{"score":0.621,"plate":"75ko7676"}],"dscore":0.783,"vehicle":{"score":0.0,"type":"Unknown","box":{"xmin":0,"ymin":0,"xmax":0,"ymax":0}}}],"filename":"1045_2lUvY_image.jpg","version":1,"camera_id":null,"timestamp":"2025-06-25T10:45:33.268549Z","image_width":188,"image_height":88}
OCR Service Error: PlateRecognizer HTTP 201: {"processing_time":44.533,"results":[{"box":{"xmin":6,"ymin":10,"xmax":179,"ymax":72},"plate":"76a07676","region":{"code":"vn","score":0.178},"score":0.948,"candidates":[{"score":0.948,"plate":"76a07676"},{"score":0.848,"plate":"75a07676"},{"score":0.84,"plate":"76k07676"},{"score":0.83,"plate":"76ao7676"},{"score":0.739,"plate":"75k07676"},{"score":0.729,"plate":"75ao7676"},{"score":0.722,"plate":"76ko7676"},{"score":0.621,"plate":"75ko7676"}],"dscore":0.783,"vehicle":{"score":0.0,"type":"Unknown","box":{"xmin":0,"ymin":0,"xmax":0,"ymax":0}}}],"filename":"1045_2lUvY_image.jpg","version":1,"camera_id":null,"timestamp":"2025-06-25T10:45:33.268549Z","image_width":188,"image_height":88}
Unknown property transition
Unknown property transition
Health check error: 'ControlScreen' object has no attribute 'last_api_check_time'
Health check error: 'ControlScreen' object has no attribute 'last_api_check_time'
Starting application shutdown...
Database check timer stopped
Cleaning up control screen...
Error during application shutdown: 'ControlScreen' object has no attribute 'cleanup
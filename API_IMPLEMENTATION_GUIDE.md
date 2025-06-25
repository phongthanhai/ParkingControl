# 📊 API Implementation Guide

## Overview
This guide covers implementing smart API calls for parking occupancy, blacklist cache, vehicle history, and fixing the OCR service for the ParkingControl system.

## 🎯 Smart Data Refresh Strategy

### Key Principle: **Event-Driven Updates**
- Refresh data **only when vehicles enter/exit** (not on timers)
- Maintain offline data availability
- Use `SimpleApiClient` singleton for all API calls
- Fast-fail with circuit breaker protection

---

## 🚗 1. Parking Occupancy Fetching

### Implementation in `control_screen.py`

```python
def _update_occupancy(self):
    """Fetch current parking lot occupancy - called on vehicle events"""
    if not self.api_client.is_online():
        print("Cannot fetch occupancy - API offline")
        return
    
    def handle_occupancy_result(success, result, context):
        if success and isinstance(result, dict):
            # Update UI with occupancy data
            total_spaces = result.get('total_spaces', 0)
            occupied_spaces = result.get('occupied_spaces', 0)
            available_spaces = total_spaces - occupied_spaces
            
            # Update your occupancy display widgets
            self.update_occupancy_display(total_spaces, occupied_spaces, available_spaces)
            print(f"✅ Occupancy updated: {occupied_spaces}/{total_spaces}")
        else:
            print(f"❌ Failed to fetch occupancy: {result}")
    
    # Async call with callback
    self.api_client.get_async(
        f"services/parking-lots/{LOT_ID}/occupancy/",
        callback=handle_occupancy_result,
        context="occupancy_refresh"
    )

def on_vehicle_entry(self, vehicle_data):
    """Called when vehicle enters - trigger occupancy refresh"""
    # ... existing vehicle entry logic ...
    
    # Smart refresh: Update occupancy after entry
    self._update_occupancy()

def on_vehicle_exit(self, vehicle_data):
    """Called when vehicle exits - trigger occupancy refresh"""
    # ... existing vehicle exit logic ...
    
    # Smart refresh: Update occupancy after exit
    self._update_occupancy()
```

### API Endpoint
- **GET** `/services/parking-lots/{LOT_ID}/occupancy/`
- **Response**: `{"total_spaces": 100, "occupied_spaces": 75}`

---

## 🚫 2. Blacklist Cache Fetching

### Implementation in `control_screen.py`

```python
def _update_blacklist_cache(self):
    """Fetch updated blacklist - called on vehicle events"""
    if not self.api_client.is_online():
        print("Cannot fetch blacklist - using cached data")
        return
    
    def handle_blacklist_result(success, result, context):
        if success and isinstance(result, list):
            # Update local blacklist cache
            self.blacklist_cache = result
            print(f"✅ Blacklist updated: {len(result)} entries")
            
            # Optional: Save to local storage for offline use
            self._save_blacklist_cache(result)
        else:
            print(f"❌ Failed to fetch blacklist: {result}")
    
    # Async call with callback
    self.api_client.get_async(
        f"services/parking-lots/{LOT_ID}/blacklist/",
        callback=handle_blacklist_result,
        context="blacklist_refresh"
    )

def _save_blacklist_cache(self, blacklist_data):
    """Save blacklist to local storage for offline access"""
    try:
        cache_file = "data/blacklist_cache.json"
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        
        with open(cache_file, 'w') as f:
            json.dump({
                'updated_at': datetime.now().isoformat(),
                'blacklist': blacklist_data
            }, f)
        print(f"💾 Blacklist cached locally: {len(blacklist_data)} entries")
    except Exception as e:
        print(f"❌ Failed to cache blacklist: {e}")

def _load_blacklist_cache(self):
    """Load blacklist from local storage when offline"""
    try:
        cache_file = "data/blacklist_cache.json"
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
                return cache_data.get('blacklist', [])
    except Exception as e:
        print(f"❌ Failed to load blacklist cache: {e}")
    return []

def is_vehicle_blacklisted(self, plate_number):
    """Check if vehicle is blacklisted (works offline)"""
    if self.api_client.is_online():
        # Use fresh blacklist cache
        blacklist = self.blacklist_cache
    else:
        # Use local cache when offline
        blacklist = self._load_blacklist_cache()
    
    return any(entry.get('plate_number') == plate_number for entry in blacklist)
```

### API Endpoint
- **GET** `/services/parking-lots/{LOT_ID}/blacklist/`
- **Response**: `[{"id": 1, "plate_number": "ABC123", "reason": "Unpaid fines"}, ...]`

---

## 📋 3. Vehicle History Fetching

### Implementation in `control_screen.py`

```python
def _update_vehicle_history(self, limit=50):
    """Fetch recent vehicle history - called on vehicle events"""
    if not self.api_client.is_online():
        print("Cannot fetch history - showing local data")
        self._show_local_history()
        return
    
    def handle_history_result(success, result, context):
        if success and isinstance(result, dict):
            history_records = result.get('records', [])
            total_count = result.get('total', 0)
            
            # Update history display
            self.update_history_display(history_records, total_count)
            print(f"✅ History updated: {len(history_records)} records")
            
            # Cache for offline use
            self._save_history_cache(history_records)
        else:
            print(f"❌ Failed to fetch history: {result}")
    
    # Async call with callback
    params = {
        'lot_id': LOT_ID,
        'limit': limit,
        'order_by': '-entry_time'  # Most recent first
    }
    
    self.api_client.get_async(
        "services/vehicle-history/",
        callback=handle_history_result,
        params=params,
        context="history_refresh"
    )

def _save_history_cache(self, history_records):
    """Save recent history for offline viewing"""
    try:
        cache_file = "data/history_cache.json"
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        
        with open(cache_file, 'w') as f:
            json.dump({
                'updated_at': datetime.now().isoformat(),
                'records': history_records[:20]  # Keep last 20 records
            }, f)
        print(f"💾 History cached locally: {len(history_records)} records")
    except Exception as e:
        print(f"❌ Failed to cache history: {e}")

def _show_local_history(self):
    """Show cached history when offline"""
    try:
        cache_file = "data/history_cache.json"
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
                history_records = cache_data.get('records', [])
                self.update_history_display(history_records, len(history_records))
                print(f"📱 Showing cached history: {len(history_records)} records")
        else:
            print("No cached history available")
    except Exception as e:
        print(f"❌ Failed to load history cache: {e}")
```

### API Endpoint
- **GET** `/services/vehicle-history/?lot_id={LOT_ID}&limit=50&order_by=-entry_time`
- **Response**: 
```json
{
  "total": 150,
  "records": [
    {
      "id": 1,
      "plate_number": "ABC123",
      "entry_time": "2024-01-15T10:30:00Z",
      "exit_time": "2024-01-15T12:30:00Z",
      "duration_minutes": 120,
      "parking_fee": 50000
    }
  ]
}
```

---

## 🎯 4. Event-Driven Integration

### Complete Integration in `control_screen.py`

```python
def on_vehicle_event(self, event_type, vehicle_data):
    """Unified handler for all vehicle events"""
    print(f"🚗 Vehicle event: {event_type} - {vehicle_data.get('plate_number')}")
    
    if event_type in ['entry', 'exit']:
        # Smart refresh on actual vehicle movement
        self._update_occupancy()        # Real-time occupancy
        self._update_blacklist_cache()  # Fresh blacklist data
        self._update_vehicle_history()  # Updated history
        
        print("✅ Smart data refresh triggered by vehicle event")

def initialize_data_refresh(self):
    """Initial data load when control screen starts"""
    if self.api_client.is_online():
        print("🔄 Initial data refresh...")
        self._update_occupancy()
        self._update_blacklist_cache()
        self._update_vehicle_history()
    else:
        print("📱 Using cached data - offline mode")
        self._show_local_history()
```

---

## 🔧 5. OCR Service Issue Diagnosis

### ❌ **CRITICAL ISSUES FOUND**

#### **Issue 1: Missing API Key** 
```python
# In config.py
PLATE_RECOGNIZER_API_KEY = ""  # ❌ EMPTY!
```

#### **Issue 2: Wrong Endpoint**
```python
# Current (WRONG):
PLATE_RECOGNIZER_URL = "https://api.platerecognizer.com/v1/plate-reader"

# Should be (CORRECT):
PLATE_RECOGNIZER_URL = "https://api.platerecognizer.com/v1/plate-reader/"
```
**Note the trailing slash!**

#### **Issue 3: Image Format**
The current implementation sends raw bytes, but PlateRecognizer expects proper file upload format.

---

## 🛠️ **TODO: OCR Service Fixes**

### **Priority 1: Configuration Fix**
```python
# In config.py - UPDATE THESE:
PLATE_RECOGNIZER_API_KEY = "your_actual_api_key_here"  # ✅ Add your API key
PLATE_RECOGNIZER_URL = "https://api.platerecognizer.com/v1/plate-reader/"  # ✅ Add trailing slash
```

### **Priority 2: Fix Image Upload Format**
**Current code in `simple_api_client.py` (line 383-391):**
```python
# ❌ WRONG FORMAT:
_, img_encoded = cv2.imencode('.jpg', image)
img_bytes = BytesIO(img_encoded.tobytes())

response = requests.post(
    PLATE_RECOGNIZER_URL,
    files={'upload': img_bytes},  # ❌ Wrong format
    headers={'Authorization': f'Token {PLATE_RECOGNIZER_API_KEY}'},
    timeout=timeout or self.plate_recognizer_timeout
)
```

**Should be:**
```python
# ✅ CORRECT FORMAT:
_, img_encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
img_bytes = BytesIO(img_encoded)

response = requests.post(
    PLATE_RECOGNIZER_URL,
    files={'upload': ('image.jpg', img_bytes, 'image/jpeg')},  # ✅ Proper file tuple
    headers={'Authorization': f'Token {PLATE_RECOGNIZER_API_KEY}'},
    timeout=timeout or self.plate_recognizer_timeout
)
```

### **Priority 3: Add Debugging**
```python
# Add debug prints to recognize_plate method:
print(f"🔍 OCR Request URL: {PLATE_RECOGNIZER_URL}")
print(f"🔑 API Key present: {'Yes' if PLATE_RECOGNIZER_API_KEY else 'No'}")
print(f"📸 Image size: {image.shape if hasattr(image, 'shape') else 'Unknown'}")
print(f"📡 Response status: {response.status_code}")
print(f"📋 Response content: {response.text[:200]}...")
```

---

## 🚀 **Implementation Order**

### **Phase 1: Fix OCR Service** (Critical)
1. ✅ Update `PLATE_RECOGNIZER_API_KEY` in config.py
2. ✅ Fix endpoint URL (add trailing slash)
3. ✅ Fix image upload format in `simple_api_client.py`
4. ✅ Add debugging logs
5. ✅ Test OCR with sample image

### **Phase 2: Implement Smart API Calls**
1. ✅ Add occupancy fetching to control screen
2. ✅ Add blacklist cache management
3. ✅ Add vehicle history fetching
4. ✅ Implement offline data caching
5. ✅ Connect to vehicle entry/exit events

### **Phase 3: Testing & Optimization**
1. ✅ Test online/offline transitions
2. ✅ Verify data refresh on vehicle events
3. ✅ Test API timeout handling
4. ✅ Optimize cache storage size

---

## 📝 **Notes**

- **No timer-based refreshing** - only event-driven updates
- **Offline support** - cached data available when API is down
- **Fast-fail behavior** - quick timeout detection with circuit breaker
- **Singleton pattern** - shared `SimpleApiClient` instance across components
- **Async callbacks** - non-blocking UI updates

---

## 🔗 **Required API Endpoints**

Your server needs to implement these endpoints:

1. **GET** `/services/parking-lots/{LOT_ID}/occupancy/`
2. **GET** `/services/parking-lots/{LOT_ID}/blacklist/`
3. **GET** `/services/vehicle-history/?lot_id={LOT_ID}&limit=50`

**External Service:**
4. **POST** `https://api.platerecognizer.com/v1/plate-reader/` (PlateRecognizer) 
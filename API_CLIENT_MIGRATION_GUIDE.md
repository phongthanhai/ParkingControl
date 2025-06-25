# API Client Migration Guide

## 🎯 **Objective**
Consolidate from dual API client architecture (`ApiClient` + `SimpleApiClient`) to a single, enhanced `SimpleApiClient` implementation with circuit breaker integration and simplified async patterns.

## 📊 **Current State Analysis**

### **Dual Client Problem**
```
Current Architecture (Problematic):
┌─────────────────────────────────────────────────────────────┐
│  app/ui/control_screen.py                                   │
│  ├─ SimpleApiClient() ✅ (for basic operations)            │
│  └─ ApiWorker/RefreshWorker ❌ (complex threading)         │
├─────────────────────────────────────────────────────────────┤
│  app/utils/db_manager.py                                    │
│  └─ ApiClient() ❌ (separate instance)                     │
├─────────────────────────────────────────────────────────────┤
│  app/controllers/sync_service.py                            │
│  └─ SimpleApiClient() ✅ (already migrated)                │
├─────────────────────────────────────────────────────────────┤
│  app/controllers/api_client.py                              │
│  └─ PlateRecognizer() ❌ (separate class)                  │
└─────────────────────────────────────────────────────────────┘

Issues:
- Multiple circuit breaker states (inconsistent)
- Separate authentication managers (can diverge)
- Different timeout behaviors
- Complex threading patterns
- Maintenance overhead
```

### **Target Architecture**
```
Target Architecture (Clean):
┌─────────────────────────────────────────────────────────────┐
│              Enhanced SimpleApiClient                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ ✅ Circuit Breaker Integration                          ││
│  │ ✅ PlateRecognizer Integration                          ││
│  │ ✅ Enhanced Token Management                            ││
│  │ ✅ Simplified Async Patterns                            ││
│  │ ✅ Singleton Pattern (Shared State)                     ││
│  │ ✅ Consistent Timeout Behavior                          ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
         ▲              ▲              ▲
         │              │              │
   ControlScreen   DBManager    SyncService
```

## 🔧 **Migration Plan**

### **Phase 1: SimpleApiClient Enhancement** ⭐ **Priority: HIGH**

#### **1.1 Add PlateRecognizer Integration**

**Current Situation:**
```python
# Separate class in api_client.py
class PlateRecognizer(QObject):
    def process(self, image, timeout=None):
        response = requests.post(PLATE_RECOGNIZER_URL, ...)
        # No circuit breaker integration
        # Separate error handling
        # Different timeout patterns
```

**Enhancement Required:**
```python
# Add to SimpleApiClient
class SimpleApiClient(QObject):
    def recognize_plate(self, image_data, timeout=None):
        """
        Integrate PlateRecognizer API with circuit breaker protection.
        
        Args:
            image_data: Image data (numpy array or bytes)
            timeout: Optional timeout (uses plate_recognizer_timeout if None)
            
        Returns:
            tuple: (success, (plate_text, confidence) or error_message)
        """
        # Check circuit breaker for external API
        if not self.connection_manager.should_attempt_operation("plate-recognition"):
            return False, "PlateRecognizer API unavailable - circuit breaker OPEN"
        
        # Rate limiting integration
        # Image encoding
        # API call with timeout
        # Circuit breaker result recording
        # Consistent error handling
```

**Implementation Details:**
- **Circuit Breaker**: Separate operation type `"plate-recognition"` for external API
- **Rate Limiting**: Integrate existing OCR rate limiting logic
- **Error Handling**: Consistent with other SimpleApiClient methods
- **Timeout Management**: Add `self.plate_recognizer_timeout = (3.0, 5.0)`

#### **1.2 Enhanced Token Management**

**Current Situation:**
```python
# ApiClient has sophisticated token refresh
class ApiClient:
    def _refresh_token(self):
        # Complex retry logic
        # Fallback to credential login
        # Thread-safe token storage
        # Multiple authentication attempts
```

**Enhancement Required:**
```python
# Enhance SimpleApiClient token refresh
class SimpleApiClient(QObject):
    def refresh_token(self):
        """Enhanced token refresh with retry logic and fallback."""
        # Current basic implementation needs:
        # 1. Retry logic (2-3 attempts)
        # 2. Credential fallback if refresh token fails
        # 3. Better error reporting
        # 4. Circuit breaker integration for auth operations
        
    def _attempt_credential_login(self):
        """Fallback login using stored credentials."""
        # Implement credential-based login fallback
        # Use stored username/password from AuthManager
        
    def _validate_token_freshness(self):
        """Check if current token needs refresh."""
        # Add token expiration checking
        # Proactive refresh before expiration
```

#### **1.3 Add Missing HTTP Methods**

**Current Gaps:**
```python
# SimpleApiClient currently has:
# ✅ get()
# ✅ post()
# ❌ put() - Missing
# ❌ delete() - Missing
# ❌ patch() - Missing
```

**Enhancement Required:**
```python
def put(self, endpoint, data=None, json_data=None, timeout=None):
    """PUT request with circuit breaker protection."""
    
def delete(self, endpoint, timeout=None):
    """DELETE request with circuit breaker protection."""
    
def patch(self, endpoint, data=None, json_data=None, timeout=None):
    """PATCH request with circuit breaker protection."""
```

#### **1.4 Simplified Async Interface**

**Current Situation:**
```python
# ControlScreen uses complex worker pattern
class ApiWorker(QRunnable):
    def run(self):
        # Complex callback system
        # Manual thread management
        # Signal/slot complexity

class RefreshWorker(QRunnable):
    # Similar complexity for token refresh
```

**Enhancement Required:**
```python
# Add simple async methods to SimpleApiClient
class SimpleApiClient(QObject):
    def get_async(self, endpoint, callback=None, context=None):
        """
        Perform GET request asynchronously using QTimer.
        
        Args:
            endpoint: API endpoint
            callback: Function to call with (success, result, context)
            context: Optional context data passed to callback
        """
        def _perform_request():
            success, result = self.get(endpoint)
            if callback:
                callback(success, result, context)
                
        # Use QTimer.singleShot for simple async execution
        QTimer.singleShot(0, _perform_request)
        
    def post_async(self, endpoint, data=None, callback=None, context=None):
        """Similar async POST implementation."""
        
    def recognize_plate_async(self, image_data, callback=None, context=None):
        """Async plate recognition."""
```

### **Phase 2: Singleton Pattern Implementation** ⭐ **Priority: HIGH**

#### **2.1 Singleton Design**

**Problem**: Multiple instances create state inconsistencies
```python
# Current: Each file creates its own instance
api_client1 = SimpleApiClient()  # control_screen.py
api_client2 = SimpleApiClient()  # sync_service.py
api_client3 = ApiClient()        # db_manager.py (different class!)
```

**Solution**: Implement singleton pattern
```python
class SimpleApiClient(QObject):
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SimpleApiClient, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, base_url=API_BASE_URL):
        if self._initialized:
            return
        super().__init__()
        # ... initialization code ...
        self._initialized = True
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

#### **2.2 Shared State Management**

**Components to Share:**
- **AuthManager**: Single authentication state
- **ConnectionManager**: Single circuit breaker state
- **Session**: Single HTTP session for connection pooling

```python
# Shared state architecture
class SimpleApiClient(QObject):
    def __init__(self, base_url=API_BASE_URL):
        if self._initialized:
            return
            
        # Shared authentication state
        self.auth_manager = AuthManager()  # Singleton
        
        # Shared circuit breaker
        self.connection_manager = ConnectionManager()  # Singleton
        
        # Shared HTTP session
        self.session = requests.Session()
        
        # Shared timeouts
        self.fast_timeout = (2.0, 3.0)
        self.health_timeout = (1.0, 2.0)
        self.plate_recognizer_timeout = (3.0, 5.0)
```

### **Phase 3: File-by-File Migration** ⭐ **Priority: MEDIUM**

#### **3.1 Control Screen Migration**

**File**: `app/ui/control_screen.py`

**Current Code Patterns to Replace:**
```python
# Remove these complex patterns:
class ApiWorker(QRunnable): ...
class RefreshWorker(QRunnable): ...

def _perform_async_api_call(self, operation_id, api_call, callback=None): ...
def _handle_async_result(self, operation_id, success, result, callback=None): ...
```

**Replace With:**
```python
# Simple async patterns using enhanced SimpleApiClient
def _update_occupancy(self):
    """Update occupancy using simple async pattern."""
    def handle_result(success, result, context):
        if success:
            self._process_occupancy_data(result)
        else:
            self.occupancy_label.setText("Occupancy data unavailable")
    
    # Simple async call
    self.api_client.get_async(
        f'services/lot-occupancy/{LOT_ID}',
        callback=handle_result,
        context="occupancy"
    )

def _attempt_token_refresh(self):
    """Simplified token refresh."""
    def handle_refresh(success, result, context):
        if success:
            self.api_available = True
            self._update_api_status(True)
        else:
            self._show_auth_error(result)
    
    self.api_client.refresh_token_async(callback=handle_refresh)
```

**Migration Steps:**
1. Replace `ApiWorker` with `SimpleApiClient.get_async()`
2. Replace `RefreshWorker` with `SimpleApiClient.refresh_token_async()`
3. Simplify callback patterns
4. Remove complex thread management
5. Use singleton instance: `self.api_client = SimpleApiClient.get_instance()`

#### **3.2 DB Manager Migration**

**File**: `app/utils/db_manager.py`

**Current Code to Replace:**
```python
# Line 628: Remove separate ApiClient instance
from app.controllers.api_client import ApiClient
api_client = ApiClient(base_url=API_BASE_URL)
success, data = api_client.get(f'parking-lots/{lot_id}', timeout=(2.0, 3.0))
```

**Replace With:**
```python
# Use singleton SimpleApiClient
from app.controllers.simple_api_client import SimpleApiClient

def _get_lot_capacity_from_api(self, lot_id):
    """Get lot capacity using shared SimpleApiClient instance."""
    try:
        api_client = SimpleApiClient.get_instance()
        
        # Only proceed if we have authentication
        if api_client.auth_manager.access_token:
            success, data = api_client.get(f'parking-lots/{lot_id}')
            
            if success and 'capacity' in data:
                # Cache the result
                setattr(self, cache_attr, data['capacity'])
                setattr(self, cache_time_attr, current_time)
                return data['capacity']
    except Exception as e:
        print(f"Error fetching lot capacity: {str(e)}")
    
    # Fallback to config
    from config import LOT_CAPACITY
    return LOT_CAPACITY
```

#### **3.3 Sync Service Verification**

**File**: `app/controllers/sync_service.py`

**Current State**: ✅ Already uses SimpleApiClient
```python
self.api_client = SimpleApiClient(base_url=API_BASE_URL)
```

**Required Changes**: 
- Update to use singleton pattern
- Verify circuit breaker consistency

```python
# Change initialization to use singleton
def __init__(self):
    super().__init__()
    
    # Use singleton instance for consistency
    self.api_client = SimpleApiClient.get_instance()
    
    # Remove separate connection manager (use shared one)
    self.connection_manager = self.api_client.connection_manager
```

### **Phase 4: Legacy Code Cleanup** ⭐ **Priority: LOW**

#### **4.1 Remove Obsolete Classes**

**Files to Clean Up:**
```python
# app/controllers/api_client.py
# Remove these classes after migration:
class PlateRecognizer(QObject): ...     # Integrated into SimpleApiClient
class ApiWorker(QRunnable): ...         # Replaced with async methods
class RefreshWorker(QRunnable): ...     # Replaced with refresh_token_async()
class ApiClient(QObject): ...           # Replaced entirely by SimpleApiClient
```

#### **4.2 Update Imports**

**Files Needing Import Updates:**
```python
# Before:
from app.controllers.api_client import ApiClient, PlateRecognizer

# After:
from app.controllers.simple_api_client import SimpleApiClient
```

#### **4.3 Configuration Updates**

**Add PlateRecognizer Settings to SimpleApiClient:**
```python
# config.py - Ensure these are available
PLATE_RECOGNIZER_API_KEY = "..."
PLATE_RECOGNIZER_URL = "https://api.platerecognizer.com/v1/plate-reader"
OCR_RATE_LIMIT = 5  # seconds between API calls
```

## 🧪 **Testing Strategy**

### **Unit Tests Required**

#### **SimpleApiClient Enhancement Tests**
```python
def test_plate_recognition_with_circuit_breaker():
    """Test PlateRecognizer integration with circuit breaker."""
    
def test_enhanced_token_refresh():
    """Test token refresh with retry logic and fallback."""
    
def test_singleton_pattern():
    """Ensure singleton pattern works correctly."""
    
def test_async_methods():
    """Test simplified async interface."""
```

#### **Integration Tests**
```python
def test_shared_circuit_breaker_state():
    """Ensure all components share same circuit breaker state."""
    
def test_authentication_consistency():
    """Verify auth state shared across all usages."""
    
def test_migration_compatibility():
    """Ensure migrated code maintains same functionality."""
```

### **Manual Testing Scenarios**

1. **Circuit Breaker Consistency**
   - Trigger network failure
   - Verify all API calls fail fast consistently
   - Confirm single circuit breaker state across app

2. **Authentication Flow**
   - Login, verify token sharing
   - Token expiration, verify refresh works
   - Network failure during auth, verify fallback

3. **PlateRecognizer Integration**
   - Image upload with various image formats
   - Rate limiting behavior
   - Error handling (invalid API key, network failure)

4. **Performance Verification**
   - Memory usage (should decrease with singleton)
   - Response times (should be consistent)
   - Connection pooling effectiveness

## 📋 **Implementation Checklist**

### **Phase 1: Enhancement** ✅
- [ ] Add `recognize_plate()` method to SimpleApiClient
- [ ] Enhance `refresh_token()` with retry logic and fallback
- [ ] Add missing HTTP methods (`put`, `delete`, `patch`)
- [ ] Implement simplified async interface
- [ ] Add PlateRecognizer timeout configuration

### **Phase 2: Singleton** ✅
- [ ] Implement singleton pattern for SimpleApiClient
- [ ] Ensure thread-safe singleton initialization
- [ ] Share AuthManager instance across all usages
- [ ] Share ConnectionManager instance across all usages
- [ ] Verify HTTP session sharing

### **Phase 3: Migration** ✅
- [ ] Migrate ControlScreen from ApiWorker to SimpleApiClient async
- [ ] Migrate ControlScreen from RefreshWorker to SimpleApiClient async
- [ ] Update DBManager to use SimpleApiClient singleton
- [ ] Update SyncService to use SimpleApiClient singleton
- [ ] Test each migration step independently

### **Phase 4: Cleanup** ✅
- [ ] Remove ApiClient class from api_client.py
- [ ] Remove PlateRecognizer class from api_client.py
- [ ] Remove ApiWorker and RefreshWorker classes
- [ ] Update all import statements
- [ ] Remove unused dependencies

### **Phase 5: Testing** ✅
- [ ] Unit tests for enhanced SimpleApiClient
- [ ] Integration tests for shared state
- [ ] Manual testing of critical flows
- [ ] Performance benchmarking
- [ ] Circuit breaker behavior verification

## 🎯 **Success Criteria**

### **Functional Requirements** ✅
- All existing API functionality preserved
- PlateRecognizer integration working
- Circuit breaker behavior consistent across app
- Authentication state shared properly
- No regression in response times

### **Code Quality** ✅
- Single API client class
- Simplified async patterns
- Reduced code complexity
- Better error handling consistency
- Improved maintainability

### **Performance** ✅
- Reduced memory usage (fewer instances)
- Better connection pooling efficiency
- Consistent timeout behavior
- Faster failure detection

## 📅 **Estimated Timeline**

| Phase | Estimated Time | Priority |
|-------|---------------|----------|
| Phase 1: Enhancement | 2-3 days | HIGH |
| Phase 2: Singleton | 1 day | HIGH |
| Phase 3: Migration | 2 days | MEDIUM |
| Phase 4: Cleanup | 0.5 day | LOW |
| Phase 5: Testing | 1 day | HIGH |
| **Total** | **6.5-7.5 days** | |

## 🚨 **Risk Mitigation**

### **Potential Risks**
1. **Authentication State Corruption**: Multiple components modifying shared auth
2. **Circuit Breaker Race Conditions**: Concurrent state modifications
3. **PlateRecognizer API Changes**: Different error patterns than backend API
4. **Memory Leaks**: Singleton holding references too long

### **Mitigation Strategies**
1. **Thread-Safe Implementation**: Use proper locking for shared state
2. **Gradual Migration**: Migrate one component at a time
3. **Extensive Testing**: Focus on edge cases and error scenarios
4. **Rollback Plan**: Keep old code in branches until migration proven stable

## 🔄 **Future Enhancements**

After successful migration, consider:

1. **Connection Pooling Optimization**: Fine-tune session configuration
2. **Metrics Collection**: Add API call timing and success rate tracking
3. **Retry Strategies**: Implement exponential backoff for transient failures
4. **Health Monitoring**: Enhanced health check capabilities
5. **Configuration Management**: Runtime configuration updates

---

**Note**: This migration will significantly improve code maintainability and system reliability by eliminating dual client complexity while preserving all existing functionality. 
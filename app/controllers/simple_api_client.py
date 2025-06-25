import requests
import time
import cv2
import threading
from io import BytesIO
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from app.utils.auth_manager import AuthManager
from app.utils.connection_state import ConnectionManager
from config import API_BASE_URL, PLATE_RECOGNIZER_API_KEY, PLATE_RECOGNIZER_URL, OCR_RATE_LIMIT

class SimpleApiClient(QObject):
    """
    Singleton API client that eliminates complex threading and uses simple async patterns.
    
    Key features:
    1. Singleton pattern for shared state
    2. True async methods using QTimer for non-blocking operations
    3. Circuit breaker integration for fast-fail behavior
    4. PlateRecognizer integration
    5. Simple callback-based async interface
    """
    
    # Singleton
    _instance = None
    _lock = threading.Lock()
    
    connection_changed = pyqtSignal(bool)  # True = online, False = offline
    
    def __new__(cls, base_url=API_BASE_URL):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SimpleApiClient, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, base_url=API_BASE_URL):
        if self._initialized:
            return
            
        super().__init__()
        
        self.base_url = base_url
        self.auth_manager = AuthManager()
        self.connection_manager = ConnectionManager()
        
        # User information for lot assignment
        self.user_id = None
        self.user_role = None
        self.assigned_lots = []
        
        # Connect to connection manager signals
        self.connection_manager.state_changed.connect(self.connection_changed.emit)
        
        # Timeout for api calls: Normal apis, health check and plate recognizer
        self.fast_timeout = (1.0, 2.0)      # Reduced for better responsiveness
        self.health_timeout = (0.5, 1.0)    # Very fast for health checks
        self.plate_recognizer_timeout = (2.0, 3.0)  # For external PlateRecognizer API
        
        # Create session for connection reuse
        self.session = requests.Session()
        
        # Configure session with reasonable settings
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=3,
            pool_maxsize=5,
            max_retries=0,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # PlateRecognizer rate limiting
        self.last_plate_call = 0
        self.plate_rate_limit_lock = threading.Lock()
        
        self._initialized = True
        print("SimpleApiClient initialized with circuit breaker integration")
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_online(self):
        """Check if API is available according to circuit breaker"""
        return self.connection_manager.is_online()
    
    def get_connection_status(self):
        """Get detailed connection status"""
        return self.connection_manager.get_status()

    # === SYNCHRONOUS METHODS (for immediate results) ===
    
    def health_check(self):
        """Perform a quick health check to test server availability."""
        if not self.connection_manager.is_online():
            print("Health check skipped - circuit breaker OPEN")
            return False
        
        try:
            response = self.session.get(
                f"{self.base_url}/services/health",
                timeout=self.health_timeout
            )
            
            success = response.status_code == 200
            
            if success:
                self.connection_manager.record_success("health-check")
                return True
            else:
                self.connection_manager.record_failure(
                    f"Health check HTTP {response.status_code}", 
                    "health-check"
                )
                return False
                
        except requests.exceptions.ConnectTimeout:
            self.connection_manager.record_failure("Health check connect timeout", "health-check")
            return False
        except requests.exceptions.ReadTimeout:
            self.connection_manager.record_failure("Health check read timeout", "health-check")
            return False
        except requests.exceptions.ConnectionError as e:
            self.connection_manager.record_failure(f"Health check connection error: {str(e)}", "health-check")
            return False
        except Exception as e:
            self.connection_manager.record_failure(f"Health check error: {str(e)}", "health-check")
            return False

    def login(self, username, password, timeout=None):
        """Authenticate user and store the token."""
        if not self.connection_manager.should_attempt_operation("login"):
            return False, "API unavailable - circuit breaker OPEN", None
        
        login_url = f"{self.base_url}/login/access-token"
        
        form_data = {
            'grant_type': 'password',
            'username': username,
            'password': password,
            'scope': '',
            'client_id': '',
            'client_secret': ''
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'accept': 'application/json'
        }
        
        try:
            response = self.session.post(
                login_url, 
                data=form_data, 
                headers=headers, 
                timeout=timeout or self.fast_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Store authentication information
                self.auth_manager.access_token = data['access_token']
                self.auth_manager.token_type = data['token_type']
                self.auth_manager.refresh_token = data.get('refresh_token')
                self.auth_manager.username = username
                self.auth_manager.password = password
                
                # Store user information if provided
                if 'user_id' in data:
                    self.user_id = data['user_id']
                if 'user_role' in data:
                    self.user_role = data['user_role']
                if 'assigned_lots' in data:
                    self.assigned_lots = data['assigned_lots']
                
                self.connection_manager.record_success("login")
                return True, "Login successful", data
            else:
                error_msg = f"Login failed with HTTP {response.status_code}"
                self.connection_manager.record_failure(error_msg, "login")
                return False, error_msg, None
                
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
            error_msg = "Login timeout - server not responding"
            self.connection_manager.record_failure(error_msg, "login")
            return False, error_msg, None
        except requests.exceptions.ConnectionError:
            error_msg = "Login failed - cannot connect to server"
            self.connection_manager.record_failure(error_msg, "login")
            return False, error_msg, None
        except Exception as e:
            error_msg = f"Login error: {str(e)}"
            self.connection_manager.record_failure(error_msg, "login")
            return False, error_msg, None

    def is_lot_assigned(self, lot_id):
        """Check if the current user is assigned to the specified lot."""
        if not self.assigned_lots:
            return False
        
        # Check if lot_id is in the assigned lots
        # Handle both string and integer lot IDs
        try:
            # Convert to int for comparison if possible
            lot_id_int = int(lot_id) if isinstance(lot_id, str) else lot_id
            
            for assigned_lot in self.assigned_lots:
                if isinstance(assigned_lot, dict):
                    # If assigned_lot is a dict, check the 'id' field
                    assigned_id = assigned_lot.get('id')
                else:
                    # If assigned_lot is a simple value
                    assigned_id = assigned_lot
                
                # Convert to int for comparison if possible
                try:
                    assigned_id_int = int(assigned_id) if isinstance(assigned_id, str) else assigned_id
                    if lot_id_int == assigned_id_int:
                        return True
                except (ValueError, TypeError):
                    # Fallback to string comparison
                    if str(lot_id) == str(assigned_id):
                        return True
                        
        except (ValueError, TypeError):
            # Fallback to string comparison for all
            for assigned_lot in self.assigned_lots:
                if isinstance(assigned_lot, dict):
                    assigned_id = assigned_lot.get('id')
                else:
                    assigned_id = assigned_lot
                    
                if str(lot_id) == str(assigned_id):
                    return True
        
        return False

    def get(self, endpoint, params=None, timeout=None):
        """Perform synchronous GET request."""
        if not self.connection_manager.should_attempt_operation("api-call"):
            return False, "API unavailable - circuit breaker OPEN"
        
        headers = self._get_auth_headers()
        if not headers:
            return False, "Authentication required"
        
        try:
            response = self.session.get(
                f"{self.base_url}/{endpoint}",
                params=params,
                headers=headers,
                timeout=timeout or self.fast_timeout
            )
            
            if response.status_code == 200:
                self.connection_manager.record_success("api-call")
                try:
                    return True, response.json()
                except:
                    return True, response.text
            elif response.status_code == 401:
                return False, "Authentication failed"
            else:
                error_msg = f"API error: HTTP {response.status_code}"
                self.connection_manager.record_failure(error_msg, "api-call")
                return False, error_msg
                
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
            error_msg = "Request timeout"
            self.connection_manager.record_failure(error_msg, "api-call")
            return False, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            self.connection_manager.record_failure(error_msg, "api-call")
            return False, error_msg
        except Exception as e:
            error_msg = f"Request error: {str(e)}"
            self.connection_manager.record_failure(error_msg, "api-call")
            return False, error_msg

    def post(self, endpoint, data=None, json_data=None, timeout=None):
        """Perform synchronous POST request."""
        if not self.connection_manager.should_attempt_operation("api-call"):
            return False, "API unavailable - circuit breaker OPEN"
        
        headers = self._get_auth_headers()
        if not headers:
            return False, "Authentication required"
        
        try:
            response = self.session.post(
                f"{self.base_url}/{endpoint}",
                data=data,
                json=json_data,
                headers=headers,
                timeout=timeout or self.fast_timeout
            )
            
            if response.status_code in [200, 201]:
                self.connection_manager.record_success("api-call")
                try:
                    return True, response.json()
                except:
                    return True, response.text
            elif response.status_code == 401:
                return False, "Authentication failed"
            else:
                error_msg = f"API error: HTTP {response.status_code}"
                self.connection_manager.record_failure(error_msg, "api-call")
                return False, error_msg
                
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
            error_msg = "Request timeout"
            self.connection_manager.record_failure(error_msg, "api-call")
            return False, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            self.connection_manager.record_failure(error_msg, "api-call")
            return False, error_msg
        except Exception as e:
            error_msg = f"Request error: {str(e)}"
            self.connection_manager.record_failure(error_msg, "api-call")
            return False, error_msg

    def post_guard_control(self, data, files=None):
        """Send guard-control request with fast-fail behavior."""
        # DEADLOCK FIX: Check circuit breaker state with a quick timeout check first
        # This prevents the hang when network is in a transitional state
        try:
            # Quick non-blocking check of circuit breaker state
            if not self.connection_manager.should_attempt_operation("guard-control"):
                print("Guard-control BLOCKED - circuit breaker OPEN (offline mode)")
                return False, "API unavailable - using offline mode"
        except Exception as e:
            # If we can't check the circuit breaker state, assume offline for safety
            print(f"Guard-control BLOCKED - circuit breaker check failed: {str(e)}")
            return False, "Circuit breaker check failed - using offline mode"
        
        print("Guard-control proceeding - circuit breaker allows operation")
        
        headers = self._get_auth_headers()
        if not headers:
            return False, "Authentication required"
        
        try:
            # CRITICAL FIX: Use very fast timeout to prevent hanging during network transitions
            # When WiFi is turned off, the connection might appear available briefly before
            # the OS realizes it's down, causing long hangs
            fast_guard_control_timeout = (1.0, 2.0)  # 1s connect, 2s read - very aggressive
            
            response = self.session.post(
                f"{self.base_url}/services/guard-control/",
                data=data,
                files=files,
                headers=headers,
                timeout=fast_guard_control_timeout
            )
            
            if response.status_code in [200, 201]:
                self.connection_manager.record_success("guard-control")
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                error_msg = f"Guard-control error: HTTP {response.status_code}"
                self.connection_manager.record_failure(error_msg, "guard-control")
                return False, error_msg
                
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
            error_msg = "Guard-control timeout - network likely down"
            print(f"Guard-control timed out after {fast_guard_control_timeout}s")
            self.connection_manager.record_failure(error_msg, "guard-control")
            return False, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Guard-control connection error: {str(e)}"
            print(f"Guard-control connection failed: {str(e)}")
            self.connection_manager.record_failure(error_msg, "guard-control")
            return False, error_msg
        except Exception as e:
            error_msg = f"Guard-control error: {str(e)}"
            print(f"Guard-control unexpected error: {str(e)}")
            self.connection_manager.record_failure(error_msg, "guard-control")
            return False, error_msg

    def recognize_plate(self, image, timeout=None):
        """
        Use PlateRecognizer service to recognize license plates from an image.
        Uses singleton pattern and rate limiting.
        """
        if PLATE_RECOGNIZER_API_KEY == "":
            return False, "PlateRecognizer API key not configured"
        
        # Rate limiting
        with self.plate_rate_limit_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_plate_call
            
            if time_since_last < OCR_RATE_LIMIT:
                sleep_time = OCR_RATE_LIMIT - time_since_last
                print(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
            
            self.last_plate_call = time.time()
        
        try:
            # ✅ FIXED: Proper image format for PlateRecognizer
            _, img_encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
            img_bytes = BytesIO(img_encoded)
            
            # Add debugging as per guide
            print(f"🔍 OCR Request URL: {PLATE_RECOGNIZER_URL}")
            print(f"🔑 API Key present: {'Yes' if PLATE_RECOGNIZER_API_KEY else 'No'}")
            print(f"📸 Image size: {image.shape if hasattr(image, 'shape') else 'Unknown'}")
            
            response = self.session.post(
                PLATE_RECOGNIZER_URL,
                files={'upload': ('image.jpg', img_bytes, 'image/jpeg')},  # ✅ FIXED: Proper file tuple
                headers={'Authorization': f'Token {PLATE_RECOGNIZER_API_KEY}'},
                timeout=timeout or self.plate_recognizer_timeout
            )
            
            print(f"📡 Response status: {response.status_code}")
            print(f"📋 Response content: {response.text[:200]}...")
            
            if response.status_code == 201:  # ✅ FIXED: PlateRecognizer returns 201, not 200
                result = response.json()
                # ✅ FIXED: Parse PlateRecognizer response format correctly
                if result.get('results') and len(result['results']) > 0:
                    plate_data = result['results'][0]
                    plate_text = plate_data.get('plate', '')
                    confidence = plate_data.get('score', 0.0)
                    print(f"✅ OCR Success: {plate_text} (confidence: {confidence:.3f})")
                    return True, (plate_text, confidence)
                else:
                    print("❌ No plate detected in image")
                    return False, "No plate detected"
            else:
                error_msg = f"PlateRecognizer HTTP {response.status_code}: {response.text}"
                print(f"❌ PlateRecognizer error: {error_msg}")
                return False, error_msg
                
        except requests.exceptions.ConnectTimeout:
            error_msg = "PlateRecognizer timeout - server not responding"
            print(f"❌ PlateRecognizer timeout")
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "PlateRecognizer connection error"
            print(f"❌ PlateRecognizer connection error")
            return False, error_msg
        except Exception as e:
            error_msg = f"PlateRecognizer error: {str(e)}"
            print(f"❌ PlateRecognizer error: {error_msg}")
            return False, error_msg

    def refresh_token(self):
        """Enhanced token refresh with retry logic and fallback."""
        if not self.auth_manager.refresh_token:
            # No refresh token available, try credential login
            return self._attempt_credential_login()
        
        refresh_url = f"{self.base_url}/login/refresh-token"
        
        # Try refresh token first
        for attempt in range(2):
            try:
                headers = {'accept': 'application/json'}
                data = {'refresh_token': self.auth_manager.refresh_token}
                
                response = self.session.post(
                    refresh_url,
                    json=data,
                    headers=headers,
                    timeout=self.fast_timeout
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    self.auth_manager.access_token = token_data['access_token']
                    self.auth_manager.token_type = token_data['token_type']
                    if 'refresh_token' in token_data:
                        self.auth_manager.refresh_token = token_data['refresh_token']
                    
                    self.connection_manager.record_success("token-refresh")
                    return True
                elif response.status_code == 401:
                    # Refresh token is invalid, try credential login
                    return self._attempt_credential_login()
                else:
                    if attempt == 0:  # First attempt failed, try once more
                        continue
                    break
                    
            except Exception as e:
                if attempt == 0:  # First attempt failed, try once more
                    continue
                print(f"Token refresh error: {str(e)}")
                break
        
        # If refresh failed, try credential login
        return self._attempt_credential_login()
    
    def _attempt_credential_login(self):
        """Fallback login using stored credentials."""
        if not self.auth_manager.username or not self.auth_manager.password:
            return False
        
        success, message, data = self.login(
            self.auth_manager.username, 
            self.auth_manager.password
        )
        return success

    # === SIMPLE ASYNC METHODS (non-blocking UI) ===
    
    def get_async(self, endpoint, callback=None, params=None, context=None):
        """Perform GET request asynchronously using QTimer."""
        def _perform_request():
            success, result = self.get(endpoint, params)
            if callback:
                callback(success, result, context)
        
        QTimer.singleShot(0, _perform_request)
    
    def post_async(self, endpoint, callback=None, data=None, json_data=None, context=None):
        """Perform POST request asynchronously using QTimer."""
        def _perform_request():
            success, result = self.post(endpoint, data, json_data)
            if callback:
                callback(success, result, context)
        
        QTimer.singleShot(0, _perform_request)
    
    def recognize_plate_async(self, image, callback=None, context=None):
        """Perform plate recognition asynchronously."""
        def _perform_recognition():
            success, result = self.recognize_plate(image)
            if callback:
                callback(success, result, context)
        
        QTimer.singleShot(0, _perform_recognition)
    
    def refresh_token_async(self, callback=None, context=None):
        """Perform token refresh asynchronously."""
        def _perform_refresh():
            success = self.refresh_token()
            message = "Token refreshed successfully" if success else "Token refresh failed"
            if callback:
                callback(success, message, context)
        
        QTimer.singleShot(0, _perform_refresh)
    
    def check_health_async(self, callback=None, timeout=None, context=None):
        """Perform health check asynchronously."""
        def _perform_health_check():
            success = self.health_check()
            if callback:
                callback(success)
        
        QTimer.singleShot(0, _perform_health_check)

    # === UTILITY METHODS ===
    
    def _get_auth_headers(self):
        """Get authorization headers for API requests."""
        if not self.auth_manager.access_token:
            return None
        
        return {
            'Authorization': f'{self.auth_manager.token_type} {self.auth_manager.access_token}',
            'accept': 'application/json'
        }
    
    def force_offline(self, reason="Manual"):
        """Force the connection to offline state."""
        self.connection_manager.force_offline(reason)
    
    def force_online(self, reason="Manual"):
        """Force the connection to online state."""
        self.connection_manager.force_online(reason)
    
    def cleanup(self):
        """Clean up resources."""
        try:
            self.session.close()
        except:
            pass

    # === SMART API METHODS FOR EVENT-DRIVEN UPDATES ===
    
    def get_occupancy_async(self, lot_id, callback=None, context=None):
        """Get parking lot occupancy - event-driven refresh"""
        if not self.is_online():
            if callback:
                callback(False, "API offline - circuit breaker OPEN", context)
            return
        
        endpoint = f"services/lot-occupancy/{lot_id}"
        self.get_async(endpoint, callback=callback, context=context)
    
    def get_blacklist_async(self, lot_id, callback=None, context=None):
        """Get blacklist for lot - event-driven refresh"""
        if not self.is_online():
            if callback:
                callback(False, "API offline - circuit breaker OPEN", context)
            return
        
        endpoint = "vehicles/blacklisted/"
        self.get_async(endpoint, callback=callback, context=context)
    
    def get_vehicle_history_async(self, lot_id, limit=50, callback=None, context=None):
        """Get recent vehicle history - event-driven refresh"""
        if not self.is_online():
            if callback:
                callback(False, "API offline - circuit breaker OPEN", context)
            return
        
        params = {
            'limit': limit,
            'lot_id': lot_id
        }
        
        self.get_async(
            "services/logs/",
            callback=callback,
            params=params,
            context=context
        )

    # === ASYNC METHODS (for non-blocking operations) ===
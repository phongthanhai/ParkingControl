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
    
    # Singleton implementation
    _instance = None
    _lock = threading.Lock()
    
    # Simple signals for status updates
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
        
        # Connect to connection manager signals
        self.connection_manager.state_changed.connect(self.connection_changed.emit)
        
        # Simple timeouts for quick failure detection
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

    def login(self, username, password):
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
                timeout=self.fast_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Store authentication information
                self.auth_manager.access_token = data['access_token']
                self.auth_manager.token_type = data['token_type']
                self.auth_manager.refresh_token = data.get('refresh_token')
                self.auth_manager.username = username
                self.auth_manager.password = password
                
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
        if not self.connection_manager.should_attempt_operation("guard-control"):
            print("Guard-control BLOCKED - circuit breaker OPEN (offline mode)")
            return False, "API unavailable - using offline mode"
        
        print("Guard-control proceeding - circuit breaker allows operation")
        
        headers = self._get_auth_headers()
        if not headers:
            return False, "Authentication required"
        
        try:
            response = self.session.post(
                f"{self.base_url}/services/guard-control/",
                data=data,
                files=files,
                headers=headers,
                timeout=self.fast_timeout
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
                
        except Exception as e:
            error_msg = f"Guard-control error: {str(e)}"
            self.connection_manager.record_failure(error_msg, "guard-control")
            return False, error_msg

    def recognize_plate(self, image, timeout=None):
        """
        Synchronous plate recognition using external PlateRecognizer service.
        
        IMPORTANT: This method is INDEPENDENT of the server API circuit breaker.
        PlateRecognizer failures do NOT affect server connectivity status.
        
        Returns:
            tuple: (success, (plate_text, confidence) or error_message)
        """
        try:
            # Check rate limiting
            with self.plate_rate_limit_lock:
                if time.time() - self.last_plate_call < OCR_RATE_LIMIT:
                    return False, "Rate limit - too many requests"
                self.last_plate_call = time.time()
            
            # Convert image to bytes
            _, img_encoded = cv2.imencode('.jpg', image)
            img_bytes = BytesIO(img_encoded.tobytes())
            
            # Make API request to EXTERNAL PlateRecognizer service
            # NOTE: This does NOT affect our server's circuit breaker state
            response = requests.post(
                PLATE_RECOGNIZER_URL,
                files={'upload': img_bytes},
                headers={'Authorization': f'Token {PLATE_RECOGNIZER_API_KEY}'},
                timeout=timeout or self.plate_recognizer_timeout
            )
            
            if response.status_code == 201:
                results = response.json()
                if results['results']:
                    plate_data = results['results'][0]
                    return True, (plate_data['plate'], plate_data['score'])
                else:
                    return False, "No plate detected"
            elif response.status_code == 429:
                return False, "API rate limit exceeded"
            else:
                return False, f"PlateRecognizer API error: {response.status_code}"
                
        except Exception as e:
            # OCR service errors are independent of server API status
            return False, f"PlateRecognizer error: {str(e)}"

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
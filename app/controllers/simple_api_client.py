import requests
import time
from PyQt5.QtCore import QObject, pyqtSignal
from app.utils.auth_manager import AuthManager
from app.utils.connection_state import ConnectionManager
from config import API_BASE_URL

class SimpleApiClient(QObject):
    """
    Simplified API client that eliminates complex threading and uses circuit breaker pattern.
    
    Key improvements:
    1. No QThreadPool - uses synchronous calls with fast timeouts
    2. Circuit breaker integration for fast-fail behavior
    3. Simplified error handling
    4. No complex callback mechanisms
    5. Thread-safe through mutex-free design
    """
    
    # Simple signals for status updates
    connection_changed = pyqtSignal(bool)  # True = online, False = offline
    
    def __init__(self, base_url=API_BASE_URL):
        super().__init__()
        
        self.base_url = base_url
        self.auth_manager = AuthManager()
        self.connection_manager = ConnectionManager()
        
        # Connect to connection manager signals
        self.connection_manager.state_changed.connect(self.connection_changed.emit)
        
        # Fast timeouts for quick failure detection
        self.fast_timeout = (2.0, 3.0)      # 2s connect, 3s read - for guard-control
        self.health_timeout = (1.0, 2.0)    # 1s connect, 2s read - for health checks
        
        # Create session for connection reuse
        self.session = requests.Session()
        
        # Configure session with reasonable settings
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=0,  # No auto-retry - we handle this
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        print("SimpleApiClient initialized with circuit breaker integration")
    
    def is_online(self):
        """Check if API is available according to circuit breaker"""
        return self.connection_manager.is_online()
    
    def get_connection_status(self):
        """Get detailed connection status"""
        return self.connection_manager.get_status()
    
    def health_check(self):
        """
        Perform a quick health check to test server availability.
        
        Returns:
            bool: True if server is reachable, False otherwise
        """
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
        """
        Authenticate user and store the token.
        
        Args:
            username (str): User's username
            password (str): User's password
            
        Returns:
            tuple: (success, message, data)
        """
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
    
    def post_guard_control(self, data, files=None):
        """
        Send guard-control request with fast-fail behavior.
        This is the critical method that was causing the race condition.
        
        Args:
            data (dict): Form data for the request
            files (dict): Files to upload
            
        Returns:
            tuple: (success, response_data_or_error_message)
        """
        # CRITICAL: Check circuit breaker FIRST - fail fast if offline
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
                timeout=self.fast_timeout  # Fast timeout!
            )
            
            if response.status_code in [200, 201]:
                self.connection_manager.record_success("guard-control")
                return True, response.json()
            else:
                error_msg = f"Guard-control failed HTTP {response.status_code}"
                self.connection_manager.record_failure(error_msg, "guard-control")
                return False, error_msg
                
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
            error_msg = "Guard-control timeout"
            self.connection_manager.record_failure(error_msg, "guard-control")
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "Guard-control connection failed"
            self.connection_manager.record_failure(error_msg, "guard-control")
            return False, error_msg
        except Exception as e:
            error_msg = f"Guard-control error: {str(e)}"
            self.connection_manager.record_failure(error_msg, "guard-control")
            return False, error_msg
    
    def get(self, endpoint, params=None):
        """
        Send GET request with circuit breaker protection.
        
        Args:
            endpoint (str): API endpoint
            params (dict): Query parameters
            
        Returns:
            tuple: (success, response_data_or_error_message)
        """
        if not self.connection_manager.is_online():
            return False, "API unavailable - circuit breaker OPEN"
        
        headers = self._get_auth_headers()
        if not headers:
            return False, "Authentication required"
        
        # Determine operation type from endpoint for better tracking
        operation_type = "general"
        if "blacklist" in endpoint:
            operation_type = "blacklist"
        elif "occupancy" in endpoint:
            operation_type = "occupancy"
        elif "logs" in endpoint:
            operation_type = "logs"
        
        try:
            response = self.session.get(
                f"{self.base_url}/{endpoint.lstrip('/')}",
                params=params,
                headers=headers,
                timeout=self.fast_timeout
            )
            
            if response.status_code == 200:
                self.connection_manager.record_success(operation_type)
                return True, response.json()
            else:
                error_msg = f"GET {endpoint} failed HTTP {response.status_code}"
                self.connection_manager.record_failure(error_msg, operation_type)
                return False, error_msg
                
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
            error_msg = f"GET {endpoint} timeout"
            self.connection_manager.record_failure(error_msg, operation_type)
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = f"GET {endpoint} connection failed"
            self.connection_manager.record_failure(error_msg, operation_type)
            return False, error_msg
        except Exception as e:
            error_msg = f"GET {endpoint} error: {str(e)}"
            self.connection_manager.record_failure(error_msg, operation_type)
            return False, error_msg
    
    def post(self, endpoint, data=None, json_data=None):
        """
        Send POST request with circuit breaker protection.
        
        Args:
            endpoint (str): API endpoint
            data (dict): Form data
            json_data (dict): JSON data
            
        Returns:
            tuple: (success, response_data_or_error_message)
        """
        if not self.connection_manager.is_online():
            return False, "API unavailable - circuit breaker OPEN"
        
        headers = self._get_auth_headers()
        if not headers:
            return False, "Authentication required"
        
        # Determine operation type from endpoint
        operation_type = "general"
        if "refresh-token" in endpoint:
            operation_type = "auth"
        
        try:
            if json_data:
                headers['Content-Type'] = 'application/json'
                response = self.session.post(
                    f"{self.base_url}/{endpoint.lstrip('/')}",
                    json=json_data,
                    headers=headers,
                    timeout=self.fast_timeout
                )
            else:
                response = self.session.post(
                    f"{self.base_url}/{endpoint.lstrip('/')}",
                    data=data,
                    headers=headers,
                    timeout=self.fast_timeout
                )
            
            if response.status_code in [200, 201]:
                self.connection_manager.record_success(operation_type)
                return True, response.json()
            else:
                error_msg = f"POST {endpoint} failed HTTP {response.status_code}"
                self.connection_manager.record_failure(error_msg, operation_type)
                return False, error_msg
                
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
            error_msg = f"POST {endpoint} timeout"
            self.connection_manager.record_failure(error_msg, operation_type)
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = f"POST {endpoint} connection failed"
            self.connection_manager.record_failure(error_msg, operation_type)
            return False, error_msg
        except Exception as e:
            error_msg = f"POST {endpoint} error: {str(e)}"
            self.connection_manager.record_failure(error_msg, operation_type)
            return False, error_msg
    
    def refresh_token(self):
        """
        Attempt to refresh the authentication token.
        
        Returns:
            bool: True if token refresh succeeded, False otherwise
        """
        if not self.connection_manager.should_attempt_operation("auth"):
            print("Token refresh skipped - circuit breaker OPEN")
            return False
        
        refresh_token = self.auth_manager.refresh_token
        if not refresh_token:
            print("No refresh token available")
            return False
        
        try:
            response = self.session.post(
                f"{self.base_url}/refresh-token",
                json={"refresh_token": refresh_token},
                headers={'Content-Type': 'application/json'},
                timeout=self.fast_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_manager.access_token = data['access_token']
                self.auth_manager.token_type = data['token_type']
                if 'refresh_token' in data:
                    self.auth_manager.refresh_token = data['refresh_token']
                
                self.connection_manager.record_success("auth")
                print("Token refreshed successfully")
                return True
            else:
                error_msg = f"Token refresh failed HTTP {response.status_code}"
                self.connection_manager.record_failure(error_msg, "auth")
                return False
                
        except Exception as e:
            error_msg = f"Token refresh error: {str(e)}"
            self.connection_manager.record_failure(error_msg, "auth")
            return False
    
    def _get_auth_headers(self):
        """Get authentication headers if available"""
        if self.auth_manager.access_token and self.auth_manager.token_type:
            return {
                "Authorization": f"{self.auth_manager.token_type} {self.auth_manager.access_token}"
            }
        return None
    
    def force_offline(self, reason="Manual"):
        """Force the API to offline mode"""
        self.connection_manager.force_offline(reason)
    
    def force_online(self, reason="Manual"):
        """Force the API to online mode"""
        self.connection_manager.force_online(reason)
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.session.close()
        except:
            pass 
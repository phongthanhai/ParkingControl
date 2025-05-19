import time
import requests
from io import BytesIO
import cv2
from PyQt5.QtCore import pyqtSignal, QObject, QThread, QMutex, QThreadPool, QRunnable, pyqtSlot
from config import PLATE_RECOGNIZER_API_KEY, PLATE_RECOGNIZER_URL, OCR_RATE_LIMIT, API_BASE_URL
import json
from app.utils.auth_manager import AuthManager

class PlateRecognizer(QObject):
    error_signal = pyqtSignal(str)
    result_signal = pyqtSignal(tuple)  # (plate_text, confidence) or (None, None)

    def __init__(self):
        super().__init__()
        self.last_call = 0
        # Default timeout values - shorter for better UI responsiveness
        self.connect_timeout = 2.0  # Reduced from 3.0
        self.read_timeout = 3.0     # Reduced from 5.0
        
        # Add rate limiting lock
        self.rate_limit_mutex = QMutex()
        
        # Keep track of workers
        self._active_workers = []
        
        # Add a flag to indicate destruction
        self._shutting_down = False

    def process(self, image, timeout=None):
        """
        Returns (plate text, confidence score) tuple or None
        
        Args:
            image: OpenCV image containing the license plate
            timeout (float or tuple): Connection and read timeout in seconds
        """
        try:
            # Don't start new workers if shutting down
            if self._shutting_down:
                print("PlateRecognizer is shutting down, rejecting new process request")
                return None
                
            # Rate limiting check with proper locking
            self.rate_limit_mutex.lock()
            try:
                if time.time() - self.last_call < OCR_RATE_LIMIT:
                    return None
                else:
                    # Mark the time immediately to prevent multiple calls getting through
                    self.last_call = time.time()
            finally:
                self.rate_limit_mutex.unlock()
            
            # Start worker thread for API call
            worker = PlateRecognizerWorker(image, timeout or (self.connect_timeout, self.read_timeout))
            worker.error_signal.connect(self.error_signal)
            worker.result_signal.connect(self._handle_result)
            worker.finished.connect(lambda: self._cleanup_worker(worker))
            
            # Track worker to prevent garbage collection
            self._active_workers.append(worker)
            
            # Clean up completed workers
            self._cleanup_workers()
            
            # Start worker
            worker.start()
            
            # Return None immediately - results will come via signal
            return None
                
        except Exception as e:
            self.error_signal.emit(f"PlateRecognizer thread error: {str(e)}")
            return None
    
    def _handle_result(self, result):
        """Handle result from worker thread"""
        # Forward to any listeners
        self.result_signal.emit(result)
    
    def _cleanup_worker(self, worker):
        """Remove a specific worker when it's finished"""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
    
    def _cleanup_workers(self):
        """Remove completed workers"""
        self._active_workers = [w for w in self._active_workers if w.isRunning()]
    
    def stop_all_workers(self):
        """Stop all running workers with proper cleanup"""
        self._shutting_down = True
        
        # Make a copy of the list to avoid modification during iteration
        workers = self._active_workers.copy()
        for worker in workers:
            try:
                if worker.isRunning():
                    worker.requestInterruption()  # Signal the thread to stop
                    if not worker.wait(300):  # Wait up to 300ms
                        print("Worker thread could not be terminated gracefully")
                        worker.terminate()  # Force termination as last resort
                        worker.wait(100)  # Give it a chance to terminate
            except Exception as e:
                print(f"Error stopping worker thread: {str(e)}")
        
        # Clear the list
        self._active_workers.clear()
    
    def __del__(self):
        """Clean up properly when object is destroyed"""
        try:
            # Set the shutdown flag first to prevent new workers from starting
            self._shutting_down = True
            
            # Explicitly stop all workers with proper cleanup
            if hasattr(self, '_active_workers') and self._active_workers:
                self.stop_all_workers()
                
            # Clear any circular references that might prevent garbage collection
            if hasattr(self, '_active_workers'):
                self._active_workers.clear()
                
        except Exception as e:
            print(f"Error cleaning up PlateRecognizer: {str(e)}")

class PlateRecognizerWorker(QThread):
    """Worker thread for making plate recognition API calls"""
    error_signal = pyqtSignal(str)
    result_signal = pyqtSignal(tuple)  # (plate_text, confidence) or (None, None)
    
    def __init__(self, image, timeout):
        super().__init__()
        self.image = image
        self.timeout = timeout
    
    def run(self):
        try:
            # Check for interruption request
            if self.isInterruptionRequested():
                return
                
            # Convert image to bytes
            _, img_encoded = cv2.imencode('.jpg', self.image)
            img_bytes = BytesIO(img_encoded.tobytes())
            
            # Check for interruption again before network call
            if self.isInterruptionRequested():
                return
                
            # Make API request with timeout
            response = requests.post(
                PLATE_RECOGNIZER_URL,
                files={'upload': img_bytes},
                headers={'Authorization': f'Token {PLATE_RECOGNIZER_API_KEY}'},
                timeout=self.timeout
            )
            
            # Check for interruption after network call
            if self.isInterruptionRequested():
                return
                
            if response.status_code == 429:
                self.error_signal.emit("API rate limit exceeded")
                self.result_signal.emit((None, None))
                return
                
            if response.status_code == 201:
                results = response.json()
                if results['results']:
                    plate_data = results['results'][0]
                    self.result_signal.emit((plate_data['plate'], plate_data['score']))
                    return
            
            # If we get here, there was no valid result
            self.result_signal.emit((None, None))
                    
        except requests.exceptions.ConnectTimeout:
            self.error_signal.emit("Connection timeout to plate recognition API")
            self.result_signal.emit((None, None))
        except requests.exceptions.ReadTimeout:
            self.error_signal.emit("Read timeout from plate recognition API")
            self.result_signal.emit((None, None))
        except requests.exceptions.RequestException as e:
            self.error_signal.emit(f"Connection error: {str(e)}")
            self.result_signal.emit((None, None))
        except Exception as e:
            self.error_signal.emit(f"Processing error: {str(e)}")
            self.result_signal.emit((None, None))
    
# Add a new ApiWorker class for threaded API operations
class ApiWorker(QRunnable):
    """Worker for executing API calls in a separate thread"""
    
    class Signals(QObject):
        finished = pyqtSignal(bool, object)
        
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = self.Signals()
        self.setAutoDelete(True)
        
    @pyqtSlot()
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.signals.finished.emit(True, result)
        except Exception as e:
            self.signals.finished.emit(False, str(e))

class ApiClient(QObject):
    """
    Client for handling API requests to the backend server.
    Manages all API interactions and authentication.
    """
    # Add a new signal for health check results
    health_check_signal = pyqtSignal(bool)
    
    def __init__(self, base_url=API_BASE_URL):
        super(ApiClient, self).__init__() 
        
        self.base_url = base_url
        self.auth_manager = AuthManager()
        # Store user information
        self.user_id = None
        self.user_role = None
        self.assigned_lots = []
        # Default timeout values (in seconds)
        self.connect_timeout = 3.0  # Reduced from 5.0
        self.read_timeout = 7.0     # Reduced from 10.0
        # Special timeout for health checks
        self.health_connect_timeout = 1.0
        self.health_read_timeout = 2.0
        
        # Create a session for connection pooling and reuse
        self.session = requests.Session()
        # Set a lower keepalive timeout to avoid stuck connections
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,     # Max number of connection pools 
            pool_maxsize=20,         # Max number of connections in each pool
            max_retries=0,           # Don't auto-retry (we handle retry logic ourselves)
            pool_block=False         # Don't block when pool is full
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Add mutex for thread safety of non-thread safe operations
        self.auth_mutex = QMutex()
        
        # Track active health check to avoid multiple parallel checks
        self._health_check_active = False
        self._health_check_mutex = QMutex()
        
        # Optimization: Cache headers to avoid recreating them for each request
        self._cached_headers = {}
        
        # Create a thread pool for API calls
        self.thread_pool = QThreadPool.globalInstance()
        # Set a reasonable maximum thread count to avoid overloading
        self.thread_pool.setMaxThreadCount(5)
        
        # Track health check callbacks
        self._health_check_callbacks = {}
        self._next_callback_id = 0
        self._callback_mutex = QMutex()
    
    def __del__(self):
        """Cleanup resources on object destruction"""
        try:
            self.session.close()
        except:
            pass

    def login(self, username, password, timeout=None):
        """
        Authenticate user and store the token.
        
        Args:
            username (str): User's username
            password (str): User's password
            timeout (float or tuple, optional): Connection and read timeout in seconds
            
        Returns:
            tuple: (success, message, data) - success is a boolean, message is a string, data contains user info
        """
        login_url = f"{self.base_url}/login/access-token"
        print(f"Attempting login at URL: {login_url}")
        
        # Use provided timeout or default values
        if timeout is None:
            timeout = (self.health_connect_timeout, self.health_read_timeout)
        
        # Prepare data in the format expected by OAuth2 form
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
            # Clear any existing token before attempting a new login
            self.auth_manager.clear()
            
            # Send POST request with timeout using session
            response = self.session.post(login_url, data=form_data, headers=headers, timeout=timeout)
            
            # Check response status
            if response.status_code == 200:
                # Parse the JSON response
                data = response.json()
                
                # Thread-safe token storage
                self.auth_mutex.lock()
                try:
                    # Store token information
                    self.auth_manager.access_token = data['access_token']
                    self.auth_manager.token_type = data['token_type']
                    
                    # Store credentials for reconnection
                    self.auth_manager.username = username
                    self.auth_manager.password = password
                    
                    # Store user information
                    self.user_id = data.get('user_id')
                    self.user_role = data.get('user_role')
                    self.assigned_lots = data.get('assigned_lots', [])
                finally:
                    self.auth_mutex.unlock()
                
                # Clear cached headers after login
                self._cached_headers = {}
                
                print(f"Login successful. Token type: {self.auth_manager.token_type}")
                return True, "Login successful", data
            else:
                # Handle error responses
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        return False, error_data['detail'], None
                except:
                    return False, f"HTTP Error: {response.status_code}", None
                
        except requests.exceptions.ConnectTimeout:
            return False, "Connection timeout. The server is not responding.", None
        except requests.exceptions.ReadTimeout:
            return False, "Read timeout. The server took too long to respond.", None
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to the server. Please check if the server is running.", None
        except Exception as e:
            return False, f"An error occurred: {str(e)}", None

    def is_lot_assigned(self, lot_id):
        """
        Check if the given lot_id is assigned to the authenticated user
        
        Args:
            lot_id (int): Lot ID to check
            
        Returns:
            bool: True if the lot is assigned to the user, False otherwise
        """
        try:
            # Ensure both are integers for comparison
            lot_id_int = int(lot_id)
            return lot_id_int in [int(l) for l in self.assigned_lots]
        except (ValueError, TypeError):
            # If conversion fails, fall back to direct comparison
            return lot_id in self.assigned_lots

    def _get_auth_header(self):
        """Get authentication header with thread safety"""
        self.auth_mutex.lock()
        try:
            # Check if we have a cached header
            if 'auth' not in self._cached_headers:
                # Create a new header
                self._cached_headers['auth'] = self.auth_manager.auth_header
            return self._cached_headers['auth']
        finally:
            self.auth_mutex.unlock()

    def get(self, endpoint, params=None, timeout=None, auth_required=True, retry_on_auth_fail=True):
        """
        Send a GET request to the API.
        
        Args:
            endpoint (str): API endpoint
            params (dict, optional): Query parameters
            timeout (float or tuple, optional): Connection and read timeout in seconds
            auth_required (bool, optional): Whether authentication is required for this endpoint
            retry_on_auth_fail (bool, optional): Whether to retry with fresh token if auth fails
            
        Returns:
            tuple: (success, data or error_message)
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Use provided timeout or default values
        if timeout is None:
            timeout = (self.connect_timeout, self.read_timeout)
        
        # Get authentication headers if required
        headers = self._get_auth_header() if auth_required else {}
        
        try:
            # Use session for connection pooling
            response = self.session.get(url, params=params, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                return True, response.json()
            elif response.status_code == 401 and auth_required and retry_on_auth_fail:
                # Only attempt token refresh if explicitly enabled and authentication is required
                print(f"Authentication failed for {url} - token might be expired")
                if self._refresh_token():
                    # Update headers with new token
                    headers = self._get_auth_header()
                    # Retry the request with the new token (but don't allow further retries to prevent loops)
                    return self.get(endpoint, params, timeout, auth_required, False)
                else:
                    return False, "Authentication failed"
            else:
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        return False, error_data['detail']
                except:
                    return False, f"HTTP Error: {response.status_code}"
                    
        except requests.exceptions.ConnectTimeout:
            return False, "Connection timeout. The server is not responding."
        except requests.exceptions.ReadTimeout:
            return False, "Read timeout. The server took too long to respond."
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def post(self, endpoint, data=None, json_data=None, timeout=None, retry_on_auth_fail=True):
        """
        Send a POST request to the API.
        
        Args:
            endpoint (str): API endpoint
            data (dict, optional): Form data
            json_data (dict, optional): JSON data
            timeout (float or tuple, optional): Connection and read timeout in seconds
            retry_on_auth_fail (bool, optional): Whether to retry with fresh token if auth fails
            
        Returns:
            tuple: (success, data or error_message)
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Use provided timeout or default values
        if timeout is None:
            timeout = (self.connect_timeout, self.read_timeout)
        
        # Get authentication headers
        headers = self._get_auth_header()
        
        try:
            if json_data:
                headers['Content-Type'] = 'application/json'
                response = self.session.post(url, json=json_data, headers=headers, timeout=timeout)
            else:
                response = self.session.post(url, data=data, headers=headers, timeout=timeout)
            
            if response.status_code in [200, 201]:
                return True, response.json()
            elif response.status_code == 401 and retry_on_auth_fail:
                print(f"Authentication failed for {url} - attempting to refresh token and retry")
                if self._refresh_token():
                    # Update headers with new token
                    headers = self._get_auth_header()
                    # Retry the request with the new token (but don't allow further retries to prevent loops)
                    return self.post(endpoint, data, json_data, timeout, False)
                else:
                    return False, "Authentication failed and token refresh failed"
            else:
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        return False, error_data['detail']
                except:
                    return False, f"HTTP Error: {response.status_code}"
                    
        except requests.exceptions.ConnectTimeout:
            return False, "Connection timeout. The server is not responding."
        except requests.exceptions.ReadTimeout:
            return False, "Read timeout. The server took too long to respond."
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def put(self, endpoint, data=None, json_data=None, timeout=None, retry_on_auth_fail=True):
        """
        Send a PUT request to the API.
        
        Args:
            endpoint (str): API endpoint
            data (dict, optional): Form data
            json_data (dict, optional): JSON data
            timeout (float or tuple, optional): Connection and read timeout in seconds
            retry_on_auth_fail (bool, optional): Whether to retry with fresh token if auth fails
            
        Returns:
            tuple: (success, data or error_message)
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Use provided timeout or default values
        if timeout is None:
            timeout = (self.connect_timeout, self.read_timeout)
        
        # Get authentication headers
        headers = self._get_auth_header()
        
        try:
            if json_data:
                headers['Content-Type'] = 'application/json'
                response = self.session.put(url, json=json_data, headers=headers, timeout=timeout)
            else:
                response = self.session.put(url, data=data, headers=headers, timeout=timeout)
            
            if response.status_code in [200, 201, 204]:
                if response.content:
                    return True, response.json()
                return True, {}
            elif response.status_code == 401 and retry_on_auth_fail:
                print(f"Authentication failed for {url} - attempting to refresh token and retry")
                if self._refresh_token():
                    # Retry the request with the new token (but don't allow further retries to prevent loops)
                    return self.put(endpoint, data, json_data, timeout, False)
                else:
                    return False, "Authentication failed and token refresh failed"
            else:
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        return False, error_data['detail']
                except:
                    return False, f"HTTP Error: {response.status_code}"
                    
        except requests.exceptions.ConnectTimeout:
            return False, "Connection timeout. The server is not responding."
        except requests.exceptions.ReadTimeout:
            return False, "Read timeout. The server took too long to respond."
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def delete(self, endpoint, timeout=None, retry_on_auth_fail=True):
        """
        Send a DELETE request to the API.
        
        Args:
            endpoint (str): API endpoint
            timeout (float or tuple, optional): Connection and read timeout in seconds
            retry_on_auth_fail (bool, optional): Whether to retry with fresh token if auth fails
            
        Returns:
            tuple: (success, data or error_message)
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Use provided timeout or default values
        if timeout is None:
            timeout = (self.connect_timeout, self.read_timeout)
        
        # Get authentication headers
        headers = self._get_auth_header()
        
        try:
            response = self.session.delete(url, headers=headers, timeout=timeout)
            
            if response.status_code in [200, 204]:
                if response.content:
                    return True, response.json()
                return True, {}
            elif response.status_code == 401 and retry_on_auth_fail:
                print(f"Authentication failed for {url} - attempting to refresh token and retry")
                if self._refresh_token():
                    # Retry the request with the new token (but don't allow further retries to prevent loops)
                    return self.delete(endpoint, timeout, False)
                else:
                    return False, "Authentication failed and token refresh failed"
            else:
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        return False, error_data['detail']
                except:
                    return False, f"HTTP Error: {response.status_code}"
                    
        except requests.exceptions.ConnectTimeout:
            return False, "Connection timeout. The server is not responding."
        except requests.exceptions.ReadTimeout:
            return False, "Read timeout. The server took too long to respond."
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def post_with_files(self, endpoint, data=None, files=None, timeout=None, retry_on_auth_fail=True):
        """
        Send a POST request with multipart/form-data including file uploads.
        
        Args:
            endpoint (str): API endpoint
            data (dict, optional): Form data
            files (dict, optional): Files to upload
            timeout (float or tuple, optional): Connection and read timeout in seconds
            retry_on_auth_fail (bool, optional): Whether to retry with fresh token if auth fails
            
        Returns:
            tuple: (success, data or error_message)
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Use provided timeout or default values
        if timeout is None:
            # Use longer timeout for file uploads
            timeout = (self.connect_timeout, self.read_timeout * 2)
        
        # Get authentication headers
        headers = self._get_auth_header()
        
        try:
            response = self.session.post(url, data=data, files=files, headers=headers, timeout=timeout)
            
            if response.status_code in [200, 201]:
                return True, response.json()
            elif response.status_code == 401 and retry_on_auth_fail:
                print(f"Authentication failed for {url} - attempting to refresh token and retry")
                if self._refresh_token():
                    # Update headers with new token
                    headers = self._get_auth_header()
                    # Retry the request with the new token (but don't allow further retries to prevent loops)
                    return self.post_with_files(endpoint, data, files, timeout, False)
                else:
                    return False, "Authentication failed and token refresh failed"
            else:
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        return False, error_data['detail']
                except:
                    return False, f"HTTP Error: {response.status_code}"
                    
        except requests.exceptions.ConnectTimeout:
            return False, "Connection timeout. The server is not responding."
        except requests.exceptions.ReadTimeout:
            return False, "Read timeout. The server took too long to respond."
        except Exception as e:
            return False, f"An error occurred: {str(e)}"
    
    def _refresh_token(self):
        """
        Internal method to refresh the authentication token using stored credentials.
        
        Returns:
            bool: True if token refresh was successful, False otherwise
        """
        # Thread-safe access to credentials
        self.auth_mutex.lock()
        try:
            # Check if we have stored credentials
            username = self.auth_manager.username
            password = self.auth_manager.password
            if not (username and password):
                print("No stored credentials available for token refresh")
                return False
        finally:
            self.auth_mutex.unlock()
            
        print(f"Attempting automatic token refresh for {username}")
        
        # Use a quick timeout for login - we don't want to hang here too long
        timeout = (self.health_connect_timeout, self.health_read_timeout)
        
        # Use direct login with lowest possible timeout
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
            # Clear any existing token before the new attempt
            self.auth_manager.clear()
            
            # Login with minimal timeout
            response = self.session.post(login_url, data=form_data, 
                                      headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # Thread-safe token update
                self.auth_mutex.lock()
                try:
                    self.auth_manager.access_token = data['access_token']
                    self.auth_manager.token_type = data['token_type']
                    
                    # Clear cached headers to force regeneration
                    self._cached_headers = {}
                finally:
                    self.auth_mutex.unlock()
                    
                print("Token refreshed successfully")
                return True
            else:
                error_msg = "Unknown error"
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        error_msg = error_data['detail']
                except:
                    error_msg = f"HTTP Error {response.status_code}"
                    
                print(f"Failed to refresh token: {error_msg}")
                return False
                
        except Exception as e:
            print(f"Token refresh error: {str(e)}")
            return False

    def check_health(self, timeout=None):
        """
        Non-blocking health check with duplicate prevention
        
        Args:
            timeout (tuple, optional): Custom timeout for health check
            
        Returns:
            bool: True if health check is successful, False otherwise
        """
        # Check if there's already an active health check to avoid duplicates
        self._health_check_mutex.lock()
        if self._health_check_active:
            self._health_check_mutex.unlock()
            return False  # Skip this check
        
        # Mark as active and unlock
        self._health_check_active = True
        self._health_check_mutex.unlock()
        
        # Use very short timeouts
        if timeout is None:
            timeout = (self.health_connect_timeout, self.health_read_timeout)
        
        try:
            # Use GET instead of HEAD since HEAD is not allowed
            response = self.session.get(
                f"{self.base_url}/services/health", 
                timeout=timeout
            )
            
            # Reset the active flag
            self._health_check_mutex.lock()
            self._health_check_active = False
            self._health_check_mutex.unlock()
            
            return response.status_code == 200
            
        except Exception as e:
            # Make sure to reset active flag even on error
            self._health_check_mutex.lock()
            self._health_check_active = False
            self._health_check_mutex.unlock()
            
            print(f"Health check error: {str(e)}")
            return False
    
    def check_health_async(self, callback=None, timeout=None):
        """
        Non-blocking health check that runs in a separate thread and calls back when done.
        
        Args:
            callback (callable, optional): Function to call with result (bool)
            timeout (tuple, optional): Custom timeout for health check
            
        Returns:
            int: Callback ID that can be used to track completion
        """
        # Use very short timeouts
        if timeout is None:
            timeout = (self.health_connect_timeout, self.health_read_timeout)
        
        callback_id = None
        if callback:
            # Store callback with a unique ID
            self._callback_mutex.lock()
            callback_id = self._next_callback_id
            self._next_callback_id += 1
            self._health_check_callbacks[callback_id] = callback
            self._callback_mutex.unlock()
        
        # Create a worker for the health check
        worker = ApiWorker(self._do_health_check, timeout, callback_id)
        worker.signals.finished.connect(self._handle_health_check_result)
        
        # Start the worker on a separate thread
        self.thread_pool.start(worker)
        
        return callback_id
    
    def _do_health_check(self, timeout, callback_id):
        """
        Perform the actual health check in a separate thread
        
        Args:
            timeout (tuple): Connection and read timeout
            callback_id (int): ID for callback lookup
            
        Returns:
            tuple: (callback_id, success)
        """
        try:
            # Only one active health check at a time
            if self._health_check_active:
                return (callback_id, False)
            
            self._health_check_mutex.lock()
            self._health_check_active = True
            self._health_check_mutex.unlock()
            
            try:
                # Use GET for health check
                response = self.session.get(
                    f"{self.base_url}/services/health", 
                    timeout=timeout
                )
                success = response.status_code == 200
            except Exception as e:
                print(f"Health check error: {str(e)}")
                success = False
            
            # Reset active flag
            self._health_check_mutex.lock()
            self._health_check_active = False
            self._health_check_mutex.unlock()
            
            return (callback_id, success)
            
        except Exception as e:
            # Make sure to reset active flag
            self._health_check_mutex.lock()
            self._health_check_active = False
            self._health_check_mutex.unlock()
            
            print(f"Async health check error: {str(e)}")
            return (callback_id, False)
    
    def _handle_health_check_result(self, success, result):
        """
        Handle result from health check worker
        
        Args:
            success (bool): Whether the worker completed successfully
            result (tuple): (callback_id, health_check_success)
        """
        if not success:
            print(f"Health check worker error: {result}")
            return
            
        callback_id, health_check_success = result
        
        # Execute callback if provided
        if callback_id is not None:
            self._callback_mutex.lock()
            if callback_id in self._health_check_callbacks:
                callback = self._health_check_callbacks.pop(callback_id)
                self._callback_mutex.unlock()
                
                # Call the callback with the result
                try:
                    callback(health_check_success)
                except Exception as e:
                    print(f"Error in health check callback: {str(e)}")
            else:
                self._callback_mutex.unlock()

import time
import requests
from io import BytesIO
import cv2
from PyQt5.QtCore import pyqtSignal, QObject
from config import PLATE_RECOGNIZER_API_KEY, PLATE_RECOGNIZER_URL, OCR_RATE_LIMIT, API_BASE_URL
import json
from app.utils.auth_manager import AuthManager

class PlateRecognizer(QObject):
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.last_call = 0
        # Default timeout values
        self.connect_timeout = 3.0
        self.read_timeout = 5.0

    def process(self, image, timeout=None):
        """
        Returns (plate text, confidence score) tuple or None
        
        Args:
            image: OpenCV image containing the license plate
            timeout (float or tuple): Connection and read timeout in seconds
        """
        try:
            if time.time() - self.last_call < OCR_RATE_LIMIT:
                return None
            
            # Use provided timeout or default values
            if timeout is None:
                timeout = (self.connect_timeout, self.read_timeout)
                
            _, img_encoded = cv2.imencode('.jpg', image)
            img_bytes = BytesIO(img_encoded.tobytes())
            
            response = requests.post(
                PLATE_RECOGNIZER_URL,
                files={'upload': img_bytes},
                headers={'Authorization': f'Token {PLATE_RECOGNIZER_API_KEY}'},
                timeout=timeout
            )
            
            if response.status_code == 429:
                self.error_signal.emit("API rate limit exceeded")
                return None
                
            if response.status_code == 201:
                results = response.json()
                if results['results']:
                    self.last_call = time.time()
                    plate_data = results['results'][0]
                    return (plate_data['plate'], plate_data['score'])
                    
        except requests.exceptions.ConnectTimeout:
            self.error_signal.emit("Connection timeout to plate recognition API")
        except requests.exceptions.ReadTimeout:
            self.error_signal.emit("Read timeout from plate recognition API")
        except requests.exceptions.RequestException as e:
            self.error_signal.emit(f"Connection error: {str(e)}")
        except Exception as e:
            self.error_signal.emit(f"Processing error: {str(e)}")
        return None
    
class ApiClient:
    """
    Client for handling API requests to the backend server.
    Manages all API interactions and authentication.
    """
    def __init__(self, base_url=API_BASE_URL):
        self.base_url = base_url
        self.auth_manager = AuthManager()
        # Store user information
        self.user_id = None
        self.user_role = None
        self.assigned_lots = []
        # Default timeout values (in seconds)
        self.connect_timeout = 3.0
        self.read_timeout = 7.0
        # Special timeout for health checks
        self.health_connect_timeout = 1.0
        self.health_read_timeout = 2.0

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
            timeout = (self.connect_timeout, self.read_timeout)
        
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
            
            # Send POST request with timeout
            response = requests.post(login_url, data=form_data, headers=headers, timeout=timeout)
            
            # Check response status
            if response.status_code == 200:
                # Parse the JSON response
                data = response.json()
                
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
        headers = self.auth_manager.auth_header if auth_required else {}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                return True, response.json()
            elif response.status_code == 401 and auth_required and retry_on_auth_fail:
                # Only attempt token refresh if explicitly enabled and authentication is required
                print(f"Authentication failed for {url} - token might be expired")
                if self._refresh_token():
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
        headers = self.auth_manager.auth_header
        
        try:
            if json_data:
                headers['Content-Type'] = 'application/json'
                response = requests.post(url, json=json_data, headers=headers, timeout=timeout)
            else:
                response = requests.post(url, data=data, headers=headers, timeout=timeout)
            
            if response.status_code in [200, 201]:
                return True, response.json()
            elif response.status_code == 401 and retry_on_auth_fail:
                print(f"Authentication failed for {url} - attempting to refresh token and retry")
                if self._refresh_token():
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
        headers = self.auth_manager.auth_header
        
        try:
            if json_data:
                headers['Content-Type'] = 'application/json'
                response = requests.put(url, json=json_data, headers=headers, timeout=timeout)
            else:
                response = requests.put(url, data=data, headers=headers, timeout=timeout)
            
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
        headers = self.auth_manager.auth_header
        
        try:
            response = requests.delete(url, headers=headers, timeout=timeout)
            
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
        headers = self.auth_manager.auth_header
        
        try:
            response = requests.post(url, data=data, files=files, headers=headers, timeout=timeout)
            
            if response.status_code in [200, 201]:
                return True, response.json()
            elif response.status_code == 401 and retry_on_auth_fail:
                print(f"Authentication failed for {url} - attempting to refresh token and retry")
                if self._refresh_token():
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
        # Check if we have stored credentials
        if not (self.auth_manager.username and self.auth_manager.password):
            print("No stored credentials available for token refresh")
            return False
            
        print(f"Attempting automatic token refresh for {self.auth_manager.username}")
        
        # Use a quick timeout for login - we don't want to hang here too long
        timeout = (self.health_connect_timeout, self.health_read_timeout)
        
        # Attempt login to get fresh token
        success, message, _ = self.login(
            self.auth_manager.username,
            self.auth_manager.password,
            timeout=timeout
        )
        
        if success:
            print("Token refreshed successfully")
            return True
        else:
            print(f"Failed to refresh token: {message}")
            return False

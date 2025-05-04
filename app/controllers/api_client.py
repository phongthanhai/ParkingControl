import time
import requests
from io import BytesIO
import cv2
from PyQt5.QtCore import pyqtSignal, QObject
from config import PLATE_RECOGNIZER_API_KEY, PLATE_RECOGNIZER_URL, OCR_RATE_LIMIT
import json
from app.utils.auth_manager import AuthManager

class PlateRecognizer(QObject):
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.last_call = 0

    def process(self, image):
        """Returns (plate text, confidence score) tuple or None"""
        try:
            if time.time() - self.last_call < OCR_RATE_LIMIT:
                return None
                
            _, img_encoded = cv2.imencode('.jpg', image)
            img_bytes = BytesIO(img_encoded.tobytes())
            
            response = requests.post(
                PLATE_RECOGNIZER_URL,
                files={'upload': img_bytes},
                headers={'Authorization': f'Token {PLATE_RECOGNIZER_API_KEY}'},
                timeout=5
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
    def __init__(self, base_url="http://127.0.0.1:8000/api/v1"):
        self.base_url = base_url
        self.auth_manager = AuthManager()

    def login(self, username, password):
        """
        Authenticate user and store the token.
        
        Args:
            username (str): User's username
            password (str): User's password
            
        Returns:
            tuple: (success, message) - success is a boolean, message is a string
        """
        login_url = f"{self.base_url}/login/access-token"
        
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
            # Send POST request
            response = requests.post(login_url, data=form_data, headers=headers)
            
            # Check response status
            if response.status_code == 200:
                # Parse the JSON response
                data = response.json()
                
                # Store token information
                self.auth_manager.access_token = data['access_token']
                self.auth_manager.token_type = data['token_type']
                
                return True, "Login successful"
            else:
                # Handle error responses
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        return False, error_data['detail']
                except:
                    return False, f"HTTP Error: {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to the server. Please check if the server is running."
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def get(self, endpoint, params=None):
        """
        Send a GET request to the API.
        
        Args:
            endpoint (str): API endpoint
            params (dict, optional): Query parameters
            
        Returns:
            tuple: (success, data or error_message)
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Get authentication headers
        headers = self.auth_manager.auth_header
        
        try:
            response = requests.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                return True, response.json()
            else:
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        return False, error_data['detail']
                except:
                    return False, f"HTTP Error: {response.status_code}"
                    
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def post(self, endpoint, data=None, json_data=None):
        """
        Send a POST request to the API.
        
        Args:
            endpoint (str): API endpoint
            data (dict, optional): Form data
            json_data (dict, optional): JSON data
            
        Returns:
            tuple: (success, data or error_message)
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Get authentication headers
        headers = self.auth_manager.auth_header
        
        try:
            if json_data:
                headers['Content-Type'] = 'application/json'
                response = requests.post(url, json=json_data, headers=headers)
            else:
                response = requests.post(url, data=data, headers=headers)
            
            if response.status_code in [200, 201]:
                return True, response.json()
            else:
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        return False, error_data['detail']
                except:
                    return False, f"HTTP Error: {response.status_code}"
                    
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def put(self, endpoint, data=None, json_data=None):
        """
        Send a PUT request to the API.
        
        Args:
            endpoint (str): API endpoint
            data (dict, optional): Form data
            json_data (dict, optional): JSON data
            
        Returns:
            tuple: (success, data or error_message)
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Get authentication headers
        headers = self.auth_manager.auth_header
        
        try:
            if json_data:
                headers['Content-Type'] = 'application/json'
                response = requests.put(url, json=json_data, headers=headers)
            else:
                response = requests.put(url, data=data, headers=headers)
            
            if response.status_code in [200, 201, 204]:
                if response.content:
                    return True, response.json()
                return True, {}
            else:
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        return False, error_data['detail']
                except:
                    return False, f"HTTP Error: {response.status_code}"
                    
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def delete(self, endpoint):
        """
        Send a DELETE request to the API.
        
        Args:
            endpoint (str): API endpoint
            
        Returns:
            tuple: (success, data or error_message)
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Get authentication headers
        headers = self.auth_manager.auth_header
        
        try:
            response = requests.delete(url, headers=headers)
            
            if response.status_code in [200, 204]:
                if response.content:
                    return True, response.json()
                return True, {}
            else:
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        return False, error_data['detail']
                except:
                    return False, f"HTTP Error: {response.status_code}"
                    
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

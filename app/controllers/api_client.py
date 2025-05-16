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
        self.connect_timeout = 3.0
        self.read_timeout = 5.0

    def process(self, image, timeout=None):
        try:
            if time.time() - self.last_call < OCR_RATE_LIMIT:
                return None
            
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
    def __init__(self, base_url=API_BASE_URL):
        self.base_url = base_url
        self.auth_manager = AuthManager()
        self.user_id = None
        self.user_role = None
        self.assigned_lots = []
        self.connect_timeout = 5.0
        self.read_timeout = 10.0

    def login(self, username, password, timeout=None):
        login_url = f"{self.base_url}/login/access-token"
        
        if timeout is None:
            timeout = (self.connect_timeout, self.read_timeout)
        
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
            self.auth_manager.clear()
            
            response = requests.post(login_url, data=form_data, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                self.auth_manager.access_token = data['access_token']
                self.auth_manager.token_type = data['token_type']
                
                self.auth_manager.username = username
                self.auth_manager.password = password
                
                self.user_id = data.get('user_id')
                self.user_role = data.get('user_role')
                self.assigned_lots = data.get('assigned_lots', [])
                
                return True, "Login successful", data
            else:
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
        try:
            lot_id_int = int(lot_id)
            return lot_id_int in [int(l) for l in self.assigned_lots]
        except (ValueError, TypeError):
            return lot_id in self.assigned_lots

    def get(self, endpoint, params=None, timeout=None, auth_required=True, retry_on_auth_fail=True):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        if timeout is None:
            timeout = (self.connect_timeout, self.read_timeout)
        
        headers = self.auth_manager.auth_header if auth_required else {}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                return True, response.json()
            elif response.status_code == 401 and auth_required and retry_on_auth_fail:
                if self._refresh_token():
                    return self.get(endpoint, params, timeout, auth_required, False)
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

    def post(self, endpoint, data=None, json_data=None, timeout=None, retry_on_auth_fail=True):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        if timeout is None:
            timeout = (self.connect_timeout, self.read_timeout)
        
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
                if self._refresh_token():
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
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        if timeout is None:
            timeout = (self.connect_timeout, self.read_timeout)
        
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
                if self._refresh_token():
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
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        if timeout is None:
            timeout = (self.connect_timeout, self.read_timeout)
        
        headers = self.auth_manager.auth_header
        
        try:
            response = requests.delete(url, headers=headers, timeout=timeout)
            
            if response.status_code in [200, 204]:
                if response.content:
                    return True, response.json()
                return True, {}
            elif response.status_code == 401 and retry_on_auth_fail:
                if self._refresh_token():
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
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        if timeout is None:
            timeout = (self.connect_timeout, self.read_timeout * 2)
        
        headers = self.auth_manager.auth_header
        
        try:
            response = requests.post(url, data=data, files=files, headers=headers, timeout=timeout)
            
            if response.status_code in [200, 201]:
                return True, response.json()
            elif response.status_code == 401 and retry_on_auth_fail:
                if self._refresh_token():
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
        if not (self.auth_manager.username and self.auth_manager.password):
            return False
            
        timeout = (3.0, 5.0)
        
        success, message, _ = self.login(
            self.auth_manager.username,
            self.auth_manager.password,
            timeout=timeout
        )
        
        return success

import time
import threading
import random
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer, QMutex
from config import API_BASE_URL
from app.controllers.api_client import ApiClient
from app.utils.auth_manager import AuthManager

class ConnectionState:
    """Enum-like class for connection states"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"


class ConnectionManager(QObject):
    """
    Centralized manager for handling API connectivity and authentication.
    
    This class:
    1. Performs periodic health checks in a background thread
    2. Manages authentication token refresh
    3. Implements exponential backoff for reconnection attempts
    4. Provides signals for connection state changes
    """
    
    # Signals
    connection_state_changed = pyqtSignal(bool)  # True if connected, False if disconnected
    connection_state_message = pyqtSignal(str)   # Detailed status message
    
    def __init__(self, base_url=API_BASE_URL):
        super().__init__()
        
        # Connection settings
        self.base_url = base_url
        self.api_client = ApiClient(base_url=base_url)
        self.auth_manager = AuthManager()
        
        # State variables
        self._state = ConnectionState.DISCONNECTED
        self._state_mutex = QMutex()
        self._connected = False
        self._authenticating = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        
        # Backoff strategy settings
        self._initial_backoff = 2  # seconds
        self._max_backoff = 300    # 5 minutes max
        self._backoff_factor = 1.5
        self._jitter = 0.1         # 10% jitter to avoid thundering herd
        
        # Timeouts
        self._health_check_timeout = (2.0, 3.0)  # (connect_timeout, read_timeout)
        self._auth_check_timeout = (3.0, 5.0)
        
        # Health check thread and timer
        self._stop_health_check = threading.Event()
        self._health_check_thread = None
        self._health_check_interval = 10  # seconds between health checks
        
        # Start health check thread
        self._start_health_check_thread()
    
    def _start_health_check_thread(self):
        """Start the background health check thread"""
        self._stop_health_check.clear()
        self._health_check_thread = threading.Thread(
            target=self._health_check_worker,
            daemon=True
        )
        self._health_check_thread.start()
    
    def _health_check_worker(self):
        """Background worker that periodically checks API health"""
        while not self._stop_health_check.is_set():
            try:
                # Check connection and update state
                self._check_connection()
                
                # Determine next check interval (using backoff if disconnected)
                if self._connected:
                    # Reset backoff when connected
                    self._reconnect_attempts = 0
                    wait_time = self._health_check_interval
                else:
                    # Use backoff strategy when disconnected
                    wait_time = self._calculate_backoff()
                    
                # Wait for the determined interval or until stopped
                self._stop_health_check.wait(wait_time)
            except Exception as e:
                # Catch any exceptions to prevent thread from dying
                print(f"Error in health check thread: {str(e)}")
                # Wait a bit before retrying
                self._stop_health_check.wait(self._health_check_interval)
    
    def _calculate_backoff(self):
        """Calculate the exponential backoff time with jitter"""
        if self._reconnect_attempts == 0:
            return self._health_check_interval
            
        backoff = min(
            self._max_backoff,
            self._initial_backoff * (self._backoff_factor ** self._reconnect_attempts)
        )
        
        # Add jitter to avoid all clients reconnecting simultaneously
        jitter_amount = backoff * self._jitter
        backoff = backoff + random.uniform(-jitter_amount, jitter_amount)
        
        print(f"Using backoff of {backoff:.2f}s for reconnect attempt {self._reconnect_attempts}")
        return backoff
    
    def _check_connection(self):
        """
        Check API connection and authentication state.
        Updates the internal state and emits signals on changes.
        """
        # Skip if we're currently in the middle of authentication
        if self._authenticating:
            return
            
        # First check basic connectivity with health endpoint (no auth required)
        is_reachable = self._is_api_reachable()
        
        if is_reachable:
            # If API is reachable, check authentication status
            is_authenticated = self._is_authenticated()
            
            # Update state based on authentication
            if is_authenticated and not self._connected:
                self._update_state(ConnectionState.CONNECTED)
                self._connected = True
                self.connection_state_changed.emit(True)
                self.connection_state_message.emit("Connected to server")
                
            elif not is_authenticated and self._connected:
                # Try to refresh token
                self._refresh_token()
                
        elif self._connected:
            # API was connected but now unreachable
            self._update_state(ConnectionState.DISCONNECTED)
            self._connected = False
            self.connection_state_changed.emit(False)
            self.connection_state_message.emit("Connection to server lost")
            self._reconnect_attempts += 1
    
    def _is_api_reachable(self):
        """Check if the API server is reachable (no auth required)"""
        try:
            # Use the health check endpoint that doesn't require authentication
            success, _ = self.api_client.get(
                'services/health', 
                timeout=self._health_check_timeout, 
                auth_required=False
            )
            return success
        except Exception as e:
            print(f"Error checking API reachability: {str(e)}")
            return False
    
    def _is_authenticated(self):
        """Check if we have valid authentication credentials"""
        try:
            # Skip auth check if we don't have a token
            if not self.auth_manager.access_token:
                return False
                
            # Try an authenticated endpoint
            success, response = self.api_client.get(
                'services/lot-occupancy/1',
                timeout=self._auth_check_timeout
            )
            
            return success
        except Exception as e:
            print(f"Error checking authentication: {str(e)}")
            return False
    
    def _refresh_token(self):
        """Attempt to refresh the authentication token"""
        try:
            self._authenticating = True
            
            # Check if we have stored credentials
            if not (self.auth_manager.username and self.auth_manager.password):
                print("No stored credentials available for token refresh")
                
                # Update state
                self._update_state(ConnectionState.DISCONNECTED)
                self._connected = False
                self.connection_state_changed.emit(False)
                self.connection_state_message.emit("Authentication expired - Please log in again")
                
                return False
                
            print(f"Attempting to refresh token for {self.auth_manager.username}")
            
            # Attempt login to get fresh token
            success, message, _ = self.api_client.login(
                self.auth_manager.username,
                self.auth_manager.password,
                timeout=self._auth_check_timeout
            )
            
            if success:
                print("Token refreshed successfully")
                
                # Update state
                self._update_state(ConnectionState.CONNECTED)
                self._connected = True
                self.connection_state_changed.emit(True)
                self.connection_state_message.emit("Connection restored")
                
                return True
            else:
                print(f"Failed to refresh token: {message}")
                
                # Update state
                self._update_state(ConnectionState.DISCONNECTED)
                self._connected = False
                self.connection_state_changed.emit(False)
                self.connection_state_message.emit(f"Authentication failed: {message}")
                
                return False
        except Exception as e:
            print(f"Error refreshing token: {str(e)}")
            return False
        finally:
            self._authenticating = False
    
    def _update_state(self, new_state):
        """Thread-safe state update"""
        self._state_mutex.lock()
        self._state = new_state
        self._state_mutex.unlock()
    
    def get_state(self):
        """Thread-safe getter for connection state"""
        self._state_mutex.lock()
        state = self._state
        self._state_mutex.unlock()
        return state
    
    def is_connected(self):
        """Check if the API is currently connected and authenticated"""
        return self._connected
    
    def force_reconnect(self):
        """
        Force an immediate reconnection attempt
        
        Returns:
            bool: True if reconnection was successful, False otherwise
        """
        # Reset the reconnect attempts counter to allow faster initial retry
        self._reconnect_attempts = 0
        
        # Try the connection immediately
        self._check_connection()
        
        # Return current connection state
        return self._connected
    
    def force_token_refresh(self):
        """
        Force a token refresh attempt
        
        Returns:
            bool: True if refresh was successful, False otherwise
        """
        return self._refresh_token()
    
    def stop(self):
        """Stop the connection manager and all background threads"""
        # Stop health check thread
        if self._health_check_thread and self._health_check_thread.is_alive():
            self._stop_health_check.set()
            self._health_check_thread.join(timeout=1.0)
    
    def __del__(self):
        """Clean up resources when object is destroyed"""
        self.stop() 
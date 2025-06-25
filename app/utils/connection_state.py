import time
import threading
from enum import Enum
from PyQt5.QtCore import QObject, pyqtSignal

class ConnectionState(Enum):
    """States for the circuit breaker pattern"""
    CLOSED = "closed"      # Normal operation, API calls allowed
    OPEN = "open"          # API is down, fail fast
    HALF_OPEN = "half_open"  # Testing if API recovered

class ConnectionManager(QObject):
    """
    Centralized connection state manager implementing Circuit Breaker pattern with enhanced
    false-positive protection.
    
    This implementation uses multiple failure detection strategies:
    1. Consecutive failures (like your original implementation)
    2. Failure rate within time window
    3. Different sensitivity for different types of operations
    
    Circuit Breaker Pattern:
    - CLOSED: Normal operation, all API calls proceed
    - OPEN: API is down, all calls fail immediately 
    - HALF_OPEN: Testing recovery, limited calls allowed
    """
    
    # Signals for notifying components of state changes
    state_changed = pyqtSignal(bool)  # True = online, False = offline
    transition_detected = pyqtSignal(str, str)  # from_state, to_state
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ConnectionManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Initialize the connection manager state"""
        super().__init__()
        
        # Circuit breaker state
        self.state = ConnectionState.CLOSED
        self.failure_count = 0
        self.consecutive_failures = 0  # Track consecutive failures specifically
        self.last_failure_time = 0
        self.last_success_time = time.time()
        
        # ENHANCED: More robust configuration to prevent false positives
        self.consecutive_failure_threshold = 3      # ⚡ FASTER: 3 consecutive failures (was 5)
        self.failure_rate_threshold = 0.8          # 80% failure rate in time window
        self.failure_rate_window = 60              # 60 second sliding window
        self.min_attempts_for_rate = 3             # Minimum attempts before rate calculation
        self.recovery_timeout = 30                 # Seconds to wait before trying half-open
        self.success_threshold = 2                 # Successes needed to close circuit from half-open
        self.consecutive_successes = 0
        
        # Enhanced failure tracking with sliding window
        self.failure_history = []  # List of (timestamp, failure_type) tuples
        self.success_history = []  # List of (timestamp,) tuples
        self.max_history_age = 300  # Keep 5 minutes of history
        
        # Different sensitivity for critical vs non-critical operations
        self.critical_operations = {'guard-control', 'login'}  # These need higher confidence
        self.critical_consecutive_threshold = 3    # Stricter for critical operations
        
        # Threading protection
        self.state_lock = threading.Lock()
        
        print("ConnectionManager initialized - Circuit CLOSED (online)")
        print(f"Config: consecutive_threshold={self.consecutive_failure_threshold}, "
              f"rate_threshold={self.failure_rate_threshold}, window={self.failure_rate_window}s")
    
    def is_online(self):
        """
        Check if API calls should proceed.
        
        Returns:
            bool: True if API calls should proceed, False if they should fail fast
        """
        with self.state_lock:
            if self.state == ConnectionState.CLOSED:
                return True
            elif self.state == ConnectionState.OPEN:
                # Check if we should transition to half-open
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self._transition_to_half_open()
                    return True  # Allow one test call
                return False
            elif self.state == ConnectionState.HALF_OPEN:
                return True  # Allow test calls
            
        return False
    
    def should_attempt_operation(self, operation_type="general"):
        """
        More granular check that considers operation criticality.
        
        Args:
            operation_type (str): Type of operation ('guard-control', 'login', 'health-check', etc.)
            
        Returns:
            bool: True if operation should proceed, False for fast-fail
        """
        with self.state_lock:
            if self.state == ConnectionState.CLOSED:
                return True
            elif self.state == ConnectionState.OPEN:
                # For critical operations during circuit OPEN, still block
                # For non-critical operations, also block
                return False
            elif self.state == ConnectionState.HALF_OPEN:
                # In half-open, allow health checks and critical operations only
                return operation_type in {'health-check', 'guard-control', 'login'}
            
        return False
    
    def record_success(self, operation_type="general"):
        """
        Record a successful API call with operation context.
        
        Args:
            operation_type (str): Type of operation that succeeded
        """
        with self.state_lock:
            current_time = time.time()
            self.last_success_time = current_time
            
            # Add to success history
            self.success_history.append((current_time,))
            self._cleanup_history()
            
            # Reset consecutive failure counter on any success
            self.consecutive_failures = 0
            
            if self.state == ConnectionState.HALF_OPEN:
                self.consecutive_successes += 1
                print(f"Circuit HALF_OPEN: Success {self.consecutive_successes}/{self.success_threshold} ({operation_type})")
                
                if self.consecutive_successes >= self.success_threshold:
                    self._transition_to_closed()
            elif self.state == ConnectionState.OPEN:
                # Shouldn't happen in normal flow, but handle gracefully
                print(f"Unexpected success during OPEN state ({operation_type}), transitioning to HALF_OPEN")
                self._transition_to_half_open()
    
    def record_failure(self, error_msg="", operation_type="general"):
        """
        Record a failed API call with enhanced false-positive protection.
        
        Args:
            error_msg (str): Description of the failure
            operation_type (str): Type of operation that failed
        """
        with self.state_lock:
            current_time = time.time()
            self.last_failure_time = current_time
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            
            # Add to failure history with context
            self.failure_history.append((current_time, operation_type, error_msg))
            self._cleanup_history()
            
            print(f"Circuit failure recorded: consecutive={self.consecutive_failures}, "
                  f"operation={operation_type}, error={error_msg}")
            
            # Determine if we should open the circuit based on multiple criteria
            should_open = self._should_open_circuit(operation_type)
            
            if self.state == ConnectionState.CLOSED and should_open:
                self._transition_to_open()
            elif self.state == ConnectionState.HALF_OPEN:
                # Any failure in half-open goes back to open (this is correct)
                print(f"HALF_OPEN test failed ({operation_type}), returning to OPEN")
                self._transition_to_open()
    
    def _should_open_circuit(self, operation_type):
        """
        Enhanced logic to determine if circuit should open, preventing false positives.
        
        Args:
            operation_type (str): Type of operation that failed
            
        Returns:
            bool: True if circuit should open
        """
        current_time = time.time()
        
        # Strategy 1: Consecutive failures (your original approach)
        threshold = (self.critical_consecutive_threshold 
                    if operation_type in self.critical_operations 
                    else self.consecutive_failure_threshold)
        
        if self.consecutive_failures >= threshold:
            print(f"Consecutive failure threshold reached: {self.consecutive_failures}/{threshold}")
            return True
        
        # Strategy 2: Failure rate in sliding window (additional protection)
        window_start = current_time - self.failure_rate_window
        recent_failures = [f for f in self.failure_history if f[0] >= window_start]
        recent_successes = [s for s in self.success_history if s[0] >= window_start]
        
        total_attempts = len(recent_failures) + len(recent_successes)
        
        # Only consider failure rate if we have enough data
        if total_attempts >= self.min_attempts_for_rate:
            failure_rate = len(recent_failures) / total_attempts
            if failure_rate >= self.failure_rate_threshold:
                print(f"Failure rate threshold exceeded: {failure_rate:.2%} "
                      f"({len(recent_failures)}/{total_attempts} in {self.failure_rate_window}s)")
                return True
        
        # Strategy 3: Critical operation failures get special treatment
        if operation_type in self.critical_operations:
            # For critical operations, also check if we've had multiple failures recently
            critical_failures = [f for f in recent_failures if f[1] in self.critical_operations]
            if len(critical_failures) >= 3:  # 3 critical operation failures in window
                print(f"Multiple critical operation failures: {len(critical_failures)} in {self.failure_rate_window}s")
                return True
        
        print(f"Circuit staying CLOSED: consecutive={self.consecutive_failures}/{threshold}, "
              f"rate={len(recent_failures)}/{total_attempts} attempts")
        return False
    
    def _cleanup_history(self):
        """Clean up old entries from failure/success history"""
        current_time = time.time()
        cutoff_time = current_time - self.max_history_age
        
        self.failure_history = [f for f in self.failure_history if f[0] >= cutoff_time]
        self.success_history = [s for s in self.success_history if s[0] >= cutoff_time]
    
    def force_offline(self, reason="Manual override"):
        """
        Force the circuit to OPEN state (offline).
        Used for manual testing or when we detect the server is definitely down.
        
        Args:
            reason (str): Reason for forcing offline
        """
        with self.state_lock:
            print(f"Forcing circuit OPEN: {reason}")
            self._transition_to_open()
    
    def force_online(self, reason="Manual override"):
        """
        Force the circuit to CLOSED state (online).
        Used for manual testing or when we know the server is back up.
        
        Args:
            reason (str): Reason for forcing online
        """
        with self.state_lock:
            print(f"Forcing circuit CLOSED: {reason}")
            self.consecutive_failures = 0
            self.consecutive_successes = 0
            self._transition_to_closed()
    
    def get_status(self):
        """
        Get current status information.
        
        Returns:
            dict: Status information including state, failure count, etc.
        """
        with self.state_lock:
            current_time = time.time()
            
            # Calculate recent failure statistics
            window_start = current_time - self.failure_rate_window
            recent_failures = [f for f in self.failure_history if f[0] >= window_start]
            recent_successes = [s for s in self.success_history if s[0] >= window_start]
            total_recent = len(recent_failures) + len(recent_successes)
            failure_rate = len(recent_failures) / total_recent if total_recent > 0 else 0
            
            return {
                'state': self.state.value,
                'is_online': self.state != ConnectionState.OPEN,
                'consecutive_failures': self.consecutive_failures,
                'consecutive_failure_threshold': self.consecutive_failure_threshold,
                'failure_rate': failure_rate,
                'failure_rate_threshold': self.failure_rate_threshold,
                'recent_attempts': total_recent,
                'last_failure_time': self.last_failure_time,
                'last_success_time': self.last_success_time,
                'time_since_last_failure': current_time - self.last_failure_time if self.last_failure_time > 0 else -1,
                'time_since_last_success': current_time - self.last_success_time,
                'consecutive_successes': self.consecutive_successes
            }
    
    def adjust_sensitivity(self, consecutive_threshold=None, failure_rate_threshold=None, 
                          failure_rate_window=None):
        """
        Adjust circuit breaker sensitivity for different environments.
        
        Args:
            consecutive_threshold (int): Number of consecutive failures before opening
            failure_rate_threshold (float): Failure rate (0.0-1.0) before opening  
            failure_rate_window (int): Time window in seconds for rate calculation
        """
        with self.state_lock:
            if consecutive_threshold is not None:
                self.consecutive_failure_threshold = consecutive_threshold
                print(f"Adjusted consecutive failure threshold to {consecutive_threshold}")
            
            if failure_rate_threshold is not None:
                self.failure_rate_threshold = failure_rate_threshold
                print(f"Adjusted failure rate threshold to {failure_rate_threshold:.2%}")
            
            if failure_rate_window is not None:
                self.failure_rate_window = failure_rate_window
                print(f"Adjusted failure rate window to {failure_rate_window}s")
    
    def _transition_to_open(self):
        """Transition to OPEN state (offline)"""
        old_state = self.state
        self.state = ConnectionState.OPEN
        self.consecutive_successes = 0
        
        # Log detailed failure analysis
        current_time = time.time()
        window_start = current_time - self.failure_rate_window
        recent_failures = [f for f in self.failure_history if f[0] >= window_start]
        
        print(f"Circuit transition: {old_state.value} -> OPEN (offline)")
        print(f"  Consecutive failures: {self.consecutive_failures}")
        print(f"  Recent failures: {len(recent_failures)} in {self.failure_rate_window}s")
        if recent_failures:
            print(f"  Recent failure types: {[f[1] for f in recent_failures[-3:]]}")
        
        self.transition_detected.emit(old_state.value, "open")
        self.state_changed.emit(False)  # offline
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state (testing recovery)"""
        old_state = self.state
        self.state = ConnectionState.HALF_OPEN
        self.consecutive_successes = 0
        
        print(f"Circuit transition: {old_state.value} -> HALF_OPEN (testing)")
        self.transition_detected.emit(old_state.value, "half_open")
        # Don't emit state_changed yet - wait for success/failure
    
    def _transition_to_closed(self):
        """Transition to CLOSED state (online)"""
        old_state = self.state
        self.state = ConnectionState.CLOSED
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        
        print(f"Circuit transition: {old_state.value} -> CLOSED (online)")
        self.transition_detected.emit(old_state.value, "closed")
        self.state_changed.emit(True)  # online
    
    def reset(self):
        """Reset the circuit breaker to initial state"""
        with self.state_lock:
            old_state = self.state
            self.state = ConnectionState.CLOSED
            self.consecutive_failures = 0
            self.consecutive_successes = 0
            self.last_failure_time = 0
            self.last_success_time = time.time()
            
            # Clear history
            self.failure_history.clear()
            self.success_history.clear()
            
            print("Circuit breaker reset to CLOSED state")
            if old_state != ConnectionState.CLOSED:
                self.transition_detected.emit(old_state.value, "closed")
                self.state_changed.emit(True)  # online 
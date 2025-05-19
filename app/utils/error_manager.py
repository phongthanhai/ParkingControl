import logging
import traceback
import os
import sys
import json
import time
from enum import Enum
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal

# Set up logging format
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'

# Define error severity levels
class ErrorSeverity(Enum):
    INFO = 0      # Informational message, not an error
    LOW = 1       # Minor issue, application can continue normally
    MEDIUM = 2    # Significant issue, feature affected but app can continue
    HIGH = 3      # Critical issue, feature unusable but app can continue
    CRITICAL = 4  # Fatal error, application cannot continue

# Define error categories
class ErrorCategory(Enum):
    NETWORK = "network"       # Network connectivity issues
    DATABASE = "database"     # Database errors
    AUTH = "authentication"   # Authentication/authorization errors
    API = "api"               # API-related errors
    UI = "ui"                 # UI-related errors
    HARDWARE = "hardware"     # Hardware-related errors (camera, GPIO)
    OCR = "ocr"               # OCR-specific errors
    CONFIG = "config"         # Configuration errors
    SYSTEM = "system"         # System-level errors (OS, file system)
    UNKNOWN = "unknown"       # Unknown/unclassified errors

class ErrorResponse:
    """
    Standardized error response object.
    Provides consistent format for error handling and reporting.
    """
    def __init__(self, 
                 message, 
                 category=ErrorCategory.UNKNOWN, 
                 severity=ErrorSeverity.MEDIUM,
                 error=None,
                 details=None):
        self.message = message
        self.category = category
        self.severity = severity
        self.timestamp = datetime.now()
        self.error = error
        self.details = details or {}
        
        # Log the error immediately when created
        self._log_error()
    
    def _log_error(self):
        """Log the error using the appropriate severity level"""
        logger = logging.getLogger('app')
        
        # Build error message
        error_msg = f"{self.category.value.upper()}: {self.message}"
        
        # Add error details if available
        if self.error:
            error_msg += f" - {str(self.error)}"
        
        # Log using appropriate level based on severity
        if self.severity == ErrorSeverity.INFO:
            logger.info(error_msg)
        elif self.severity == ErrorSeverity.LOW:
            logger.debug(error_msg)
        elif self.severity == ErrorSeverity.MEDIUM:
            logger.warning(error_msg)
        elif self.severity == ErrorSeverity.HIGH:
            logger.error(error_msg)
        elif self.severity == ErrorSeverity.CRITICAL:
            logger.critical(error_msg)
            
    def to_dict(self):
        """Convert to dictionary for serialization/storage"""
        return {
            'message': self.message,
            'category': self.category.value,
            'severity': self.severity.value,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details
        }
    
    def __str__(self):
        return f"{self.category.value.upper()} ({self.severity.name}): {self.message}"

class ErrorManager(QObject):
    """
    Centralized error management system.
    
    Handles:
    - Error logging to file
    - Error broadcasting to UI components
    - Error recovery strategies
    """
    # Signal emitted when new errors occur
    error_occurred = pyqtSignal(ErrorResponse)
    # Signal only for errors that might impact connection status
    connection_error_occurred = pyqtSignal(ErrorResponse)
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one error manager exists"""
        if cls._instance is None:
            cls._instance = super(ErrorManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        super().__init__()
        
        # Initialize error log
        self._setup_logging()
        
        # Recent errors list (keep last 100 errors)
        self._recent_errors = []
        self._max_recent_errors = 100
        
        # Error counts by category
        self._error_counts = {cat.value: 0 for cat in ErrorCategory}
        
        # Track connection-impacting categories (explicitly exclude OCR)
        self._connection_categories = [ErrorCategory.NETWORK, ErrorCategory.AUTH]
        
        self._initialized = True
    
    def _setup_logging(self):
        """Set up the logging system"""
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Current date for log file name
        current_date = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(log_dir, f'app_{current_date}.log')
        
        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            format=LOG_FORMAT,
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Create app logger
        self.logger = logging.getLogger('app')
        self.logger.info("Error manager initialized")
    
    def log_error(self, message, category=ErrorCategory.UNKNOWN, severity=ErrorSeverity.MEDIUM, 
                 error=None, details=None):
        """
        Log an error and emit the error signal.
        
        Args:
            message: Human-readable error message
            category: ErrorCategory enum value
            severity: ErrorSeverity enum value
            error: Original exception object, if available
            details: Dictionary with additional error details
            
        Returns:
            ErrorResponse: The created error response object
        """
        # Create standardized error response
        error_response = ErrorResponse(message, category, severity, error, details)
        
        # Add to recent errors and update counts
        self._recent_errors.append(error_response)
        if len(self._recent_errors) > self._max_recent_errors:
            self._recent_errors.pop(0)
            
        self._error_counts[error_response.category.value] += 1
        
        # Emit signal for UI components
        self.error_occurred.emit(error_response)
        
        # Check if this error might impact connection status
        # Explicitly exclude OCR errors
        if (category in self._connection_categories and 
            severity.value >= ErrorSeverity.MEDIUM.value and
            category != ErrorCategory.OCR):
            self.connection_error_occurred.emit(error_response)
        
        return error_response
    
    def get_recent_errors(self, limit=None, category=None, min_severity=None):
        """
        Get recent errors with optional filtering
        
        Args:
            limit: Maximum number of errors to return
            category: Filter by ErrorCategory
            min_severity: Only return errors with this severity or higher
            
        Returns:
            list: Filtered list of recent errors
        """
        filtered_errors = self._recent_errors
        
        # Apply category filter
        if category:
            filtered_errors = [e for e in filtered_errors 
                              if e.category == category]
        
        # Apply severity filter
        if min_severity:
            filtered_errors = [e for e in filtered_errors 
                              if e.severity.value >= min_severity.value]
        
        # Apply limit
        if limit and limit > 0:
            filtered_errors = filtered_errors[-limit:]
            
        return filtered_errors
    
    def get_error_count(self, category=None):
        """
        Get count of errors, optionally filtered by category
        
        Args:
            category: ErrorCategory to count, or None for total
            
        Returns:
            int: Error count
        """
        if category:
            return self._error_counts[category.value]
        else:
            return sum(self._error_counts.values())
            
    def clear_errors(self):
        """Clear the error history"""
        self._recent_errors = []
        self._error_counts = {cat.value: 0 for cat in ErrorCategory}
    
    @staticmethod
    def handle_exception(func):
        """
        Decorator for automatic error handling and reporting
        
        Example:
            @ErrorManager.handle_exception
            def some_function():
                # function body
        """
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get error manager instance
                error_manager = ErrorManager()
                
                # Determine error category based on exception type
                category = ErrorCategory.UNKNOWN
                if "timeout" in str(e).lower() or "connection" in str(e).lower():
                    category = ErrorCategory.NETWORK
                elif "database" in str(e).lower() or "sqlite" in str(e).lower():
                    category = ErrorCategory.DATABASE
                elif "authentication" in str(e).lower() or "authorization" in str(e).lower():
                    category = ErrorCategory.AUTH
                elif "api" in str(e).lower():
                    category = ErrorCategory.API
                
                # Log the error
                error_manager.log_error(
                    message=f"Error in {func.__name__}: {str(e)}",
                    category=category,
                    severity=ErrorSeverity.MEDIUM,
                    error=e,
                    details={
                        'function': func.__name__,
                        'args': str(args),
                        'kwargs': str(kwargs),
                        'traceback': traceback.format_exc()
                    }
                )
                
                # Re-raise if critical
                if isinstance(e, (SystemExit, KeyboardInterrupt)):
                    raise
                    
                # Return None to indicate failure
                return None
                
        return wrapper

def network_error(message, severity=ErrorSeverity.MEDIUM, error=None, details=None):
    """Helper function for network errors"""
    return ErrorManager().log_error(message, ErrorCategory.NETWORK, severity, error, details)

def database_error(message, severity=ErrorSeverity.MEDIUM, error=None, details=None):
    """Helper function for database errors"""
    return ErrorManager().log_error(message, ErrorCategory.DATABASE, severity, error, details)

def auth_error(message, severity=ErrorSeverity.MEDIUM, error=None, details=None):
    """Helper function for authentication errors"""
    return ErrorManager().log_error(message, ErrorCategory.AUTH, severity, error, details)

def api_error(message, severity=ErrorSeverity.MEDIUM, error=None, details=None):
    """Helper function for API errors"""
    return ErrorManager().log_error(message, ErrorCategory.API, severity, error, details)

def ui_error(message, severity=ErrorSeverity.MEDIUM, error=None, details=None):
    """Helper function for UI errors"""
    return ErrorManager().log_error(message, ErrorCategory.UI, severity, error, details)

def hardware_error(message, severity=ErrorSeverity.MEDIUM, error=None, details=None):
    """Helper function for hardware errors"""
    return ErrorManager().log_error(message, ErrorCategory.HARDWARE, severity, error, details)

def config_error(message, severity=ErrorSeverity.MEDIUM, error=None, details=None):
    """Helper function for configuration errors"""
    return ErrorManager().log_error(message, ErrorCategory.CONFIG, severity, error, details)

def system_error(message, severity=ErrorSeverity.MEDIUM, error=None, details=None):
    """Helper function for system errors"""
    return ErrorManager().log_error(message, ErrorCategory.SYSTEM, severity, error, details)

def generic_error(message, severity=ErrorSeverity.MEDIUM, error=None, details=None):
    """Helper function for uncategorized errors"""
    return ErrorManager().log_error(message, ErrorCategory.UNKNOWN, severity, error, details) 
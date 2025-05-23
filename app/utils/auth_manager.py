class AuthManager:
    """
    Singleton class for managing authentication information.
    Stores and provides access to the authentication token.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuthManager, cls).__new__(cls)
            cls._instance._access_token = None
            cls._instance._token_type = None
            cls._instance._username = None
            cls._instance._password = None
        return cls._instance
    
    @property
    def access_token(self):
        return self._access_token
    
    @access_token.setter
    def access_token(self, value):
        self._access_token = value
    
    @property
    def token_type(self):
        return self._token_type
    
    @token_type.setter
    def token_type(self, value):
        self._token_type = value
    
    @property
    def username(self):
        return self._username
    
    @username.setter
    def username(self, value):
        self._username = value
    
    @property
    def password(self):
        return self._password
    
    @password.setter
    def password(self, value):
        self._password = value
    
    @property
    def auth_header(self):
        """
        Returns the Authorization header with the token.
        """
        if self._access_token and self._token_type:
            return {
                "Authorization": f"{self._token_type} {self._access_token}"
            }
        return {}
    
    def clear(self):
        """
        Clear the stored token information.
        """
        self._access_token = None
        self._token_type = None
        # Don't clear credentials to allow reconnection
    
    def is_authenticated(self):
        """
        Check if user is authenticated.
        """
        return self._access_token is not None
    
    def has_stored_credentials(self):
        """
        Check if credentials are stored for potential reconnection.
        """
        return bool(self._username and self._password)
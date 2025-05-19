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
            cls._instance._refresh_token = None
            print("AuthManager instance created")
        return cls._instance
    
    @property
    def access_token(self):
        return self._access_token
    
    @access_token.setter
    def access_token(self, value):
        self._access_token = value
        print(f"Access token set: {'present' if value else 'empty'}")
    
    @property
    def token_type(self):
        return self._token_type
    
    @token_type.setter
    def token_type(self, value):
        self._token_type = value
        print(f"Token type set to: {value}")
    
    @property
    def username(self):
        return self._username
    
    @username.setter
    def username(self, value):
        self._username = value
        if value:
            print(f"Username set to: {value}")
    
    @property
    def password(self):
        return self._password
    
    @password.setter
    def password(self, value):
        self._password = value
        if value:
            print("Password set (value hidden)")
    
    @property
    def refresh_token(self):
        return self._refresh_token
    
    @refresh_token.setter
    def refresh_token(self, value):
        self._refresh_token = value
        print(f"Refresh token set: {'present' if value else 'empty'}")
    
    @property
    def auth_header(self):
        """
        Returns the Authorization header with the token.
        """
        if self._access_token and self._token_type:
            return {
                "Authorization": f"{self._token_type} {self._access_token}"
            }
        # If no token is available, show a helpful debug message
        print("WARNING: Auth header requested but no token available!")
        return {}
    
    def clear(self):
        """
        Clear the stored token information.
        """
        print("Clearing authentication token")
        self._access_token = None
        self._token_type = None
        self._refresh_token = None
        # Don't clear credentials to allow reconnection
    
    def is_authenticated(self):
        """
        Check if user is authenticated.
        """
        return self._access_token is not None
    
    def has_refresh_token(self):
        """
        Check if refresh token is available.
        """
        return self._refresh_token is not None
    
    def has_stored_credentials(self):
        """
        Check if credentials are stored for potential reconnection.
        """
        return bool(self._username and self._password)
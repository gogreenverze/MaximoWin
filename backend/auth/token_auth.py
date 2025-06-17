"""
Authentication module for Maximo OAuth.
"""
import os
import re
import json
import time
import pickle
import logging
import threading
import urllib.parse
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('token_auth')

class MaximoAuthManager:
    """Handles authentication with Maximo OAuth."""

    def __init__(self, base_url, client_id="MAXIMO", cache_dir=None):
        """Initialize the token manager.

        Args:
            base_url (str): The base URL of the Maximo instance.
            client_id (str): The client ID for OAuth authentication.
            cache_dir (str): Directory to cache tokens. If None, uses ~/.maximo_oauth.
        """
        self.base_url = base_url
        self.client_id = client_id
        self.username = None

        # Set up session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set up cache directory
        if cache_dir is None:
            self.cache_dir = os.path.expanduser("~/.maximo_oauth")
        else:
            self.cache_dir = cache_dir

        # Create cache directory if it doesn't exist
        self._cache_dir = os.path.join(self.cache_dir, re.sub(r'[^\w\-_]', '_', self.base_url))
        os.makedirs(self._cache_dir, exist_ok=True)

        # Initialize tokens
        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0

        # Cache for auth URLs
        self._cached_auth_urls = {}

        # Load tokens from cache
        self._load_tokens()

    def _load_tokens(self):
        """Load tokens from cache if available."""
        try:
            cache_file = os.path.join(self._cache_dir, 'token_cache.pkl')
            if os.path.exists(cache_file):
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)

                # Check if the cached data is for the same base URL
                if cached_data.get('base_url') == self.base_url:
                    # Check if the refresh token is still valid with a 5-minute safety margin
                    safety_margin = 300  # 5 minutes in seconds
                    if cached_data.get('expires_at', 0) > (time.time() + safety_margin):
                        logger.info("Loading tokens from cache")
                        self.access_token = cached_data.get('access_token')
                        self.refresh_token = cached_data.get('refresh_token')
                        self.expires_at = cached_data.get('expires_at')
                        self.username = cached_data.get('username')

                        # Verify the loaded token is actually valid
                        try:
                            verify_url = f"{self.base_url}/oslc/whoami"
                            response = self.session.head(
                                verify_url,
                                timeout=(3.05, 5),
                                allow_redirects=False
                            )

                            if 200 <= response.status_code < 400:
                                logger.info("Cached token verified as valid")
                                return
                            else:
                                logger.warning(f"Cached token invalid (status code: {response.status_code}), removing cache")
                                self._clear_token_cache()
                        except Exception as e:
                            logger.warning(f"Failed to verify cached token: {e}, removing cache")
                            self._clear_token_cache()
                    else:
                        logger.info("Cached tokens expired or too close to expiry, will need to login again")
                        self._clear_token_cache()
        except Exception as e:
            logger.warning(f"Error loading tokens from cache: {e}")

    def _clear_token_cache(self):
        """Clear the token cache file and reset token attributes."""
        try:
            cache_file = os.path.join(self._cache_dir, 'token_cache.pkl')
            if os.path.exists(cache_file):
                os.remove(cache_file)
                logger.info("Removed cached tokens")
        except Exception as e:
            logger.warning(f"Error removing cached tokens: {e}")

        # Reset token attributes
        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0

    def _save_tokens_to_cache(self):
        """Save tokens to cache for future use."""
        if not self.access_token or not self.refresh_token:
            logger.warning("No tokens to cache")
            return

        try:
            cache_data = {
                'base_url': self.base_url,
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_at': self.expires_at,
                'username': self.username,
                'cached_at': time.time()
            }

            cache_file = os.path.join(self._cache_dir, 'token_cache.pkl')
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)

            logger.info(f"Tokens cached successfully, expires at {datetime.fromtimestamp(self.expires_at)}")
        except Exception as e:
            logger.warning(f"Error caching tokens: {e}")

    def is_logged_in(self):
        """Check if the user is logged in and the session is valid."""
        # First check if we have valid tokens
        is_token_valid = self.access_token is not None and time.time() < (self.expires_at - 60)

        # If we have valid tokens, we're logged in
        if is_token_valid:
            return True

        # If we don't have valid tokens, check if we have a valid session
        # This handles users who authenticate with session cookies but don't get tokens
        if len(self.session.cookies) > 0:
            try:
                # Make a HEAD request to verify session is still valid
                verify_url = f"{self.base_url}/oslc/whoami"
                response = self.session.head(
                    verify_url,
                    timeout=(3.05, 5),  # Short timeout for quick verification
                    allow_redirects=False  # Don't follow redirects
                )

                # If we get 2xx or 3xx response, session is still valid
                if 200 <= response.status_code < 400:
                    logger.info("Session verified as valid through API check")
                    return True

                # If we get redirected to login page, session is invalid
                if response.status_code == 302 and 'login' in response.headers.get('Location', '').lower():
                    logger.warning("Session expired - redirected to login page")
                    return False

                # For other 3xx responses, we need to check where they redirect
                if 300 <= response.status_code < 400:
                    # Try a GET request with redirects to see if we end up at login page
                    try:
                        full_response = self.session.get(
                            verify_url,
                            timeout=(3.05, 10),
                            allow_redirects=True
                        )

                        # If we end up at login page, session is invalid
                        if 'login' in full_response.url.lower():
                            logger.warning("Session expired - redirected to login page")
                            return False

                        # Otherwise, session is probably valid
                        logger.info(f"Session verified through redirect chain (final URL: {full_response.url})")
                        return True
                    except Exception as e:
                        logger.warning(f"Error following redirect chain: {e}")
                        # Be conservative and assume session is invalid
                        return False

                # If we get an error response, session is invalid
                logger.warning(f"Session verification failed with status code: {response.status_code}")
                return False
            except Exception as e:
                logger.warning(f"Session verification request failed: {e}")
                return False

        # If we don't have tokens or cookies, we're not logged in
        return False

    def force_session_refresh(self):
        """Force a session refresh by clearing tokens and checking session validity."""
        logger.info("🔄 Forcing session refresh...")

        # Clear cached tokens to force fresh authentication
        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0

        # Check if session is still valid
        return self.is_logged_in()

    def refresh_token_if_needed(self):
        """Refresh token if it's close to expiry."""
        if self.access_token and self.expires_at:
            # Refresh if token expires within 5 minutes
            if time.time() > (self.expires_at - 300):
                logger.info("🔄 Token close to expiry, forcing refresh...")
                return self.force_session_refresh()
        return True

    def logout(self):
        """Clear the session and tokens."""
        self.session.cookies.clear()
        self._clear_token_cache()

        logger.info("Logged out successfully")
        return True

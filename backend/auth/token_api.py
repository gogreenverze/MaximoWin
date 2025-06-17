"""
API module for Maximo OAuth.
"""
import os
import json
import time
import logging
import threading
import pickle
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('token_api')

class MaximoApiManager:
    """Handles API calls with Maximo OAuth."""

    # Class-level cache for user profiles
    _profile_cache = {}
    _profile_cache_timestamp = 0
    _profile_cache_duration = 300  # 5 minutes in seconds

    def _extract_tokens_from_cookies(self):
        """Extract access and refresh tokens from cookies or response headers."""
        # Look for tokens in cookies
        for cookie in self.session.cookies:
            if cookie.name == 'x-access-token':
                self.access_token = cookie.value
                logger.info("Found access token in cookies")
            elif cookie.name == 'x-refresh-token':
                self.refresh_token = cookie.value
                logger.info("Found refresh token in cookies")

        # If we found tokens, set expiry time (default to 30 minutes if not specified)
        if self.access_token:
            # Try to parse JWT to get expiry time
            try:
                import base64
                import json

                # JWT tokens have 3 parts separated by dots
                token_parts = self.access_token.split('.')
                if len(token_parts) == 3:
                    # The second part contains the payload
                    payload = token_parts[1]
                    # Add padding if needed
                    payload += '=' * (4 - len(payload) % 4) if len(payload) % 4 else ''
                    # Decode the payload
                    decoded = base64.b64decode(payload)
                    payload_data = json.loads(decoded)

                    # Extract expiry time
                    if 'exp' in payload_data:
                        self.expires_at = payload_data['exp']
                        logger.info(f"Token expires at: {time.ctime(self.expires_at)}")
                    else:
                        # Default to 30 minutes
                        self.expires_at = time.time() + 1800
                else:
                    # Default to 30 minutes
                    self.expires_at = time.time() + 1800
            except Exception as e:
                logger.error(f"Error parsing JWT token: {e}")
                # Default to 30 minutes
                self.expires_at = time.time() + 1800
        else:
            logger.warning("No tokens found in cookies")

    def _verify_login(self):
        """Verify login by checking if we have a valid session."""
        # First check if we have tokens - most reliable method
        if self.access_token and self.refresh_token:
            logger.info("Login verified through tokens")
            return True

        # Next, check if we have cookies and verify with API call
        if len(self.session.cookies) > 0:
            logger.info("Found session cookies, verifying with API call")

            # Try to make a simple API call to verify the session is actually valid
            try:
                # Use a GET request with JSON parsing as the most reliable verification
                verify_url = f"{self.base_url}/oslc/whoami"
                response = self.session.get(
                    verify_url,
                    timeout=(3.05, 10),
                    headers={"Accept": "application/json"},
                    allow_redirects=True  # Follow redirects to see where we end up
                )

                # If we got redirected to login page, session is invalid
                if 'login' in response.url.lower() or 'auth' in response.url.lower():
                    logger.warning(f"Session verification failed - redirected to login page: {response.url}")
                    error_msg = "Login verification failed. Redirected to login page."
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                # If we got a 2xx status code, try to parse as JSON
                if 200 <= response.status_code < 300:
                    try:
                        # Try to parse as JSON - if successful, we're definitely logged in
                        user_data = response.json()
                        if user_data:
                            logger.info("Login verified with API call - got valid JSON response")
                            return True
                    except Exception as json_error:
                        logger.warning(f"API call returned non-JSON response: {json_error}")

                        # Check if response looks like an error page
                        if 'error' in response.text.lower() or 'invalid' in response.text.lower():
                            logger.warning("Session verification failed - error page detected")
                            error_msg = "Login verification failed. Error page detected."
                            logger.error(error_msg)
                            raise ValueError(error_msg)

                # If we got here, the verification is inconclusive
                logger.warning(f"Session verification inconclusive (status: {response.status_code})")
            except ValueError:
                # Re-raise ValueError exceptions from above
                raise
            except Exception as e:
                logger.warning(f"Error verifying session with API call: {e}")

        # If we don't have tokens or verified cookies, login failed
        error_msg = "Login verification failed. No valid session found."
        logger.error(error_msg)
        raise ValueError(error_msg)

    def _schedule_token_refresh(self):
        """Schedule a token refresh before the current token expires."""
        if not self.refresh_token or not self.expires_at:
            return

        # Calculate time until refresh (5 minutes before expiry)
        now = time.time()
        refresh_margin = 300  # 5 minutes in seconds
        time_until_refresh = max(0, self.expires_at - now - refresh_margin)

        if time_until_refresh <= 0:
            # Token is already expired or about to expire
            logger.info("Token is expired or about to expire, not scheduling refresh")
            return

        logger.info(f"Scheduling token refresh in {time_until_refresh:.1f} seconds")

        # Create a timer to refresh the token
        refresh_timer = threading.Timer(time_until_refresh, self._refresh_token)
        refresh_timer.daemon = True
        refresh_timer.start()

    def _refresh_token(self):
        """Refresh the access token using the refresh token."""
        logger.info("Attempting to refresh token...")

        try:
            # Try to make a real token refresh request to Maximo
            refresh_url = f"{self.base_url}/oslc/token"

            # Prepare refresh request with the refresh token
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }

            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id
            }

            # Make the refresh request
            response = self.session.post(
                refresh_url,
                headers=headers,
                data=data,
                timeout=(3.05, 15)
            )

            if response.status_code == 200:
                # Successfully refreshed token
                try:
                    token_data = response.json()
                    self.access_token = token_data.get("access_token")
                    new_refresh_token = token_data.get("refresh_token")
                    if new_refresh_token:
                        self.refresh_token = new_refresh_token

                    # Update expiry time
                    expires_in = token_data.get("expires_in", 1800)  # Default 30 minutes
                    self.expires_at = time.time() + expires_in

                    logger.info(f"Token refreshed successfully, expires at {datetime.fromtimestamp(self.expires_at)}")

                    # Save the refreshed tokens
                    self._save_tokens_to_cache()

                    # Schedule the next refresh
                    self._schedule_token_refresh()
                    return
                except Exception as e:
                    logger.error(f"Error parsing token refresh response: {e}")
            else:
                logger.warning(f"Token refresh failed with status code: {response.status_code}")

            # If we get here, the refresh failed - clear tokens and force re-login
            logger.warning("Token refresh failed, clearing tokens to force re-login")
            self._clear_token_cache()

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            # Clear tokens on error to force re-login
            self._clear_token_cache()

    def get_user_profile(self, use_mock=False, use_cache=True, force_refresh=False):
        """Fetch user profile data from Maximo with caching for lightning-fast retrieval.

        Args:
            use_mock (bool): Parameter kept for compatibility but not used.
                             All data comes from live Maximo API.
            use_cache (bool): Whether to use cached profile if available.
            force_refresh (bool): Whether to force a refresh of the cache.

        Returns:
            dict: User profile data with cleaned field names.
        """
        # Check if we're logged in
        if not self.is_logged_in():
            logger.error("Cannot fetch user profile: Not logged in")
            return None

        # Generate cache key based on username and base URL
        cache_key = f"{self.username}@{self.base_url}"

        # Check if we have a valid cached profile
        cache_valid = (
            cache_key in MaximoApiManager._profile_cache and
            time.time() - MaximoApiManager._profile_cache_timestamp < MaximoApiManager._profile_cache_duration
        )

        # Return cached profile if valid and not forcing refresh
        if use_cache and cache_valid and not force_refresh:
            logger.info("Using cached user profile (lightning-fast)")
            return MaximoApiManager._profile_cache[cache_key]

        try:
            # Make API call to fetch user profile data
            whoami_url = f"{self.base_url}/oslc/whoami"
            logger.info(f"Fetching user profile from {whoami_url}")

            # Use a shorter timeout for faster response
            response = self.session.get(
                whoami_url,
                timeout=(3.05, 10),  # Reduced timeout
                headers={"Accept": "application/json"},
                allow_redirects=True
            )

            # Check if we got redirected to login page
            if 'login' in response.url.lower():
                logger.error("Session expired during profile fetch - redirected to login page")
                return None

            # Check for successful response
            if response.status_code != 200:
                logger.error(f"Failed to fetch user profile. Status code: {response.status_code}")
                return None

            # Try to parse JSON response
            try:
                profile_data = response.json()
                logger.info("Successfully fetched user profile data")

                # Clean up the profile data by removing unnecessary prefixes
                cleaned_profile = self._clean_profile_data(profile_data)

                # Cache the cleaned profile
                MaximoApiManager._profile_cache[cache_key] = cleaned_profile
                MaximoApiManager._profile_cache_timestamp = time.time()

                # Also save to disk cache for persistence across sessions
                self._save_profile_to_cache(cleaned_profile)

                return cleaned_profile
            except Exception as e:
                logger.error(f"Error parsing user profile JSON: {e}")
                return None

        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")

            # Try to load from disk cache as fallback
            disk_cache = self._load_profile_from_cache()
            if disk_cache:
                logger.info("Using profile from disk cache as fallback")
                return disk_cache

            return None

    def _clean_profile_data(self, profile_data):
        """Clean up profile data by removing unnecessary prefixes and normalizing field names.

        Args:
            profile_data (dict): Raw profile data from Maximo API.

        Returns:
            dict: Cleaned profile data with consistent field names.
        """
        if not profile_data:
            return {}

        # Create a new dict for the cleaned data
        cleaned = {}

        # Process each key in the profile data
        for key, value in profile_data.items():
            # Remove 'spi:' prefix from keys
            if key.startswith('spi:'):
                clean_key = key[4:]  # Remove the 'spi:' prefix
            else:
                clean_key = key

            # Store with the cleaned key
            cleaned[clean_key] = value

        # Ensure we have both defaultSite and insertSite in standard format
        if 'defaultSite' not in cleaned and 'defaultsite' in cleaned:
            cleaned['defaultSite'] = cleaned['defaultsite']

        if 'insertSite' not in cleaned and 'insertsite' in cleaned:
            cleaned['insertSite'] = cleaned['insertsite']

        return cleaned

    def _save_profile_to_cache(self, profile_data):
        """Save profile data to disk cache for persistence across sessions.

        Args:
            profile_data (dict): Profile data to cache.
        """
        if not profile_data or not self.username:
            return

        try:
            # Create a cache file path based on username
            cache_file = os.path.join(self._cache_dir, f'profile_{self.username}.pkl')

            # Save the profile data along with a timestamp
            cache_data = {
                'profile': profile_data,
                'timestamp': time.time(),
                'username': self.username,
                'base_url': self.base_url
            }

            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)

            logger.info(f"Profile data cached to disk for {self.username}")
        except Exception as e:
            logger.warning(f"Error saving profile to disk cache: {e}")

    def _clear_profile_cache(self, username: str = None):
        """Clear profile cache for a specific user or current user.

        Args:
            username: Username to clear cache for (defaults to current user)
        """
        target_username = username or self.username
        if not target_username:
            logger.warning("Cannot clear profile cache - no username provided")
            return

        try:
            # Clear memory cache
            if hasattr(self, '_profile_cache') and target_username in self._profile_cache:
                del self._profile_cache[target_username]
                logger.info(f"✅ TOKEN API: Memory profile cache cleared for {target_username}")

            # Clear disk cache
            cache_file = os.path.join(self._cache_dir, f'profile_{target_username}.pkl')
            if os.path.exists(cache_file):
                os.remove(cache_file)
                logger.info(f"✅ TOKEN API: Disk profile cache cleared for {target_username}")

        except Exception as e:
            logger.warning(f"Error clearing profile cache for {target_username}: {e}")

    def _load_profile_from_cache(self):
        """Load profile data from disk cache if available and not too old.

        Returns:
            dict: Cached profile data or None if not available.
        """
        if not self.username:
            return None

        try:
            # Get the cache file path
            cache_file = os.path.join(self._cache_dir, f'profile_{self.username}.pkl')

            # Check if the cache file exists
            if not os.path.exists(cache_file):
                return None

            # Load the cache data
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)

            # Check if the cache is for the current user and base URL
            if (cache_data.get('username') == self.username and
                cache_data.get('base_url') == self.base_url):

                # Check if the cache is not too old (30 minutes max)
                if time.time() - cache_data.get('timestamp', 0) < 1800:  # 30 minutes
                    logger.info(f"Loaded profile from disk cache for {self.username}")
                    return cache_data.get('profile')

            return None
        except Exception as e:
            logger.warning(f"Error loading profile from disk cache: {e}")
            return None

    def get_api_key(self):
        """Generate or retrieve an API key for the current user.

        This method uses the authenticated session to request an API key
        from the Maximo API. If successful, it returns the API key.

        Returns:
            str: The API key, or None if retrieval failed.
        """
        # Check if we're logged in
        if not self.is_logged_in():
            logger.error("Cannot get API key: Not logged in")
            return None

        logger.info("Attempting to get API key from Maximo")

        try:
            # First try to get existing API keys
            apikey_url = f"{self.base_url}/oslc/apikey"

            # Make the API request to get API key
            response = self.session.get(
                apikey_url,
                headers={"Accept": "application/json"},
                timeout=(3.05, 15)
            )

            # Check if we got a successful response
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info("Successfully retrieved API key data")

                    # Check if we have any API keys
                    if isinstance(data, list) and len(data) > 0:
                        # Use the first API key
                        api_key = data[0].get('apikey')
                        if api_key:
                            logger.info("Found existing API key")
                            return api_key

                    # If we don't have any API keys, create a new one
                    logger.info("No existing API keys found, creating a new one")
                except Exception as e:
                    logger.warning(f"Error parsing API key response: {e}")

            # If we get here, we need to create a new API key
            logger.info("Creating new API key")

            # Prepare headers for API key creation
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            # Prepare request body
            request_body = {
                "description": f"Auto-generated API key for {self.username} - {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "expiration": None  # No expiration
            }

            # Make the API request to create API key
            response = self.session.post(
                apikey_url,
                headers=headers,
                json=request_body,
                timeout=(3.05, 15)
            )

            # Check if we got a successful response
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    logger.info("Successfully created new API key")

                    # Extract API key from response
                    if 'apikey' in data:
                        return data['apikey']
                    else:
                        logger.warning(f"API key not found in response. Response keys: {data.keys()}")
                        return None
                except Exception as e:
                    logger.error(f"Error parsing API key creation response: {e}")
                    return None
            else:
                logger.error(f"Failed to create API key. Status code: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting API key: {e}")
            return None

"""
Login module for Maximo OAuth.
"""
import re
import time
import logging
import urllib.parse
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('token_login')

class MaximoLoginManager:
    """Handles login with Maximo OAuth."""
    
    def login(self, username, password):
        """Login to Maximo with username and password.
        
        Args:
            username (str): The username to login with.
            password (str): The password to login with.
            
        Returns:
            bool: True if login was successful, False otherwise.
        """
        # If already logged in, return True
        if self.is_logged_in():
            logger.info(f"Already logged in as {self.username}, using existing tokens")
            return True
            
        # Store username for future use
        self.username = username
        
        # Step 1: Access the main page to get redirected to the auth page
        timeout = (3.05, 15)  # Connect timeout, Read timeout
        auth_url = self._cached_auth_urls.get(self.base_url)
        
        if not auth_url:
            try:
                logger.info(f"Logging in to {self.base_url} as {username}...")
                response = self.session.get(
                    self.base_url,
                    allow_redirects=True,
                    timeout=timeout
                )
                
                if response.status_code != 200:
                    error_msg = f"Failed to access main page. Status code: {response.status_code}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                    
                logger.info(f"Current URL after redirects: {response.url}")
                
                # Look for OAuth authorization URL in the response
                # Check if we were redirected to an auth page
                if 'auth' in response.url or 'login' in response.url:
                    auth_url = response.url
                    logger.info(f"Redirected to authentication URL: {auth_url}")
                else:
                    # Try to extract the auth URL from the page content
                    oauth_url_pattern = re.compile(r'(https://[^"\']+/oauth[^"\']+)')
                    match = oauth_url_pattern.search(response.text)
                    if match:
                        auth_url = match.group(1)
                        logger.info(f"Found OAuth URL in page: {auth_url}")
                    else:
                        # Look for authorization endpoint in the HTML
                        oidc_pattern = re.compile(r'(https://[^"\']+/oidc[^"\']+)')
                        match = oidc_pattern.search(response.text)
                        if match:
                            auth_url = match.group(1)
                            logger.info(f"Found OIDC URL in page: {auth_url}")
                
                if not auth_url:
                    # Check if we can find the auth URL in the WASReqURL cookie
                    for cookie in self.session.cookies:
                        if cookie.name == 'WASReqURL':
                            auth_url = urllib.parse.unquote(cookie.value)
                            if not auth_url.startswith('http'):
                                # Try to reconstruct the full URL
                                auth_domain = re.match(r'(https://[^/]+)', self.base_url).group(1)
                                auth_url = auth_domain + auth_url
                            logger.info(f"Found auth URL in WASReqURL cookie: {auth_url}")
                            break
                            
            except requests.exceptions.Timeout:
                logger.warning("Timeout accessing main page, trying default auth URLs")
                # If timeout, try some common auth URLs based on the base URL
                base_domain = re.match(r'(https://[^/]+)', self.base_url)
                if base_domain:
                    domain = base_domain.group(1)
                    # Try common auth paths
                    for path in ['/oidc/endpoint/MaximoAppSuite/authorize', '/oauth/authorize']:
                        auth_url = domain + path
                        logger.info(f"Trying default auth URL: {auth_url}")
                        try:
                            auth_response = self.session.get(auth_url, timeout=timeout)
                            if auth_response.status_code == 200:
                                logger.info(f"Default auth URL {auth_url} is accessible")
                                break
                        except:
                            continue
        
        if not auth_url:
            error_msg = "Could not find authentication URL. Authentication flow cannot continue."
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Cache the auth URL for future use
        self._cached_auth_urls[self.base_url] = auth_url
        
        # Step 2: Access the auth URL to get the login form
        try:
            auth_response = self.session.get(auth_url, allow_redirects=True, timeout=(3.05, 15))
            
            if auth_response.status_code != 200:
                error_msg = f"Failed to access auth URL. Status code: {auth_response.status_code}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        except requests.exceptions.Timeout:
            error_msg = f"Timeout accessing auth URL: {auth_url}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Step 3: Find login endpoint and submit credentials
        login_url = None
        login_success = False
        
        # Try to extract the domain from the current URL
        domain_match = re.match(r'(https://[^/]+)', auth_response.url)
        if domain_match:
            auth_domain = domain_match.group(1)
            
            # Try common login endpoints
            login_endpoints = [
                '/j_security_check',
                '/login',  # Move this up in priority
                '/oidc/endpoint/MaximoAppSuite/login',
                '/idaas/mtfim/sps/authsvc'
            ]
            
            # Prepare login data with common field names
            login_data = {
                'username': username,
                'j_username': username,
                'email': username,
                'password': password,
                'j_password': password
            }
            
            # Try each endpoint until one works
            for endpoint in login_endpoints:
                login_url = auth_domain + endpoint
                logger.info(f"Trying login endpoint: {login_url}")
                
                try:
                    login_response = self.session.post(
                        login_url,
                        data=login_data,
                        allow_redirects=True,
                        timeout=(3.05, 15)
                    )
                    logger.info(f"Login response status: {login_response.status_code}")
                    
                    # If we got redirected back to the main application, login might be successful
                    if self.base_url in login_response.url:
                        logger.info("Redirected back to main application. Login might be successful.")
                        login_success = True
                        break
                        
                    # Special case for j_security_check - it might be successful even with a 200 response
                    if endpoint == '/j_security_check':
                        # Check if we have cookies, which would indicate successful authentication
                        if len(self.session.cookies) > 0:
                            logger.info("j_security_check login appears successful based on cookies")
                            
                            # Try to verify the login with a quick API call
                            try:
                                verify_url = f"{self.base_url}/oslc/whoami"
                                verify_response = self.session.head(
                                    verify_url,
                                    timeout=(3.05, 5),
                                    allow_redirects=False
                                )
                                
                                if 200 <= verify_response.status_code < 300:
                                    # Direct success - definitely logged in
                                    logger.info(f"Login verified with API call (status: {verify_response.status_code})")
                                    login_success = True
                                    break
                                elif verify_response.status_code == 302:
                                    # Redirect - need to check where it's redirecting to
                                    redirect_url = verify_response.headers.get('Location', '')
                                    if 'login' in redirect_url.lower() or 'auth' in redirect_url.lower():
                                        # Redirecting to login page - authentication failed
                                        logger.warning(f"Login verification failed - redirected to login page: {redirect_url}")
                                        continue  # Try next endpoint
                                    else:
                                        # Redirecting somewhere else - might be successful
                                        logger.info(f"Login appears successful - redirected to: {redirect_url}")
                                        
                                        # Make a full GET request to verify
                                        try:
                                            full_verify = self.session.get(
                                                verify_url,
                                                timeout=(3.05, 10),
                                                allow_redirects=True
                                            )
                                            
                                            # Check if we ended up at login page
                                            if 'login' in full_verify.url.lower() or 'auth' in full_verify.url.lower():
                                                logger.warning(f"Login verification failed - ended at login page: {full_verify.url}")
                                                continue  # Try next endpoint
                                            
                                            # Try to parse response as JSON to verify it's valid
                                            try:
                                                _ = full_verify.json()
                                                logger.info("Login verified - got valid JSON response")
                                                login_success = True
                                                break
                                            except:
                                                # Not JSON - check if it looks like an error page
                                                if 'error' in full_verify.text.lower() or 'invalid' in full_verify.text.lower():
                                                    logger.warning("Login verification failed - error page detected")
                                                    continue  # Try next endpoint
                                                
                                                # Otherwise, assume success
                                                logger.info("Login appears successful based on redirect chain")
                                                login_success = True
                                                break
                                        except Exception as e:
                                            logger.warning(f"Error following redirect chain: {e}")
                                            # Don't assume success
                                else:
                                    logger.warning(f"Login verification failed with status code: {verify_response.status_code}")
                            except Exception as e:
                                logger.warning(f"Error verifying login: {e}")
                            
                            # Don't automatically consider it successful just because we have cookies
                            # Only set login_success to True if we've explicitly verified it above
                    
                    # If we're still on the login page, try the next endpoint
                    if 'login' in login_response.url.lower() or 'auth' in login_response.url.lower():
                        continue
                    
                    # If we got here, we might have logged in successfully
                    login_success = True
                    break
                except Exception as e:
                    logger.error(f"Error trying endpoint {endpoint}: {e}")
                    continue
        else:
            error_msg = "Could not determine auth domain. Authentication flow cannot continue."
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        if not login_success:
            error_msg = "Failed to login with any of the known endpoints."
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Step 4: Extract tokens from cookies or response
        self._extract_tokens_from_cookies()
        
        # Step 5: Verify login by checking for cookies/tokens
        self._verify_login()
        
        # Step 6: Cache the tokens for future use
        self._save_tokens_to_cache()
        
        # Step 7: Schedule token refresh before expiry
        self._schedule_token_refresh()
        
        logger.info("Login successful!")
        return True

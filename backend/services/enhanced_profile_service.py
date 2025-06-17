"""
Enhanced Profile Service for Maximo OAuth.
Optimized profile data retrieval with intelligent caching and performance monitoring.
"""
import os
import json
import time
import logging
import pickle
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('enhanced_profile_service')

class EnhancedProfileService:
    """
    Optimized profile service that consolidates all profile data retrieval logic
    with intelligent caching and performance monitoring.
    """

    # Class-level cached default profile template (performance optimization)
    DEFAULT_PROFILE_TEMPLATE = {
        "firstName": "",
        "lastName": "",
        "displayName": "",
        "personid": "",
        "userName": "",
        "loginID": "",
        "loginUserName": "",
        "email": "",
        "country": "",
        "stateprovince": "",
        "phone": "",
        "primaryPhone": "",
        "timezone": "",
        "systimezone": "UTC",
        "baseLang": "EN",
        "baseCurrency": "USD",
        "baseCalendar": "gregorian",
        "dateformat": "M/d/yy",
        "canUseInactiveSites": "False",
        "defaultStoreroom": "",
        "defaultRepairSite": "None",
        "defaultRepairFacility": "None",
        "defaultOrg": "",
        "defaultSiteDescription": "",
        "defaultStoreroomSite": "None",
        "insertSite": "",
        "defaultSite": ""
    }

    # Class-level caches for performance
    _profile_cache = {}
    _profile_cache_timestamp = {}
    _session_validation_cache = {}
    _session_validation_timestamp = {}
    _sites_cache = {}
    _sites_cache_timestamp = {}

    # Cache configuration
    PROFILE_CACHE_DURATION = 300  # 5 minutes
    SESSION_CACHE_DURATION = 30   # 30 seconds for session validation
    SITES_CACHE_DURATION = 600    # 10 minutes for sites

    # Performance monitoring
    _performance_stats = {
        'total_requests': 0,
        'cache_hits': 0,
        'api_calls': 0,
        'average_response_time': 0.0,
        'last_reset': time.time()
    }

    def __init__(self, token_manager, cache_dir=None):
        """
        Initialize the enhanced profile service.

        Args:
            token_manager: The Maximo token manager instance
            cache_dir: Directory for disk cache (optional)
        """
        self.token_manager = token_manager
        self.cache_dir = cache_dir or os.path.expanduser('~/.maximo_enhanced_cache')
        self._ensure_cache_dir()
        self._lock = threading.RLock()  # Thread-safe operations

    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create cache directory: {e}")
            self.cache_dir = None

    def _get_cache_key(self, username: str, base_url: str) -> str:
        """Generate optimized cache key."""
        return f"{username}@{hash(base_url)}"  # Use hash for shorter keys

    def _is_cache_valid(self, cache_key: str, cache_type: str) -> bool:
        """Check if cache entry is still valid."""
        timestamp_cache = getattr(self, f'_{cache_type}_cache_timestamp', {})
        duration = getattr(self, f'{cache_type.upper()}_CACHE_DURATION', 300)

        if cache_key not in timestamp_cache:
            return False

        return time.time() - timestamp_cache[cache_key] < duration

    def _update_performance_stats(self, response_time: float, cache_hit: bool, api_call: bool):
        """Update performance monitoring statistics."""
        with self._lock:
            stats = self._performance_stats
            stats['total_requests'] += 1

            if cache_hit:
                stats['cache_hits'] += 1
            if api_call:
                stats['api_calls'] += 1

            # Update average response time using exponential moving average
            alpha = 0.1  # Smoothing factor
            if stats['average_response_time'] == 0:
                stats['average_response_time'] = response_time
            else:
                stats['average_response_time'] = (
                    alpha * response_time +
                    (1 - alpha) * stats['average_response_time']
                )

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        with self._lock:
            stats = self._performance_stats.copy()
            stats['cache_hit_rate'] = (
                stats['cache_hits'] / max(stats['total_requests'], 1) * 100
            )
            stats['uptime_seconds'] = time.time() - stats['last_reset']
            return stats

    def reset_performance_stats(self):
        """Reset performance statistics."""
        with self._lock:
            self._performance_stats = {
                'total_requests': 0,
                'cache_hits': 0,
                'api_calls': 0,
                'average_response_time': 0.0,
                'last_reset': time.time()
            }

    def is_session_valid(self, force_check: bool = False) -> bool:
        """
        Optimized session validation with caching.

        Args:
            force_check: Force a fresh validation check

        Returns:
            bool: True if session is valid
        """
        start_time = time.time()

        if not self.token_manager:
            return False

        # Check if we have a valid token first (fastest check)
        if hasattr(self.token_manager, 'access_token') and self.token_manager.access_token:
            if hasattr(self.token_manager, 'expires_at') and time.time() < (self.token_manager.expires_at - 60):
                self._update_performance_stats(time.time() - start_time, True, False)
                return True

        # Use cached validation result if available and not forcing check
        cache_key = f"session_{getattr(self.token_manager, 'username', 'unknown')}"
        if not force_check and self._is_cache_valid(cache_key, 'session_validation'):
            cached_result = self._session_validation_cache.get(cache_key, False)
            self._update_performance_stats(time.time() - start_time, True, False)
            return cached_result

        # Perform actual session validation
        try:
            is_valid = self.token_manager.is_logged_in()

            # Cache the result
            with self._lock:
                self._session_validation_cache[cache_key] = is_valid
                self._session_validation_timestamp[cache_key] = time.time()

            self._update_performance_stats(time.time() - start_time, False, True)
            return is_valid

        except Exception as e:
            logger.warning(f"Session validation failed: {e}")
            self._update_performance_stats(time.time() - start_time, False, True)
            return False

    def _clean_profile_data(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimized profile data cleaning with minimal processing.

        Args:
            profile_data: Raw profile data from Maximo API

        Returns:
            dict: Cleaned profile data with consistent field names
        """
        if not profile_data:
            return {}

        # Use dictionary comprehension for better performance
        cleaned = {
            key[4:] if key.startswith('spi:') else key: value
            for key, value in profile_data.items()
        }

        # Ensure standard field names exist (minimal processing)
        if 'defaultSite' not in cleaned and 'defaultsite' in cleaned:
            cleaned['defaultSite'] = cleaned['defaultsite']

        if 'insertSite' not in cleaned and 'insertsite' in cleaned:
            cleaned['insertSite'] = cleaned['insertsite']

        return cleaned

    def _save_profile_to_disk_cache(self, profile_data: Dict[str, Any], username: str):
        """
        Save profile data to disk cache for persistence.

        Args:
            profile_data: Profile data to cache
            username: Username for cache file naming
        """
        if not profile_data or not username or not self.cache_dir:
            return

        try:
            cache_file = os.path.join(self.cache_dir, f'enhanced_profile_{username}.pkl')
            cache_data = {
                'profile': profile_data,
                'timestamp': time.time(),
                'username': username,
                'base_url': getattr(self.token_manager, 'base_url', '')
            }

            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)

            logger.debug(f"Profile cached to disk for {username}")
        except Exception as e:
            logger.warning(f"Error saving profile to disk cache: {e}")

    def _load_profile_from_disk_cache(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Load profile data from disk cache if available and valid.

        Args:
            username: Username to load cache for

        Returns:
            dict: Cached profile data or None if not available
        """
        if not username or not self.cache_dir:
            return None

        try:
            cache_file = os.path.join(self.cache_dir, f'enhanced_profile_{username}.pkl')

            if not os.path.exists(cache_file):
                return None

            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)

            # Validate cache data
            if (cache_data.get('username') == username and
                cache_data.get('base_url') == getattr(self.token_manager, 'base_url', '') and
                time.time() - cache_data.get('timestamp', 0) < 1800):  # 30 minutes max

                logger.debug(f"Loaded profile from disk cache for {username}")
                return cache_data.get('profile')

            return None
        except Exception as e:
            logger.warning(f"Error loading profile from disk cache: {e}")
            return None

    def get_user_profile(self, username: str = None, use_cache: bool = True,
                        force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Optimized profile retrieval with intelligent caching.

        Args:
            username: Username to get profile for (defaults to current user)
            use_cache: Whether to use cached data
            force_refresh: Force a fresh API call

        Returns:
            dict: User profile data or None if unavailable
        """
        start_time = time.time()

        # Validate session first
        if not self.is_session_valid():
            logger.error("Cannot fetch user profile: Not logged in")
            self._update_performance_stats(time.time() - start_time, False, False)
            return None

        # Get username from token manager if not provided
        if not username:
            username = getattr(self.token_manager, 'username', '')
            if not username:
                logger.error("Cannot determine username for profile fetch")
                self._update_performance_stats(time.time() - start_time, False, False)
                return None

        # Generate cache key
        base_url = getattr(self.token_manager, 'base_url', '')
        cache_key = self._get_cache_key(username, base_url)

        # Check memory cache first (fastest)
        if use_cache and not force_refresh and self._is_cache_valid(cache_key, 'profile'):
            cached_profile = self._profile_cache.get(cache_key)
            if cached_profile:
                logger.info(f"✅ ENHANCED: Using memory cached profile (ultra-fast: {time.time() - start_time:.3f}s)")
                self._update_performance_stats(time.time() - start_time, True, False)
                return cached_profile

        # Check disk cache if memory cache miss
        if use_cache and not force_refresh:
            disk_cached = self._load_profile_from_disk_cache(username)
            if disk_cached:
                # Store in memory cache for next time
                with self._lock:
                    self._profile_cache[cache_key] = disk_cached
                    self._profile_cache_timestamp[cache_key] = time.time()

                logger.info(f"✅ ENHANCED: Using disk cached profile (fast: {time.time() - start_time:.3f}s)")
                self._update_performance_stats(time.time() - start_time, True, False)
                return disk_cached

        # Perform single optimized API call
        try:
            whoami_url = f"{base_url}/oslc/whoami"
            logger.info(f"🔄 ENHANCED: Fetching fresh profile from {whoami_url}")

            response = self.token_manager.session.get(
                whoami_url,
                timeout=(3.05, 8),  # Optimized timeout
                headers={"Accept": "application/json"},
                allow_redirects=True
            )

            # Validate response
            if 'login' in response.url.lower():
                logger.error("Session expired during profile fetch")
                self._update_performance_stats(time.time() - start_time, False, True)
                return None

            if response.status_code != 200:
                logger.error(f"Profile fetch failed. Status: {response.status_code}")
                self._update_performance_stats(time.time() - start_time, False, True)
                return None

            # Parse and clean profile data
            profile_data = response.json()
            cleaned_profile = self._clean_profile_data(profile_data)

            # Cache the result in both memory and disk
            with self._lock:
                self._profile_cache[cache_key] = cleaned_profile
                self._profile_cache_timestamp[cache_key] = time.time()

            self._save_profile_to_disk_cache(cleaned_profile, username)

            api_time = time.time() - start_time
            logger.info(f"✅ ENHANCED: Fresh profile fetched successfully ({api_time:.3f}s)")
            self._update_performance_stats(api_time, False, True)
            return cleaned_profile

        except Exception as e:
            logger.error(f"Error fetching profile: {e}")

            # Try disk cache as last resort
            disk_fallback = self._load_profile_from_disk_cache(username)
            if disk_fallback:
                logger.info("Using stale disk cache as fallback")
                self._update_performance_stats(time.time() - start_time, True, True)
                return disk_fallback

            self._update_performance_stats(time.time() - start_time, False, True)
            return None

    def get_available_sites(self, use_cache: bool = True, force_refresh: bool = False) -> list:
        """
        Optimized sites retrieval with intelligent caching.

        Args:
            use_cache: Whether to use cached data
            force_refresh: Force a fresh API call

        Returns:
            list: Available sites data
        """
        start_time = time.time()

        if not self.is_session_valid():
            logger.error("Cannot fetch sites: Not logged in")
            self._update_performance_stats(time.time() - start_time, False, False)
            return []

        username = getattr(self.token_manager, 'username', '')
        base_url = getattr(self.token_manager, 'base_url', '')
        cache_key = f"sites_{self._get_cache_key(username, base_url)}"

        # Check memory cache first
        if use_cache and not force_refresh and self._is_cache_valid(cache_key, 'sites'):
            cached_sites = self._sites_cache.get(cache_key, [])
            if cached_sites:
                logger.info(f"✅ ENHANCED: Using cached sites (ultra-fast: {time.time() - start_time:.3f}s)")
                self._update_performance_stats(time.time() - start_time, True, False)
                return cached_sites

        # Try to get sites from site access service first (most accurate)
        try:
            user_profile = self.get_user_profile(username, use_cache=True)
            person_id = user_profile.get('personid', '') if user_profile else ''

            if person_id:
                # Import here to avoid circular imports
                from backend.services.site_access_service import SiteAccessService

                logger.info(f"🔄 ENHANCED: Fetching sites from site access service for person: {person_id}")
                site_auth_data = SiteAccessService.get_sites_data(person_id)

                if site_auth_data and len(site_auth_data) > 0:
                    # Convert site access format to our format
                    unique_sites = {}
                    for site in site_auth_data:
                        siteid = site.get('Site ID', '')
                        if siteid:
                            unique_sites[siteid] = {
                                'siteid': siteid,
                                'description': f"{siteid} - {site.get('Organization', siteid)}"
                            }

                    # Add default site if not already present
                    default_site = user_profile.get('defaultSite', '') if user_profile else ''
                    if default_site and default_site not in unique_sites:
                        unique_sites[default_site] = {
                            'siteid': default_site,
                            'description': user_profile.get('defaultSiteDescription', default_site)
                        }

                    if len(unique_sites) > 0:
                        result = sorted(list(unique_sites.values()), key=lambda x: x.get('siteid', ''))

                        # Cache the result
                        with self._lock:
                            self._sites_cache[cache_key] = result
                            self._sites_cache_timestamp[cache_key] = time.time()

                        site_auth_time = time.time() - start_time
                        logger.info(f"✅ ENHANCED: Sites from site access service ({len(result)} sites, {site_auth_time:.3f}s)")
                        self._update_performance_stats(site_auth_time, False, False)
                        return result

        except Exception as e:
            logger.warning(f"Error getting sites from site access service: {e}")

        # Fallback: Try to get sites from user profile basic data
        try:
            user_profile = self.get_user_profile(username, use_cache=True)
            if user_profile:
                unique_sites = {}

                # Extract sites from profile
                default_site = user_profile.get('defaultSite', '')
                insert_site = user_profile.get('insertSite', '')

                if default_site:
                    unique_sites[default_site] = {
                        'siteid': default_site,
                        'description': user_profile.get('defaultSiteDescription', default_site)
                    }

                if insert_site and insert_site != default_site:
                    unique_sites[insert_site] = {
                        'siteid': insert_site,
                        'description': insert_site
                    }

                if len(unique_sites) > 0:
                    # Store profile sites as fallback
                    profile_sites = sorted(list(unique_sites.values()), key=lambda x: x.get('siteid', ''))
                    logger.info(f"🔄 ENHANCED: Using profile fallback sites ({len(profile_sites)} sites)")
                else:
                    profile_sites = []

        except Exception as e:
            logger.warning(f"Error extracting sites from profile: {e}")
            profile_sites = []

        # Fallback to API call if profile doesn't have enough sites
        try:
            sites_url = f"{base_url}/oslc/sites"
            logger.info(f"🔄 ENHANCED: Fetching sites from API: {sites_url}")

            response = self.token_manager.session.get(
                sites_url,
                timeout=(3.05, 8),
                headers={"Accept": "application/json"},
                allow_redirects=True
            )

            if response.status_code == 200:
                sites_data = response.json()

                # Process sites data and merge with profile sites
                unique_sites = {}

                # Add profile sites first (if any)
                if 'profile_sites' in locals():
                    for site in profile_sites:
                        unique_sites[site['siteid']] = site

                # Add API sites
                if isinstance(sites_data, dict) and 'member' in sites_data:
                    for site in sites_data['member']:
                        siteid = site.get('siteid')
                        if siteid and siteid not in unique_sites:
                            unique_sites[siteid] = {
                                'siteid': siteid,
                                'description': site.get('description', siteid)
                            }

                # Convert to sorted list
                sites_list = sorted(list(unique_sites.values()), key=lambda x: x.get('siteid', ''))

                # Cache the result
                with self._lock:
                    self._sites_cache[cache_key] = sites_list
                    self._sites_cache_timestamp[cache_key] = time.time()

                api_time = time.time() - start_time
                logger.info(f"✅ ENHANCED: Sites from API + profile ({len(sites_list)} sites, {api_time:.3f}s)")
                self._update_performance_stats(api_time, False, True)
                return sites_list

        except Exception as e:
            logger.warning(f"Error fetching sites from API: {e}")

        # Return empty list if all methods fail
        self._update_performance_stats(time.time() - start_time, False, True)
        return []

    def build_complete_profile(self, session_data: Dict[str, Any] = None) -> Tuple[Dict[str, Any], list]:
        """
        Build a complete profile with all required fields and available sites.

        Args:
            session_data: Optional session data for fallback values

        Returns:
            tuple: (complete_profile_dict, available_sites_list)
        """
        start_time = time.time()

        # Get user profile
        user_profile = self.get_user_profile()

        if not user_profile and session_data:
            # Create minimal profile from session data
            username = session_data.get('username', '')
            user_profile = {
                "firstName": session_data.get('first_name', ''),
                "lastName": session_data.get('last_name', ''),
                "displayName": username,
                "userName": username,
                "loginUserName": username,
                "defaultSite": session_data.get('default_site', ''),
                "insertSite": session_data.get('insert_site', '')
            }
            logger.info("✅ ENHANCED: Using session fallback profile")

        # Use cached template and merge efficiently
        complete_profile = self.DEFAULT_PROFILE_TEMPLATE.copy()

        if user_profile:
            # Update username fields from session if available
            if session_data and session_data.get('username'):
                complete_profile['userName'] = session_data['username']
                complete_profile['loginUserName'] = session_data['username']

            # Merge user profile data (only update existing keys for performance)
            for key, value in user_profile.items():
                if key in complete_profile or key not in self.DEFAULT_PROFILE_TEMPLATE:
                    complete_profile[key] = value

        # Get available sites
        available_sites = self.get_available_sites()

        # Ensure current sites are in the available sites list
        if available_sites and user_profile:
            self._ensure_current_sites_in_list(complete_profile, available_sites)

        total_time = time.time() - start_time
        logger.info(f"✅ ENHANCED: Complete profile built ({total_time:.3f}s)")

        return complete_profile, available_sites

    def _ensure_current_sites_in_list(self, profile: Dict[str, Any], sites_list: list):
        """
        Ensure current default and insert sites are in the available sites list.

        Args:
            profile: User profile data
            sites_list: List of available sites (modified in place)
        """
        default_site = profile.get('defaultSite', '')
        insert_site = profile.get('insertSite', '')

        # Create a set of existing site IDs for O(1) lookup
        existing_sites = {site.get('siteid') for site in sites_list}

        # Add missing sites
        if default_site and default_site not in existing_sites:
            sites_list.append({
                'siteid': default_site,
                'description': profile.get('defaultSiteDescription', default_site)
            })

        if insert_site and insert_site not in existing_sites:
            sites_list.append({
                'siteid': insert_site,
                'description': insert_site
            })

        # Re-sort if we added sites
        if (default_site and default_site not in existing_sites) or \
           (insert_site and insert_site not in existing_sites):
            sites_list.sort(key=lambda x: x.get('siteid', ''))

    def clear_cache(self, cache_type: str = 'all'):
        """
        Clear specified cache type.

        Args:
            cache_type: Type of cache to clear ('profile', 'sites', 'session', 'all')
        """
        with self._lock:
            if cache_type in ['profile', 'all']:
                self._profile_cache.clear()
                self._profile_cache_timestamp.clear()
                logger.info("✅ ENHANCED PROFILE: Profile cache cleared")

            if cache_type in ['sites', 'all']:
                self._sites_cache.clear()
                self._sites_cache_timestamp.clear()
                logger.info("✅ ENHANCED PROFILE: Sites cache cleared")

            if cache_type in ['session', 'all']:
                self._session_validation_cache.clear()
                self._session_validation_timestamp.clear()
                logger.info("✅ ENHANCED PROFILE: Session validation cache cleared")

    def invalidate_user_profile_cache(self, username: str = None):
        """
        Invalidate profile cache for a specific user.

        Args:
            username: Username to invalidate cache for (defaults to current user)
        """
        if not username:
            username = getattr(self.token_manager, 'username', '')

        if not username:
            logger.warning("Cannot invalidate profile cache - no username provided")
            return

        base_url = getattr(self.token_manager, 'base_url', '')
        cache_key = self._get_cache_key(username, base_url)

        with self._lock:
            # Remove from memory cache
            if cache_key in self._profile_cache:
                del self._profile_cache[cache_key]
                logger.info(f"✅ ENHANCED PROFILE: Memory cache invalidated for user {username}")

            if cache_key in self._profile_cache_timestamp:
                del self._profile_cache_timestamp[cache_key]

        # Remove from disk cache
        try:
            cache_file = os.path.join(self.cache_dir, f'enhanced_profile_{username}.pkl')
            if os.path.exists(cache_file):
                os.remove(cache_file)
                logger.info(f"✅ ENHANCED PROFILE: Disk cache invalidated for user {username}")
        except Exception as e:
            logger.warning(f"Error removing disk cache for user {username}: {e}")

    def force_profile_refresh(self, username: str = None):
        """
        Force a fresh profile fetch for a user (invalidates cache and fetches new data).

        Args:
            username: Username to refresh profile for (defaults to current user)

        Returns:
            dict: Fresh profile data or None if failed
        """
        # Invalidate existing cache first
        self.invalidate_user_profile_cache(username)

        # Force fresh fetch
        return self.get_user_profile(username=username, use_cache=False, force_refresh=True)

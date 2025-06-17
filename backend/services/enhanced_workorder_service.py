"""
Enhanced Work Order Service for Maximo OAuth.
Optimized work order data retrieval with intelligent caching and performance monitoring.
"""
import os
import json
import time
import logging
import pickle
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('enhanced_workorder_service')

class EnhancedWorkOrderService:
    """
    Optimized work order service that consolidates work order data retrieval logic
    with intelligent caching and performance monitoring.
    """

    # Class-level caches for performance
    _workorder_cache = {}
    _workorder_cache_timestamp = {}
    _session_validation_cache = {}
    _session_validation_timestamp = {}

    # Cache configuration (shorter TTL for more dynamic work order data)
    WORKORDER_CACHE_DURATION = 180  # 3 minutes for work orders
    SESSION_CACHE_DURATION = 30     # 30 seconds for session validation

    # Performance monitoring
    _performance_stats = {
        'total_requests': 0,
        'cache_hits': 0,
        'api_calls': 0,
        'average_response_time': 0.0,
        'total_workorders_fetched': 0,
        'last_reset': time.time()
    }

    def __init__(self, token_manager, enhanced_profile_service, cache_dir=None):
        """
        Initialize the enhanced work order service.

        Args:
            token_manager: The Maximo token manager instance
            enhanced_profile_service: Enhanced profile service for user site retrieval
            cache_dir: Directory for disk cache (optional)
        """
        self.token_manager = token_manager
        self.enhanced_profile_service = enhanced_profile_service
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

    def _get_cache_key(self, username: str, site_id: str, base_url: str) -> str:
        """Generate optimized cache key for work orders."""
        return f"wo_{username}_{site_id}@{hash(base_url)}"

    def _is_cache_valid(self, cache_key: str, cache_type: str) -> bool:
        """Check if cache entry is still valid."""
        timestamp_cache = getattr(self, f'_{cache_type}_cache_timestamp', {})
        duration = getattr(self, f'{cache_type.upper()}_CACHE_DURATION', 180)

        if cache_key not in timestamp_cache:
            return False

        return time.time() - timestamp_cache[cache_key] < duration

    def _update_performance_stats(self, response_time: float, cache_hit: bool, api_call: bool, workorder_count: int = 0):
        """Update performance monitoring statistics."""
        with self._lock:
            stats = self._performance_stats
            stats['total_requests'] += 1

            if cache_hit:
                stats['cache_hits'] += 1
            if api_call:
                stats['api_calls'] += 1
            if workorder_count > 0:
                stats['total_workorders_fetched'] += workorder_count

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
                'total_workorders_fetched': 0,
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

    def _get_user_site_id(self) -> Optional[str]:
        """
        Get the user's site ID from the enhanced profile service.

        Returns:
            str: User's site ID or None if not available
        """
        try:
            # Use the enhanced profile service to get user profile
            user_profile = self.enhanced_profile_service.get_user_profile()
            if user_profile:
                site_id = user_profile.get('defaultSite', '')
                if site_id:
                    logger.info(f"✅ ENHANCED WO: Using user site ID: {site_id}")
                    return site_id
                else:
                    logger.warning("⚠️ ENHANCED WO: No default site found in user profile")
            else:
                logger.warning("⚠️ ENHANCED WO: Could not retrieve user profile")
            return None
        except Exception as e:
            logger.error(f"❌ ENHANCED WO: Error getting user site ID: {e}")
            return None

    def _save_workorders_to_disk_cache(self, workorders_data: List[Dict[str, Any]], username: str, site_id: str):
        """
        Save work orders data to disk cache for persistence.

        Args:
            workorders_data: Work orders data to cache
            username: Username for cache file naming
            site_id: Site ID for cache file naming
        """
        if not workorders_data or not username or not site_id or not self.cache_dir:
            return

        try:
            cache_file = os.path.join(self.cache_dir, f'enhanced_workorders_{username}_{site_id}.pkl')
            cache_data = {
                'workorders': workorders_data,
                'timestamp': time.time(),
                'username': username,
                'site_id': site_id,
                'base_url': getattr(self.token_manager, 'base_url', '')
            }

            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)

            logger.debug(f"Work orders cached to disk for {username} at site {site_id}")
        except Exception as e:
            logger.warning(f"Error saving work orders to disk cache: {e}")

    def _load_workorders_from_disk_cache(self, username: str, site_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Load work orders data from disk cache if available and valid.

        Args:
            username: Username to load cache for
            site_id: Site ID to load cache for

        Returns:
            list: Cached work orders data or None if not available
        """
        if not username or not site_id or not self.cache_dir:
            return None

        try:
            cache_file = os.path.join(self.cache_dir, f'enhanced_workorders_{username}_{site_id}.pkl')

            if not os.path.exists(cache_file):
                return None

            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)

            # Validate cache data
            if (cache_data.get('username') == username and
                cache_data.get('site_id') == site_id and
                cache_data.get('base_url') == getattr(self.token_manager, 'base_url', '') and
                time.time() - cache_data.get('timestamp', 0) < 900):  # 15 minutes max for disk cache

                logger.debug(f"Loaded work orders from disk cache for {username} at site {site_id}")
                return cache_data.get('workorders', [])

            return None
        except Exception as e:
            logger.warning(f"Error loading work orders from disk cache: {e}")
            return None

    def _clean_workorder_data(self, workorder_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean and normalize work order data.

        Args:
            workorder_data: Raw work order data from Maximo API

        Returns:
            dict: Cleaned work order data
        """
        if not workorder_data:
            return {}

        # Extract essential fields and clean them
        cleaned = {
            'wonum': workorder_data.get('wonum', ''),
            'description': workorder_data.get('description', ''),
            'status': workorder_data.get('status', ''),
            'siteid': workorder_data.get('siteid', ''),
            'priority': workorder_data.get('priority', ''),
            'worktype': workorder_data.get('worktype', ''),
            'assignedto': workorder_data.get('assignedto', ''),
            'targetstart': workorder_data.get('targetstart', ''),
            'targetfinish': workorder_data.get('targetfinish', ''),
            'schedstart': workorder_data.get('schedstart', ''),
            'schedfinish': workorder_data.get('schedfinish', ''),
            'location': workorder_data.get('location', ''),
            'assetnum': workorder_data.get('assetnum', ''),
            'istask': workorder_data.get('istask', 0),
            'historyflag': workorder_data.get('historyflag', 0),
            'statusdate': workorder_data.get('statusdate', ''),
            'reportdate': workorder_data.get('reportdate', ''),
            'actstart': workorder_data.get('actstart', ''),
            'actfinish': workorder_data.get('actfinish', ''),
            'estdur': workorder_data.get('estdur', 0),
            'actlabcost': workorder_data.get('actlabcost', 0),
            'actmatcost': workorder_data.get('actmatcost', 0),
            'acttoolcost': workorder_data.get('acttoolcost', 0),
            'acttotalcost': workorder_data.get('acttotalcost', 0)
        }

        return cleaned

    def get_assigned_workorders(self, use_cache: bool = True, force_refresh: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Optimized work order retrieval with intelligent caching.

        Args:
            use_cache: Whether to use cached data
            force_refresh: Force a fresh API call

        Returns:
            tuple: (workorders_list, performance_stats)
        """
        start_time = time.time()

        # Validate session first
        if not self.is_session_valid():
            logger.error("Cannot fetch work orders: Not logged in")
            self._update_performance_stats(time.time() - start_time, False, False)
            return [], self.get_performance_stats()

        # Get user's site ID (no fallback - must use actual user's site)
        site_id = self._get_user_site_id()
        if not site_id:
            logger.error("❌ ENHANCED WO: Cannot fetch work orders - no user site ID available")
            self._update_performance_stats(time.time() - start_time, False, False)
            return [], self.get_performance_stats()

        # Get username and generate cache key
        username = getattr(self.token_manager, 'username', '')
        if not username:
            logger.error("Cannot determine username for work order fetch")
            self._update_performance_stats(time.time() - start_time, False, False)
            return [], self.get_performance_stats()

        base_url = getattr(self.token_manager, 'base_url', '')
        cache_key = self._get_cache_key(username, site_id, base_url)

        # Check memory cache first (fastest)
        if use_cache and not force_refresh and self._is_cache_valid(cache_key, 'workorder'):
            cached_workorders = self._workorder_cache.get(cache_key, [])
            if cached_workorders:
                cache_time = time.time() - start_time
                logger.info(f"✅ ENHANCED WO: Using memory cached work orders ({len(cached_workorders)} WOs, {cache_time:.3f}s)")
                self._update_performance_stats(cache_time, True, False, len(cached_workorders))
                return cached_workorders, self.get_performance_stats()

        # Check disk cache if memory cache miss
        if use_cache and not force_refresh:
            disk_cached = self._load_workorders_from_disk_cache(username, site_id)
            if disk_cached:
                # Store in memory cache for next time
                with self._lock:
                    self._workorder_cache[cache_key] = disk_cached
                    self._workorder_cache_timestamp[cache_key] = time.time()

                disk_time = time.time() - start_time
                logger.info(f"✅ ENHANCED WO: Using disk cached work orders ({len(disk_cached)} WOs, {disk_time:.3f}s)")
                self._update_performance_stats(disk_time, True, False, len(disk_cached))
                return disk_cached, self.get_performance_stats()

        # Enhanced status filters using OSLC 'in' operator for multiple status values
        # Includes all specified status values: APPR, ASSIGN, READY, INPRG, PACK, DEFER, WAPPR, WGOVT, AWARD, MTLCXD, MTLISD, PISSUE, RTI, WMATL, WSERV, WSCH
        # LIGHTNING FAST: Use OSLC 'in' operator syntax: status in ["APPR","ASSIGN","READY"]
        # CORRECT OSLC SYNTAX: According to IBM docs, use 'in' operator for OR within single property
        status_filters = [
            # Primary filter: Most common statuses first for fastest results
            'status in ["APPR","ASSIGN","READY","INPRG"]',
            # Secondary filter: Additional statuses
            'status in ["PACK","DEFER","WAPPR","WGOVT"]',
            # Tertiary filter: Remaining statuses
            'status in ["AWARD","MTLCXD","MTLISD","PISSUE","RTI","WMATL","WSERV","WSCH"]',
            # Fallback: Single status for maximum compatibility
            'status="APPR"',
            # Last resort: No status filter
            ""
        ]

        # Perform optimized API call with session refresh capability
        max_retries = 2
        for status_filter in status_filters:
            logger.info(f"🔍 ENHANCED WO: Trying status filter: {status_filter}")

            for attempt in range(max_retries):
                try:
                    # Ensure we have a valid session before making the API call
                    if attempt > 0:
                        logger.info(f"🔄 ENHANCED WO: Retry attempt {attempt + 1}, refreshing session...")
                        # Force session refresh
                        if hasattr(self.token_manager, 'force_session_refresh'):
                            self.token_manager.force_session_refresh()
                        elif hasattr(self.token_manager, 'refresh_token_if_needed'):
                            self.token_manager.refresh_token_if_needed()
                        elif hasattr(self.token_manager, 'is_logged_in'):
                            # Force a fresh login check
                            self.token_manager.is_logged_in()

                        # Add a small delay to allow session refresh to take effect
                        import time as time_module
                        time_module.sleep(0.5)

                    # Build the API URL with specific filters
                    api_url = f"{base_url}/oslc/os/mxapiwodetail"

                    # Construct the consolidated filter with all requirements
                    # LIGHTNING FAST: Include BOTH WORKORDER and ACTIVITY
                    # PERFORMANCE: Use pagination (20 records) to avoid server overload
                    # CORRECT OSLC SYNTAX: Use 'in' operator for multiple statuses

                    # We'll make TWO separate API calls: one for WORKORDER, one for ACTIVITY
                    # This avoids complex woclass OR logic while using proper status 'in' syntax
                    woclass_types = ["WORKORDER", "ACTIVITY"]
                    all_workorders = []

                    for woclass_type in woclass_types:
                        if status_filter:
                            # Build filter using OSLC 'in' operator for status
                            filter_clause = f"{status_filter} and woclass=\"{woclass_type}\" and siteid=\"{site_id}\" and istask=0 and historyflag=0"
                        else:
                            # No status filter - just woclass, site, task, and history filters
                            filter_clause = f"woclass=\"{woclass_type}\" and siteid=\"{site_id}\" and istask=0 and historyflag=0"

                        # LIGHTNING FAST: Use pagination with 20 records per page
                        params = {
                            "oslc.select": "*",
                            "oslc.where": filter_clause,
                            "oslc.pageSize": "20",  # PERFORMANCE: 20 records per page for lightning speed
                            "lean": "1"  # Lean response for better performance
                        }

                        logger.info(f"� ENHANCED WO: Fetching {woclass_type} work orders from {api_url} (attempt {attempt + 1})")
                        logger.info(f"🔍 ENHANCED WO: Filter: {filter_clause}")
                        logger.info(f"🔍 ENHANCED WO: Full URL with params: {api_url}?{self._build_query_string(params)}")

                        response = self.token_manager.session.get(
                            api_url,
                            params=params,
                            timeout=(3.0, 10),  # LIGHTNING FAST: Reduced timeout for quick response
                            headers={"Accept": "application/json"},
                            allow_redirects=True
                        )

                        # Validate response
                        if 'login' in response.url.lower():
                            logger.warning(f"Session expired during work order fetch for {woclass_type} (attempt {attempt + 1})")
                            if attempt < max_retries - 1:
                                break  # Break inner loop to retry with session refresh
                            else:
                                logger.error(f"Session expired after all retry attempts for {woclass_type}")
                                continue  # Try next woclass_type

                        if response.status_code != 200:
                            logger.error(f"Work order fetch failed for {woclass_type}. Status: {response.status_code}")
                            logger.error(f"Response content: {response.text[:500]}")
                            if attempt < max_retries - 1:
                                break  # Break inner loop to retry
                            else:
                                continue  # Try next woclass_type

                        # Success! Process this woclass_type response
                        try:
                            response_data = response.json()
                            woclass_workorders = []

                            # Handle different response formats
                            if isinstance(response_data, dict):
                                if 'member' in response_data:
                                    woclass_workorders = response_data['member']
                                elif 'workorder' in response_data:
                                    woclass_workorders = response_data['workorder']
                                else:
                                    woclass_workorders = [response_data] if response_data else []
                            elif isinstance(response_data, list):
                                woclass_workorders = response_data

                            # Add to all_workorders
                            all_workorders.extend(woclass_workorders)
                            logger.info(f"📊 ENHANCED WO: Found {len(woclass_workorders)} {woclass_type} work orders")

                        except Exception as e:
                            logger.error(f"Error processing {woclass_type} response: {e}")
                            continue  # Try next woclass_type

                    # If we got here and had a session issue, retry the entire status filter
                    if 'login' in response.url.lower() and attempt < max_retries - 1:
                        continue  # Retry with session refresh

                    # Success for this status filter - break out of retry loop
                    break

                except Exception as e:
                    logger.warning(f"Error on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        continue  # Retry
                    else:
                        continue  # Try next status filter

            # If we collected any workorders from this status filter, process them
            if all_workorders:
                logger.info(f"📊 ENHANCED WO: Collected {len(all_workorders)} total work orders from status filter")
                break  # Exit status filter loop - we have data

        # If no workorders collected after all status filters, try disk cache
        if not all_workorders:
            logger.error(f"Error fetching work orders after all status filters and attempts")
            # Try disk cache as last resort
            disk_fallback = self._load_workorders_from_disk_cache(username, site_id)
            if disk_fallback:
                logger.info("Using stale disk cache as fallback for work orders")
                self._update_performance_stats(time.time() - start_time, True, True, len(disk_fallback))
                return disk_fallback, self.get_performance_stats()

            self._update_performance_stats(time.time() - start_time, False, True)
            return [], self.get_performance_stats()

        # Process collected workorders
        try:
            # Clean and process work orders
            cleaned_workorders = []
            for i, wo_data in enumerate(all_workorders):
                cleaned_wo = self._clean_workorder_data(wo_data)
                if cleaned_wo.get('wonum'):  # Only include work orders with valid work order numbers
                    cleaned_workorders.append(cleaned_wo)
                    if i < 3:  # Log first few work orders for debugging
                        logger.info(f"📋 ENHANCED WO: Work Order {i+1}: {cleaned_wo.get('wonum')} - {cleaned_wo.get('description', 'No description')[:50]}")

            # Cache the result in both memory and disk
            with self._lock:
                self._workorder_cache[cache_key] = cleaned_workorders
                self._workorder_cache_timestamp[cache_key] = time.time()

            self._save_workorders_to_disk_cache(cleaned_workorders, username, site_id)

            api_time = time.time() - start_time
            logger.info(f"✅ ENHANCED WO: Fresh work orders fetched successfully ({len(cleaned_workorders)} WOs, {api_time:.3f}s)")
            self._update_performance_stats(api_time, False, True, len(cleaned_workorders))
            return cleaned_workorders, self.get_performance_stats()

        except Exception as e:
            logger.error(f"Error processing work order data: {e}")

            # Try disk cache as last resort
            disk_fallback = self._load_workorders_from_disk_cache(username, site_id)
            if disk_fallback:
                logger.info("Using stale disk cache as fallback for work orders")
                self._update_performance_stats(time.time() - start_time, True, True, len(disk_fallback))
                return disk_fallback, self.get_performance_stats()

            self._update_performance_stats(time.time() - start_time, False, True)
            return [], self.get_performance_stats()

    def clear_cache(self, cache_type: str = 'all'):
        """
        Clear specified cache type including disk cache.

        Args:
            cache_type: Type of cache to clear ('workorder', 'session', 'all')
        """
        with self._lock:
            if cache_type in ['workorder', 'all']:
                self._workorder_cache.clear()
                self._workorder_cache_timestamp.clear()
                logger.info("Work order memory cache cleared")

                # Also clear disk cache files
                if self.cache_dir and os.path.exists(self.cache_dir):
                    try:
                        for filename in os.listdir(self.cache_dir):
                            if filename.startswith('enhanced_workorders_') and filename.endswith('.pkl'):
                                file_path = os.path.join(self.cache_dir, filename)
                                os.remove(file_path)
                                logger.info(f"Removed disk cache file: {filename}")
                    except Exception as e:
                        logger.warning(f"Error clearing disk cache: {e}")

            if cache_type in ['session', 'all']:
                self._session_validation_cache.clear()
                self._session_validation_timestamp.clear()
                logger.info("Session validation cache cleared")

    def get_workorder_summary(self, workorders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics for work orders.

        Args:
            workorders: List of work order data

        Returns:
            dict: Summary statistics
        """
        if not workorders:
            return {
                'total_count': 0,
                'by_priority': {},
                'by_worktype': {},
                'by_status': {},
                'total_estimated_cost': 0,
                'total_actual_cost': 0
            }

        summary = {
            'total_count': len(workorders),
            'by_priority': {},
            'by_worktype': {},
            'by_status': {},
            'total_estimated_cost': 0,
            'total_actual_cost': 0
        }

        for wo in workorders:
            # Count by priority
            priority = wo.get('priority', 'Unknown')
            summary['by_priority'][priority] = summary['by_priority'].get(priority, 0) + 1

            # Count by work type
            worktype = wo.get('worktype', 'Unknown')
            summary['by_worktype'][worktype] = summary['by_worktype'].get(worktype, 0) + 1

            # Count by status
            status = wo.get('status', 'Unknown')
            summary['by_status'][status] = summary['by_status'].get(status, 0) + 1

            # Sum costs
            try:
                summary['total_actual_cost'] += float(wo.get('acttotalcost', 0) or 0)
            except (ValueError, TypeError):
                pass

        return summary

    def search_workorders(self, search_criteria=None, page=1, page_size=20):
        """
        Search work orders with lazy loading, pagination, and client-side filtering.

        Args:
            search_criteria (dict): Search filters {status, priority, description, woclass, wonum}
                - status: Work order status filter
                - priority: Work order priority filter
                - description: Description text search (partial match)
                - woclass: Work order class filter
                - wonum: Work order number search (partial or exact match)
                - site_ids: List of site IDs to search
            page (int): Page number (1-based)
            page_size (int): Records per page (default 20)

        Returns:
            dict: {
                'workorders': list,
                'total_count': int,
                'page': int,
                'page_size': int,
                'total_pages': int,
                'has_next': bool,
                'has_prev': bool,
                'performance_stats': dict
            }
        """
        start_time = time.time()

        # Check if we have a valid session first
        if not self.is_session_valid():
            logger.warning("Session not valid for work order search")
            return self._empty_search_result()

        # If no search criteria provided, return empty result (lazy loading)
        if not search_criteria or not any(search_criteria.values()):
            logger.info("🔍 ENHANCED WO: No search criteria provided - returning empty result for lazy loading")
            return self._empty_search_result()

        # Get user's site ID
        site_id = self._get_user_site_id()
        if not site_id:
            logger.error("❌ ENHANCED WO: Cannot search work orders - no user site ID available")
            return self._empty_search_result()

        # Get username
        username = getattr(self.token_manager, 'username', '')
        base_url = getattr(self.token_manager, 'base_url', '')

        # Build OSLC filter from search criteria
        filter_parts = []

        # Site filter (always required) - support multiple sites
        site_ids = search_criteria.get('site_ids', [])
        if site_ids and isinstance(site_ids, list) and len(site_ids) > 0:
            # Multiple sites selected
            if len(site_ids) == 1:
                filter_parts.append(f'siteid="{site_ids[0]}"')
            else:
                # Use OSLC 'in' operator for multiple sites
                site_list = '","'.join(site_ids)
                filter_parts.append(f'siteid in ["{site_list}"]')
            logger.info(f"🏢 ENHANCED WO: Using selected sites: {site_ids}")
        else:
            # Fallback to user's default site
            filter_parts.append(f'siteid="{site_id}"')
            logger.info(f"🏢 ENHANCED WO: Using default site: {site_id}")

        # Basic filters (always applied)
        filter_parts.append('istask=0')
        filter_parts.append('historyflag=0')

        # Work order class filter
        woclass = search_criteria.get('woclass', 'WORKORDER')
        if woclass and woclass != 'ALL':
            if woclass == 'BOTH':
                filter_parts.append('(woclass="WORKORDER" or woclass="ACTIVITY")')
            else:
                filter_parts.append(f'woclass="{woclass}"')

        # Status filter
        status = search_criteria.get('status')
        if status and status != 'ALL':
            if isinstance(status, list):
                # Multiple statuses using 'in' operator
                status_list = '","'.join(status)
                filter_parts.append(f'status in ["{status_list}"]')
            else:
                filter_parts.append(f'status="{status}"')

        # Priority filter
        priority = search_criteria.get('priority')
        if priority and priority != 'ALL':
            filter_parts.append(f'wopriority={priority}')

        # Description filter (using LIKE for partial matching)
        description = search_criteria.get('description')
        if description:
            # Escape quotes and use LIKE operator
            description_clean = description.replace('"', '\\"')
            filter_parts.append(f'description="%{description_clean}%"')

        # Work Order Number filter (support both exact and partial matching)
        wonum = search_criteria.get('wonum')
        if wonum:
            # Escape quotes and clean the input
            wonum_clean = wonum.replace('"', '\\"').strip()
            if wonum_clean:
                # Use LIKE operator for partial matching (supports both exact and partial)
                filter_parts.append(f'wonum="%{wonum_clean}%"')
                logger.info(f'🔍 ENHANCED WO: Added wonum filter: wonum="%{wonum_clean}%"')

        # Combine all filters
        oslc_filter = ' and '.join(filter_parts)

        logger.info(f"🔍 ENHANCED WO: Search filter: {oslc_filter}")

        # Calculate pagination offset
        offset = (page - 1) * page_size

        return self._execute_paginated_search(oslc_filter, page, page_size, offset, start_time)

    def _empty_search_result(self):
        """Return empty search result structure."""
        return {
            'workorders': [],
            'total_count': 0,
            'page': 1,
            'page_size': 20,
            'total_pages': 0,
            'has_next': False,
            'has_prev': False,
            'performance_stats': self.get_performance_stats()
        }

    def _execute_paginated_search(self, oslc_filter, page, page_size, offset, start_time):
        """Execute paginated search with proper OSLC ordering and pagination."""
        try:
            base_url = getattr(self.token_manager, 'base_url', '')
            api_url = f"{base_url}/oslc/os/mxapiwodetail"

            # LIGHTNING FAST: Use pagination with sorting by REPORTDATE ascending
            # OSLC orderBy syntax requires + or - prefix for sort direction
            params = {
                "oslc.select": "*",
                "oslc.where": oslc_filter,
                "oslc.orderBy": "+reportdate",  # Sort by REPORTDATE ascending (+ prefix required)
                "oslc.pageSize": str(page_size),
                "oslc.paging": "true",
                "lean": "1"  # Lean response for better performance
            }

            logger.info(f"🔍 ENHANCED WO: Executing paginated search (page {page}, size {page_size})")
            logger.info(f"🔍 ENHANCED WO: Full URL: {api_url}?{self._build_query_string(params)}")

            response = self.token_manager.session.get(
                api_url,
                params=params,
                timeout=(3.0, 15),  # Slightly longer timeout for search
                headers={"Accept": "application/json"},
                allow_redirects=True
            )

            # Validate response and handle session expiration
            if 'login' in response.url.lower():
                logger.warning("Session expired during work order search")
                # Try to refresh session once
                if hasattr(self.token_manager, 'force_session_refresh'):
                    logger.info("🔄 ENHANCED WO: Attempting session refresh...")
                    if self.token_manager.force_session_refresh():
                        logger.info("✅ ENHANCED WO: Session refreshed, retrying search...")
                        # Retry the search once with refreshed session
                        try:
                            response = self.token_manager.session.get(
                                api_url,
                                params=params,
                                timeout=(3.0, 30),
                                headers={"Accept": "application/json"},
                                allow_redirects=True
                            )
                            if response.status_code == 200 and 'login' not in response.url.lower():
                                logger.info("✅ ENHANCED WO: Retry after session refresh successful")
                                # Continue with processing the response
                            else:
                                logger.warning("❌ ENHANCED WO: Retry after session refresh failed")
                                return self._empty_search_result()
                        except Exception as retry_e:
                            logger.error(f"Error during retry after session refresh: {retry_e}")
                            return self._empty_search_result()
                    else:
                        logger.warning("❌ ENHANCED WO: Session refresh failed")
                        return self._empty_search_result()
                else:
                    return self._empty_search_result()

            if response.status_code != 200:
                logger.error(f"Work order search failed. Status: {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}")
                return self._empty_search_result()

            # Process successful response
            response_data = response.json()
            workorders_raw = []

            # Handle different response formats
            if isinstance(response_data, dict):
                if 'member' in response_data:
                    workorders_raw = response_data['member']
                elif 'workorder' in response_data:
                    workorders_raw = response_data['workorder']
                else:
                    workorders_raw = [response_data] if response_data else []
            elif isinstance(response_data, list):
                workorders_raw = response_data

            # Clean and process work orders
            cleaned_workorders = []
            for wo_data in workorders_raw:
                cleaned_wo = self._clean_workorder_data(wo_data)
                if cleaned_wo.get('wonum'):  # Only include work orders with valid work order numbers
                    cleaned_workorders.append(cleaned_wo)

            # Calculate pagination info
            total_count = len(cleaned_workorders)  # For now, use current page count
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            has_next = page < total_pages
            has_prev = page > 1

            api_time = time.time() - start_time
            logger.info(f"✅ ENHANCED WO: Search completed ({len(cleaned_workorders)} WOs, {api_time:.3f}s)")

            return {
                'workorders': cleaned_workorders,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'has_next': has_next,
                'has_prev': has_prev,
                'performance_stats': self.get_performance_stats()
            }

        except Exception as e:
            logger.error(f"Error executing paginated search: {e}")
            return self._empty_search_result()

    def get_workorder_by_wonum(self, wonum: str):
        """
        Get a specific work order by work order number.
        This method bypasses pagination and cache limitations to find any work order.
        It searches across all accessible sites, not just the user's default site.

        Args:
            wonum (str): Work order number to search for

        Returns:
            dict: Work order data or None if not found
        """
        start_time = time.time()

        # Check if we have a valid session first
        if not self.is_session_valid():
            logger.warning(f"Session not valid for work order lookup: {wonum}")
            return None

        logger.info(f"🔍 ENHANCED WO: Looking up specific work order: {wonum}")

        try:
            base_url = getattr(self.token_manager, 'base_url', '')
            api_url = f"{base_url}/oslc/os/mxapiwodetail"

            # First try: Search without site restriction to find the work order in any site
            # This is more flexible and matches how work orders are displayed in search results
            oslc_filter = f'wonum="{wonum}"'

            params = {
                "oslc.select": "*",
                "oslc.where": oslc_filter,
                "oslc.pageSize": "1",  # Only need one result
                "lean": "1"
            }

            logger.info(f"🔍 ENHANCED WO: Direct lookup filter (any site): {oslc_filter}")
            logger.info(f"🔍 ENHANCED WO: Full URL: {api_url}?{self._build_query_string(params)}")

            response = self.token_manager.session.get(
                api_url,
                params=params,
                timeout=(3.0, 15),
                headers={"Accept": "application/json"},
                allow_redirects=True
            )

            # Validate response and handle session expiration
            if 'login' in response.url.lower():
                logger.warning(f"Session expired during work order lookup: {wonum}")
                # Try to refresh session once
                if hasattr(self.token_manager, 'force_session_refresh'):
                    logger.info(f"🔄 ENHANCED WO: Attempting session refresh for lookup: {wonum}")
                    if self.token_manager.force_session_refresh():
                        logger.info(f"✅ ENHANCED WO: Session refreshed, retrying lookup: {wonum}")
                        # Retry the lookup once with refreshed session
                        try:
                            response = self.token_manager.session.get(
                                api_url,
                                params=params,
                                timeout=(3.0, 15),
                                headers={"Accept": "application/json"},
                                allow_redirects=True
                            )
                            if response.status_code == 200 and 'login' not in response.url.lower():
                                logger.info(f"✅ ENHANCED WO: Retry lookup after session refresh successful: {wonum}")
                                # Continue with processing the response
                            else:
                                logger.warning(f"❌ ENHANCED WO: Retry lookup after session refresh failed: {wonum}")
                                return None
                        except Exception as retry_e:
                            logger.error(f"Error during retry lookup after session refresh: {retry_e}")
                            return None
                    else:
                        logger.warning(f"❌ ENHANCED WO: Session refresh failed for lookup: {wonum}")
                        return None
                else:
                    return None

            if response.status_code != 200:
                logger.error(f"Work order lookup failed for {wonum}. Status: {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}")
                return None

            # Process successful response
            response_data = response.json()
            workorders_raw = []

            # Handle different response formats
            if isinstance(response_data, dict):
                if 'member' in response_data:
                    workorders_raw = response_data['member']
                elif 'workorder' in response_data:
                    workorders_raw = response_data['workorder']
                else:
                    workorders_raw = [response_data] if response_data else []
            elif isinstance(response_data, list):
                workorders_raw = response_data

            # Process the work order if found
            if workorders_raw:
                workorder = self._clean_workorder_data(workorders_raw[0])
                lookup_time = time.time() - start_time
                found_site = workorder.get('siteid', 'Unknown')
                logger.info(f"✅ ENHANCED WO: Found work order {wonum} in site {found_site} ({lookup_time:.3f}s)")
                return workorder
            else:
                # If not found without site restriction, try with user's default site as fallback
                site_id = self._get_user_site_id()
                if site_id:
                    logger.info(f"🔍 ENHANCED WO: Retrying lookup with user's default site: {site_id}")
                    oslc_filter_with_site = f'wonum="{wonum}" and siteid="{site_id}"'
                    params['oslc.where'] = oslc_filter_with_site

                    response = self.token_manager.session.get(
                        api_url,
                        params=params,
                        timeout=(3.0, 15),
                        headers={"Accept": "application/json"},
                        allow_redirects=True
                    )

                    if response.status_code == 200 and 'login' not in response.url.lower():
                        response_data = response.json()
                        if isinstance(response_data, dict) and 'member' in response_data and response_data['member']:
                            workorder = self._clean_workorder_data(response_data['member'][0])
                            lookup_time = time.time() - start_time
                            logger.info(f"✅ ENHANCED WO: Found work order {wonum} in default site {site_id} ({lookup_time:.3f}s)")
                            return workorder

                lookup_time = time.time() - start_time
                logger.warning(f"❌ ENHANCED WO: Work order {wonum} not found in any accessible site ({lookup_time:.3f}s)")
                return None

        except Exception as e:
            lookup_time = time.time() - start_time
            logger.error(f"Error looking up work order {wonum}: {e} ({lookup_time:.3f}s)")
            return None

    def _build_query_string(self, params: Dict[str, str]) -> str:
        """Build query string for debugging purposes."""
        try:
            from urllib.parse import urlencode
            return urlencode(params)
        except Exception:
            return str(params)

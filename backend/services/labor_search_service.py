#!/usr/bin/env python3
"""
Labor Search Service for Maximo Work Orders
Provides labor code search functionality using MXAPILABOR endpoint
"""

import logging
import time
import json
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

class LaborSearchService:
    """
    Service for searching labor codes using MXAPILABOR API.
    
    This service handles:
    - Labor code search with various filters
    - Caching for performance optimization
    - Session-based authentication using token manager
    - Proper error handling and logging
    """
    
    def __init__(self, token_manager):
        """Initialize the labor search service."""
        self.token_manager = token_manager
        self.logger = logging.getLogger(f'{__name__}.{self.__class__.__name__}')
        
        # Cache configuration
        self._search_cache = {}
        self._cache_timestamps = {}
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._max_cache_size = 100
        
        # Performance tracking
        self._performance_stats = {
            'total_searches': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_response_time': 0,
            'last_search_time': None
        }
        
        self.logger.info("🔧 LABOR SEARCH: Service initialized")
    
    def is_session_valid(self) -> bool:
        """Check if the current session is valid."""
        return (hasattr(self.token_manager, 'username') and 
                self.token_manager.username and 
                hasattr(self.token_manager, 'session') and 
                self.token_manager.session)
    
    def _generate_cache_key(self, search_term: str, site_id: str, limit: int, 
                           craft: Optional[str] = None, skill_level: Optional[str] = None) -> str:
        """Generate a cache key for the search parameters."""
        key_parts = [
            f"term:{search_term.lower().strip()}",
            f"site:{site_id}",
            f"limit:{limit}"
        ]
        
        if craft:
            key_parts.append(f"craft:{craft.lower().strip()}")
        if skill_level:
            key_parts.append(f"skill:{skill_level.lower().strip()}")
            
        return "|".join(key_parts)
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._cache_timestamps:
            return False
        
        cache_age = time.time() - self._cache_timestamps[cache_key]
        return cache_age < self._cache_ttl
    
    def _clean_cache(self):
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = []
        
        for key, timestamp in self._cache_timestamps.items():
            if current_time - timestamp > self._cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._search_cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
        
        # Limit cache size
        if len(self._search_cache) > self._max_cache_size:
            # Remove oldest entries
            sorted_keys = sorted(self._cache_timestamps.items(), key=lambda x: x[1])
            keys_to_remove = [k for k, _ in sorted_keys[:len(self._search_cache) - self._max_cache_size]]
            
            for key in keys_to_remove:
                self._search_cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
    
    def _update_performance_stats(self, response_time: float, cache_hit: bool):
        """Update performance statistics."""
        self._performance_stats['total_searches'] += 1
        self._performance_stats['last_search_time'] = time.time()
        
        if cache_hit:
            self._performance_stats['cache_hits'] += 1
        else:
            self._performance_stats['cache_misses'] += 1
        
        # Update average response time
        total_searches = self._performance_stats['total_searches']
        current_avg = self._performance_stats['avg_response_time']
        self._performance_stats['avg_response_time'] = (
            (current_avg * (total_searches - 1) + response_time) / total_searches
        )
    
    def search_labor(self, search_term: str, site_id: str, limit: int = 20,
                    craft: Optional[str] = None, skill_level: Optional[str] = None,
                    use_cache: bool = True) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Search for labor codes using MXAPILABOR endpoint.
        
        Args:
            search_term: Labor code or description to search for
            site_id: Site ID to filter labor codes
            limit: Maximum number of results to return
            craft: Optional craft filter
            skill_level: Optional skill level filter
            use_cache: Whether to use cached results
            
        Returns:
            tuple: (labor_list, metadata)
        """
        start_time = time.time()
        
        # Validate session
        if not self.is_session_valid():
            self.logger.error("Cannot search labor: Not logged in")
            self._update_performance_stats(time.time() - start_time, False)
            return [], {'error': 'Not logged in', 'search_time': 0}
        
        # Clean and validate inputs
        search_term = search_term.strip() if search_term else ""
        site_id = site_id.strip() if site_id else ""
        limit = max(1, min(limit, 100))  # Limit between 1 and 100
        
        if not search_term:
            self.logger.warning("Empty search term provided")
            self._update_performance_stats(time.time() - start_time, False)
            return [], {'error': 'Search term is required', 'search_time': 0}
        
        if len(search_term) < 2:
            self.logger.warning("Search term too short")
            self._update_performance_stats(time.time() - start_time, False)
            return [], {'error': 'Search term must be at least 2 characters', 'search_time': 0}
        
        # Check cache first
        cache_key = self._generate_cache_key(search_term, site_id, limit, craft, skill_level)
        
        if use_cache and self._is_cache_valid(cache_key):
            self.logger.info(f"🎯 LABOR SEARCH: Cache hit for key: {cache_key}")
            cached_result = self._search_cache[cache_key]
            self._update_performance_stats(time.time() - start_time, True)
            return cached_result['labor_list'], {
                **cached_result['metadata'],
                'cache_hit': True,
                'search_time': time.time() - start_time
            }
        
        # Perform API search
        try:
            labor_list, metadata = self._perform_labor_search(
                search_term, site_id, limit, craft, skill_level
            )
            
            # Cache the results
            if use_cache:
                self._clean_cache()
                self._search_cache[cache_key] = {
                    'labor_list': labor_list,
                    'metadata': metadata
                }
                self._cache_timestamps[cache_key] = time.time()
            
            search_time = time.time() - start_time
            self._update_performance_stats(search_time, False)
            
            metadata.update({
                'cache_hit': False,
                'search_time': search_time
            })
            
            return labor_list, metadata
            
        except Exception as e:
            self.logger.error(f"Error in labor search: {e}")
            self._update_performance_stats(time.time() - start_time, False)
            return [], {
                'error': str(e),
                'search_time': time.time() - start_time,
                'cache_hit': False
            }

    def _perform_labor_search(self, search_term: str, site_id: str, limit: int,
                             craft: Optional[str] = None, skill_level: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Perform the actual labor search using MXAPILABOR API.

        Args:
            search_term: Labor code or description to search for
            site_id: Site ID to filter labor codes
            limit: Maximum number of results to return
            craft: Optional craft filter
            skill_level: Optional skill level filter

        Returns:
            tuple: (labor_list, metadata)
        """
        api_start_time = time.time()

        try:
            base_url = getattr(self.token_manager, 'base_url', '')
            api_url = f"{base_url}/oslc/os/mxapilabor"

            # Build search filters for MXAPILABOR endpoint using correct field names
            # Clean search term to prevent injection
            search_term_clean = search_term.replace('"', '\\"')

            # MXAPILABOR endpoint search strategies using correct fields
            search_filters = []

            # Strategy 1: Partial match on laborcode with worksite filter
            if site_id and site_id != 'UNKNOWN':
                search_filters.append(f'laborcode="%{search_term_clean}%" and worksite="{site_id}"')
            else:
                search_filters.append(f'laborcode="%{search_term_clean}%"')

            # Strategy 2: Exact match on laborcode with worksite filter
            if site_id and site_id != 'UNKNOWN':
                search_filters.append(f'laborcode="{search_term_clean}" and worksite="{site_id}"')
            else:
                search_filters.append(f'laborcode="{search_term_clean}"')

            # Strategy 3: Search by personid (often same as laborcode)
            if site_id and site_id != 'UNKNOWN':
                search_filters.append(f'personid="%{search_term_clean}%" and worksite="{site_id}"')
            else:
                search_filters.append(f'personid="%{search_term_clean}%"')

            # Add craft and skill level filters to each strategy if provided
            if craft or skill_level:
                updated_filters = []
                for base_filter in search_filters:
                    filter_with_extras = base_filter
                    if craft:
                        filter_with_extras += f' and craft="{craft}"'
                    if skill_level:
                        filter_with_extras += f' and skilllevel="{skill_level}"'
                    updated_filters.append(filter_with_extras)
                search_filters = updated_filters

            # Try each search filter and combine results
            all_labor = []
            found_labor_codes = set()  # Track found labor codes to avoid duplicates

            for i, oslc_filter in enumerate(search_filters):
                self.logger.info(f"🔍 LABOR SEARCH: Try #{i+1} - Filter: {oslc_filter}")

                # Use correct MXAPILABOR fields based on discovered schema
                params = {
                    "oslc.select": "laborcode,personid,worksite,status,status_description,laborcraftrate,orgid,laborid,reportedhrs,availfactor,assigned",
                    "oslc.where": oslc_filter,
                    "oslc.pageSize": str(limit),
                    "lean": "1"
                }

                try:
                    # Make API request
                    response = self.token_manager.session.get(
                        api_url,
                        params=params,
                        timeout=(5.0, 30),
                        headers={"Accept": "application/json"},
                        allow_redirects=True
                    )

                    self.logger.info(f"🔍 LABOR SEARCH: Response status: {response.status_code}")

                    if response.status_code == 200:
                        try:
                            # Log the raw response content for debugging
                            response_text = response.text
                            self.logger.info(f"🔍 LABOR SEARCH: Raw response length: {len(response_text)}")
                            if len(response_text) == 0:
                                self.logger.info(f"🔍 LABOR SEARCH: Empty response - no labor records found for this filter")
                                continue

                            data = response.json()
                            self.logger.info(f"🔍 LABOR SEARCH: Response data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

                            # Extract labor records
                            labor_records = []
                            if 'member' in data:
                                labor_records = data['member']
                            elif 'rdfs:member' in data:
                                labor_records = data['rdfs:member']

                            # Process labor records from MXAPILABOR
                            if labor_records and len(labor_records) > 0:
                                self.logger.info(f"🔍 LABOR SEARCH: Sample record structure: {labor_records[0]}")

                            # Process and add unique labor records
                            for labor in labor_records:
                                labor_code = labor.get('laborcode', '')
                                if labor_code and labor_code not in found_labor_codes:
                                    found_labor_codes.add(labor_code)
                                    processed_labor = self._process_labor_record(labor)
                                    all_labor.append(processed_labor)

                                    # Stop if we've reached the limit
                                    if len(all_labor) >= limit:
                                        break

                            self.logger.info(f"✅ LABOR SEARCH: Strategy #{i+1} found {len(labor_records)} records")

                        except json.JSONDecodeError as e:
                            self.logger.error(f"Failed to parse JSON response for strategy #{i+1}: {e}")
                            self.logger.error(f"Response text (first 200 chars): {response.text[:200]}")
                            continue
                    else:
                        self.logger.error(f"API request failed for strategy #{i+1} with status {response.status_code}")
                        self.logger.error(f"Response: {response.text[:500]}")
                        continue

                except Exception as e:
                    self.logger.error(f"Exception during strategy #{i+1}: {e}")
                    continue

                # Stop if we've reached the limit
                if len(all_labor) >= limit:
                    break

            api_time = time.time() - api_start_time
            self.logger.info(f"✅ LABOR SEARCH: Total found {len(all_labor)} unique labor records")

            # Log the final processed response for debugging
            if all_labor:
                self.logger.info(f"🔍 LABOR SEARCH: Sample processed record: {all_labor[0]}")

            metadata = {
                'total_found': len(all_labor),
                'api_response_time': api_time,
                'search_term': search_term,
                'site_id': site_id,
                'craft': craft,
                'skill_level': skill_level,
                'limit': limit,
                'strategies_used': len(search_filters)
            }

            return all_labor[:limit], metadata

        except Exception as e:
            api_time = time.time() - api_start_time
            self.logger.error(f"Exception during labor search: {e}")
            return [], {
                'error': f'Search failed: {str(e)}',
                'api_response_time': api_time,
                'search_term': search_term,
                'site_id': site_id
            }

    def _process_labor_record(self, labor: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and clean a labor record from the MXAPILABOR API response.

        Args:
            labor: Raw labor record from MXAPILABOR API

        Returns:
            Processed labor record with correct field mappings
        """
        # Extract basic labor information using correct MXAPILABOR field names
        labor_code = labor.get('laborcode', '')
        person_id = labor.get('personid', '')
        worksite = labor.get('worksite', '')  # This is the site field in MXAPILABOR
        status = labor.get('status', '')
        status_description = labor.get('status_description', '')
        org_id = labor.get('orgid', '')
        labor_id = labor.get('laborid', '')
        reported_hrs = labor.get('reportedhrs', 0.0)
        avail_factor = labor.get('availfactor', 1.0)
        assigned = labor.get('assigned', False)

        # Extract craft and rate information from laborcraftrate array
        craft = ''
        default_rate = 0.0
        skill_level = ''  # Not available in MXAPILABOR

        laborcraftrate = labor.get('laborcraftrate', [])
        if isinstance(laborcraftrate, list) and len(laborcraftrate) > 0:
            # Find the default craft (defaultcraft=True) or use the first one
            default_craft_rate = None
            for craft_rate in laborcraftrate:
                if isinstance(craft_rate, dict):
                    if craft_rate.get('defaultcraft', False):
                        default_craft_rate = craft_rate
                        break
                    elif default_craft_rate is None:  # Use first one as fallback
                        default_craft_rate = craft_rate

            if default_craft_rate:
                craft = default_craft_rate.get('craft', '')
                default_rate = self._safe_float(default_craft_rate.get('rate', 0.0)) or 0.0

        return {
            'laborcode': labor_code,
            'personid': person_id,
            'worksite': worksite,
            'craft': craft,
            'skilllevel': skill_level,  # Not available in MXAPILABOR
            'siteid': worksite,  # Map worksite to siteid for compatibility
            'status': status,
            'status_description': status_description,
            'description': status_description or f"{labor_code} - {craft}" if craft else labor_code,  # Frontend expects this
            'defaultrate': default_rate,
            'standardrate': default_rate,  # Use default_rate for now
            'premiumrate': default_rate,   # Use default_rate for now
            'orgid': org_id,
            'laborid': labor_id,
            'reportedhrs': reported_hrs,  # Frontend expects this field name (no underscore)
            'availfactor': avail_factor,  # Frontend expects this field name (no underscore)
            'reported_hrs': reported_hrs,  # Keep both for compatibility
            'avail_factor': avail_factor,  # Keep both for compatibility
            'assigned': assigned,
            'laborcraftrate': laborcraftrate,  # Pass through the full laborcraftrate array
            'vendor': '',  # Not available in MXAPILABOR
            'contractnum': '',  # Not available in MXAPILABOR
            # Additional fields for display
            'display_name': f"{labor_code} ({craft})" if craft else labor_code,
            'rate_display': self._format_rate_display_mxapilabor(labor_code, craft, default_rate)
        }

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _format_rate_display(self, labor: Dict[str, Any]) -> str:
        """Format rate display for labor record (legacy method)."""
        rates = []

        default_rate = self._safe_float(labor.get('defaultrate'))
        standard_rate = self._safe_float(labor.get('standardrate'))
        premium_rate = self._safe_float(labor.get('premiumrate'))

        if default_rate is not None:
            rates.append(f"Default: ${default_rate:.2f}")
        if standard_rate is not None:
            rates.append(f"Standard: ${standard_rate:.2f}")
        if premium_rate is not None:
            rates.append(f"Premium: ${premium_rate:.2f}")

        return " | ".join(rates) if rates else "No rate info"

    def _format_rate_display_mxapilabor(self, labor_code: str, craft: str, rate: float) -> str:
        """Format rate display for MXAPILABOR labor record."""
        if rate and rate > 0:
            return f"Rate: ${rate:.2f}/hr"
        else:
            return f"Craft: {craft}" if craft else "No rate info"

    def clear_cache(self) -> Dict[str, Any]:
        """Clear the search cache."""
        cache_size = len(self._search_cache)
        self._search_cache.clear()
        self._cache_timestamps.clear()

        self.logger.info(f"🧹 LABOR SEARCH: Cleared cache ({cache_size} entries)")

        return {
            'success': True,
            'message': f'Cleared {cache_size} cache entries',
            'cache_size_before': cache_size
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache and performance statistics."""
        return {
            'cache_stats': {
                'total_entries': len(self._search_cache),
                'cache_ttl_seconds': self._cache_ttl,
                'max_cache_size': self._max_cache_size
            },
            'performance_stats': self._performance_stats.copy()
        }

#!/usr/bin/env python3
"""
Inventory Search Service

This service handles searching inventory items using MXAPIINVENTORY and MXAPIITEM APIs.
It provides comprehensive inventory search functionality with site-aware filtering.

Author: Augment Agent
Date: 2025-01-27
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

class InventorySearchService:
    """
    Service for searching inventory items from Maximo MXAPIINVENTORY and MXAPIITEM APIs.

    This service provides:
    - Inventory search by item number (partial/full)
    - Inventory search by description (partial/full)
    - Site-aware inventory filtering
    - Enhanced item data from MXAPIITEM when needed
    - Efficient API calls with proper error handling
    """

    def __init__(self, token_manager):
        """
        Initialize the inventory search service.

        Args:
            token_manager: Maximo token manager for API authentication
        """
        self.token_manager = token_manager
        self.logger = logging.getLogger(__name__)
        self._search_cache = {}
        self._cache_timeout = 300  # 5 minutes cache timeout

    def search_inventory_items(self, search_term: str, site_id: str, limit: int = 20) -> Tuple[List[Dict], Dict]:
        """
        Search inventory items by item number or description.

        Args:
            search_term (str): Search term for item number or description
            site_id (str): Site ID to filter inventory
            limit (int): Maximum number of results to return

        Returns:
            Tuple[List[Dict], Dict]: (inventory_items, metadata)
        """
        start_time = time.time()
        
        if not search_term or not search_term.strip():
            return [], {'load_time': 0, 'source': 'empty', 'count': 0}

        search_term = search_term.strip()
        
        # Check cache first
        cache_key = f"{search_term}_{site_id}_{limit}"
        if self._is_cache_valid(cache_key):
            self.logger.info(f"🔍 INVENTORY: Using cached search results for '{search_term}'")
            return self._search_cache[cache_key]['data'], {
                'load_time': time.time() - start_time,
                'source': 'cache'
            }

        try:
            # Primary search: MXAPIINVENTORY (site-specific)
            inventory_items = self._search_inventory_primary(search_term, site_id, limit)

            # Enhance with MXAPIITEM data for missing fields (description, etc.)
            enhanced_items = self._enhance_with_item_data(inventory_items, site_id)

            # If no items found in inventory, search MXAPIITEM for direct issue items
            if not enhanced_items:
                self.logger.info(f"🔍 INVENTORY: No items found in MXAPIINVENTORY, searching MXAPIITEM for direct issue")
                direct_issue_items = self._search_item_master_for_direct_issue(search_term, site_id, limit)
                enhanced_items = direct_issue_items

            # Cache the results
            self._search_cache[cache_key] = {
                'data': enhanced_items,
                'timestamp': time.time()
            }

            load_time = time.time() - start_time
            self.logger.info(f"🔍 INVENTORY: Found {len(enhanced_items)} items for '{search_term}' in {load_time:.3f}s")

            return enhanced_items, {
                'load_time': load_time,
                'source': 'api',
                'count': len(enhanced_items)
            }

        except Exception as e:
            self.logger.error(f"🔍 INVENTORY: Search failed for '{search_term}': {str(e)}")
            return [], {
                'load_time': time.time() - start_time,
                'source': 'error',
                'error': str(e)
            }

    def _search_inventory_primary(self, search_term: str, site_id: str, limit: int) -> List[Dict]:
        """
        Primary search using MXAPIINVENTORY endpoint.

        Args:
            search_term (str): Search term
            site_id (str): Site ID for filtering
            limit (int): Maximum results

        Returns:
            List[Dict]: Inventory items from MXAPIINVENTORY
        """
        base_url = getattr(self.token_manager, 'base_url', '')
        api_url = f"{base_url}/oslc/os/mxapiinventory"

        # Build search filters using proper OSLC syntax (no parentheses)
        # OSLC doesn't support parentheses grouping, so we need to use multiple conditions

        # Build search filter for MXAPIINVENTORY with partial search
        # RESTRICTED TO CURRENT WORK ORDER SITE ID ONLY - no cross-site search
        # Use the correct OSLC syntax: ="%term%" for partial search (from reference implementation)
        search_term_clean = search_term.replace('"', '\\"')
        oslc_filter = f'itemnum="%{search_term_clean}%" and siteid="{site_id}" and status="ACTIVE"'

        # Select ONLY the fields that actually exist in MXAPIINVENTORY
        # Based on API testing, these are the valid fields:
        select_fields = [
            "itemnum", "siteid", "location",
            "issueunit", "orderunit", "curbaltotal", "avblbalance",
            "status", "itemtype", "itemsetid"
        ]
        # Note: description, abc, vendor, manufacturer, modelnum, rotating, conditioncode
        # are NOT available in MXAPIINVENTORY

        # Add related table fields that actually exist
        invcost_fields = [
            "invcost.avgcost", "invcost.lastcost", "invcost.stdcost"
            # Note: invcost.currencycode does NOT exist
        ]

        all_fields = select_fields + invcost_fields

        params = {
            "oslc.select": ",".join(all_fields),
            "oslc.where": oslc_filter,
            "oslc.pageSize": str(limit),
            "lean": "1"
        }

        self.logger.info(f"🔍 INVENTORY: Searching MXAPIINVENTORY for '{search_term}'")
        self.logger.info(f"🔍 INVENTORY: API URL: {api_url}")
        self.logger.info(f"🔍 INVENTORY: Filter: {oslc_filter}")
        self.logger.info(f"🔍 INVENTORY: OSLC Select: {params['oslc.select']}")

        response = self.token_manager.session.get(
            api_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"},
            allow_redirects=True
        )

        self.logger.info(f"🔍 INVENTORY: Response status: {response.status_code}")

        if response.status_code != 200:
            self.logger.error(f"🔍 INVENTORY: API call failed with status {response.status_code}")
            self.logger.error(f"🔍 INVENTORY: Response text: {response.text}")
            raise Exception(f"API call failed: {response.status_code}")

        try:
            # Debug: Log the actual response content
            response_text = response.text
            self.logger.info(f"🔍 INVENTORY: Response content length: {len(response_text)}")
            self.logger.info(f"🔍 INVENTORY: Response content (first 200 chars): {response_text[:200]}")

            if not response_text.strip():
                self.logger.warning("🔍 INVENTORY: Empty response - no inventory items found")
                return []

            data = response.json()
            self.logger.info(f"🔍 INVENTORY: JSON keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

            items = data.get('member', data.get('rdfs:member', []))

            self.logger.info(f"🔍 INVENTORY: Raw response contains {len(items)} items")

            # Clean and process inventory data
            processed_items = []
            for item in items:
                processed_item = self._clean_inventory_data(item)
                if processed_item:
                    processed_items.append(processed_item)

            self.logger.info(f"🔍 INVENTORY: Processed {len(processed_items)} inventory items")
            return processed_items

        except Exception as e:
            self.logger.error(f"🔍 INVENTORY: Error parsing API response: {str(e)}")
            self.logger.error(f"🔍 INVENTORY: Raw response: {response.text[:500]}")
            raise Exception(f"Error parsing inventory data: {str(e)}")

    def _enhance_with_item_data(self, inventory_items: List[Dict], site_id: str) -> List[Dict]:
        """
        Enhance inventory items with additional data from MXAPIITEM.

        Args:
            inventory_items (List[Dict]): Items from MXAPIINVENTORY
            site_id (str): Site ID

        Returns:
            List[Dict]: Enhanced inventory items
        """
        if not inventory_items:
            return inventory_items

        enhanced_items = []
        
        for inv_item in inventory_items:
            itemnum = inv_item.get('itemnum')
            if not itemnum:
                enhanced_items.append(inv_item)
                continue

            try:
                # Get additional item data from MXAPIITEM (always fetch description from item master)
                item_data = self._get_item_details(itemnum)

                # Merge data (inventory data takes precedence for quantities/costs, item master for description)
                enhanced_item = {**inv_item}  # Start with inventory data
                enhanced_item['description'] = item_data.get('description', '')  # Always use item master description
                enhanced_item['itemtype'] = item_data.get('itemtype', enhanced_item.get('itemtype', ''))
                enhanced_item['data_source'] = 'inventory_enhanced'
                enhanced_item['is_direct_issue'] = False  # Items in inventory are NOT direct issue
                enhanced_items.append(enhanced_item)
                
            except Exception as e:
                self.logger.warning(f"🔍 INVENTORY: Failed to enhance item {itemnum}: {str(e)}")
                inv_item['data_source'] = 'inventory_only'
                inv_item['is_direct_issue'] = False  # Items in inventory are NOT direct issue
                enhanced_items.append(inv_item)

        return enhanced_items

    def _get_item_details(self, itemnum: str) -> Dict:
        """
        Get item details from MXAPIITEM.

        Args:
            itemnum (str): Item number

        Returns:
            Dict: Item details from MXAPIITEM
        """
        base_url = getattr(self.token_manager, 'base_url', '')
        api_url = f"{base_url}/oslc/os/mxapiitem"

        # Select fields from MXAPIITEM that actually exist (based on testing)
        select_fields = [
            "itemnum", "description", "issueunit", "orderunit", "itemsetid"
            # Note: conditioncode, nsn, commoditygroup, commodity may not exist
        ]

        params = {
            "oslc.select": ",".join(select_fields),
            "oslc.where": f'itemnum="{itemnum}" and status="ACTIVE"',
            "oslc.pageSize": "1",
            "lean": "1"
        }

        response = self.token_manager.session.get(
            api_url,
            params=params,
            timeout=(5.0, 15),
            headers={"Accept": "application/json"}
        )

        if response.status_code == 200:
            try:
                data = response.json()
                items = data.get('member', [])
                if items:
                    return self._clean_item_data(items[0])
            except Exception as e:
                self.logger.warning(f"🔍 INVENTORY: Failed to parse item data for {itemnum}: {str(e)}")

        return {}

    def _search_item_master_for_direct_issue(self, search_term: str, site_id: str, limit: int) -> List[Dict]:
        """
        Search MXAPIITEM for items not in inventory (direct issue items).

        Args:
            search_term (str): Search term
            site_id (str): Site ID (for reference)
            limit (int): Maximum results

        Returns:
            List[Dict]: Items from MXAPIITEM marked as direct issue
        """
        base_url = getattr(self.token_manager, 'base_url', '')
        api_url = f"{base_url}/oslc/os/mxapiitem"

        # Search MXAPIITEM for partial itemnum and description matches (ACTIVE status)
        # Use the correct OSLC syntax: ="%term%" for partial search (from reference implementation)
        search_term_clean = search_term.replace('"', '\\"')

        # Search strategies - ONLY ACTIVE status items (no PENDOBS or other statuses)
        search_filters = [
            # 1. Exact item number match
            f'itemnum="{search_term_clean}" and status="ACTIVE"',
            # 2. Partial item number match using LIKE pattern
            f'itemnum="%{search_term_clean}%" and status="ACTIVE"',
            # 3. Partial description match using LIKE pattern
            f'description="%{search_term_clean}%" and status="ACTIVE"'
        ]

        # Select fields from MXAPIITEM that actually exist (based on testing)
        select_fields = [
            "itemnum", "description", "issueunit", "orderunit", "itemsetid", "itemtype", "status"
        ]

        all_items = []
        found_item_nums = set()  # Track found items to avoid duplicates

        # Try each search filter
        for i, oslc_filter in enumerate(search_filters):
            self.logger.info(f"🔍 ITEM MASTER: Try #{i+1} - Filter: {oslc_filter}")

            params = {
                "oslc.select": ",".join(select_fields),
                "oslc.where": oslc_filter,
                "oslc.pageSize": str(limit),
                "lean": "1"
            }

            try:
                response = self.token_manager.session.get(
                    api_url,
                    params=params,
                    timeout=(5.0, 30),
                    headers={"Accept": "application/json"}
                )

                if response.status_code == 200:
                    data = response.json()
                    items = data.get('member', [])
                    self.logger.info(f"🔍 ITEM MASTER: Found {len(items)} items with filter #{i+1}")

                    # Add unique items only
                    for item in items:
                        itemnum = item.get('itemnum', '')
                        if itemnum and itemnum not in found_item_nums:
                            all_items.append(item)
                            found_item_nums.add(itemnum)

                    # If we found enough items, stop searching
                    if len(all_items) >= limit:
                        break

                else:
                    self.logger.error(f"🔍 ITEM MASTER: API call failed with status {response.status_code} for filter #{i+1}")

            except Exception as e:
                self.logger.error(f"🔍 ITEM MASTER: Error with filter #{i+1}: {str(e)}")

        # Convert to direct issue format
        direct_issue_items = []
        for item in all_items:
            direct_issue_item = self._convert_to_direct_issue_item(item, site_id)
            if direct_issue_item:
                direct_issue_items.append(direct_issue_item)

        # NO PENDOBS SEARCH - Only ACTIVE status items allowed
        # Direct issue items are only those found in MXAPIITEM with ACTIVE status
        # that are NOT found in MXAPIINVENTORY

        return direct_issue_items

    # REMOVED: _search_item_master_pendobs method
    # Only ACTIVE status items are allowed - no PENDOBS search

    def _convert_to_direct_issue_item(self, item_data: Dict, site_id: str) -> Dict:
        """
        Convert MXAPIITEM data to direct issue item format.

        Args:
            item_data (Dict): Raw item data from MXAPIITEM
            site_id (str): Site ID for reference

        Returns:
            Dict: Formatted direct issue item
        """
        return {
            'itemnum': item_data.get('itemnum', ''),
            'siteid': site_id,  # Reference site, not actual inventory location
            'location': 'DIRECT ISSUE',  # Highlight as direct issue
            'description': item_data.get('description', ''),
            'issueunit': item_data.get('issueunit', 'EA'),
            'orderunit': item_data.get('orderunit', 'EA'),
            'curbaltotal': 0.0,  # No inventory balance
            'avblbalance': 0.0,  # No available balance
            'status': item_data.get('status', 'ACTIVE'),
            'itemtype': item_data.get('itemtype', ''),
            'itemsetid': item_data.get('itemsetid', ''),
            'avgcost': 0.0,  # No cost data from item master
            'lastcost': 0.0,
            'stdcost': 0.0,
            'currency': '',  # No hardcoded currency
            'data_source': 'direct_issue',  # Mark as direct issue item
            'is_direct_issue': True  # Flag for UI highlighting
        }

    def _clean_inventory_data(self, raw_item: Dict) -> Dict:
        """Clean and normalize inventory data."""
        if not raw_item:
            return {}

        # Process invcost data
        cost_data = self._process_cost_data(raw_item.get('invcost', []))

        cleaned_item = {
            'itemnum': raw_item.get('itemnum', ''),
            'siteid': raw_item.get('siteid', ''),
            'location': raw_item.get('location', ''),
            'description': raw_item.get('description', ''),
            'issueunit': raw_item.get('issueunit', 'EA'),
            'orderunit': raw_item.get('orderunit', 'EA'),
            'curbaltotal': float(raw_item.get('curbaltotal', 0)),
            'avblbalance': float(raw_item.get('avblbalance', 0)),
            'status': raw_item.get('status', ''),
            'abc': raw_item.get('abc', ''),
            'vendor': raw_item.get('vendor', ''),
            'manufacturer': raw_item.get('manufacturer', ''),
            'modelnum': raw_item.get('modelnum', ''),
            'itemtype': raw_item.get('itemtype', ''),
            'rotating': raw_item.get('rotating', False),
            'conditioncode': raw_item.get('conditioncode', ''),
            'itemsetid': raw_item.get('itemsetid', ''),
            **cost_data
        }

        return cleaned_item

    def _clean_item_data(self, raw_item: Dict) -> Dict:
        """Clean and normalize item master data."""
        if not raw_item:
            return {}

        return {
            'itemnum': raw_item.get('itemnum', ''),
            'description': raw_item.get('description', ''),
            'issueunit': raw_item.get('issueunit', 'EA'),
            'orderunit': raw_item.get('orderunit', 'EA'),
            'conditioncode': raw_item.get('conditioncode', ''),
            'itemsetid': raw_item.get('itemsetid', ''),
            'nsn': raw_item.get('nsn', ''),
            'commoditygroup': raw_item.get('commoditygroup', ''),
            'commodity': raw_item.get('commodity', '')
        }

    def _process_cost_data(self, invcost_data) -> Dict:
        """Process cost data from invcost table."""
        cost_info = {
            'avgcost': 0.0,
            'lastcost': 0.0,
            'stdcost': 0.0,
            'currency': ''  # No hardcoded currency - get from actual data
        }

        if not invcost_data:
            return cost_info

        # Handle both dict and list formats
        if isinstance(invcost_data, dict):
            # Single cost record as dict
            cost_info['avgcost'] = float(invcost_data.get('avgcost', 0) or 0)
            cost_info['lastcost'] = float(invcost_data.get('lastcost', 0) or 0)
            cost_info['stdcost'] = float(invcost_data.get('stdcost', 0) or 0)
            cost_info['currency'] = invcost_data.get('currencycode', '') or ''
        elif isinstance(invcost_data, list):
            # Multiple cost records as list
            for cost_record in invcost_data:
                if not isinstance(cost_record, dict):
                    continue

                cost_type = cost_record.get('costtype', '').upper()
                # Try different field names for cost value
                cost_value = cost_record.get('avgcost') or cost_record.get('lastcost') or cost_record.get('stdcost') or cost_record.get('cost', 0)
                cost_value = float(cost_value or 0)
                currency = cost_record.get('currencycode', '')

                if cost_type == 'AVERAGE' or 'avgcost' in cost_record:
                    cost_info['avgcost'] = cost_value
                elif cost_type == 'LAST' or 'lastcost' in cost_record:
                    cost_info['lastcost'] = cost_value
                elif cost_type == 'STANDARD' or 'stdcost' in cost_record:
                    cost_info['stdcost'] = cost_value

                # Use the first currency found
                if currency and not cost_info['currency']:
                    cost_info['currency'] = currency

        return cost_info

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self._search_cache:
            return False
        
        cache_entry = self._search_cache[cache_key]
        return (time.time() - cache_entry['timestamp']) < self._cache_timeout

    def clear_cache(self):
        """Clear the search cache."""
        self._search_cache.clear()
        self.logger.info("🔍 INVENTORY: Search cache cleared")

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            'entries': len(self._search_cache),
            'timeout_seconds': self._cache_timeout
        }

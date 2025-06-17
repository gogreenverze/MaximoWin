#!/usr/bin/env python3
"""
Task Planned Materials Service

This service handles fetching and managing planned materials for work order tasks
from Maximo MXAPIWODETAIL API. It provides site-aware planned materials functionality
for tasks with specific statuses (APPR, INPRG, WMATL).

Author: Augment Agent
Date: 2025-01-27
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

class TaskPlannedMaterialsService:
    """
    Service for managing task planned materials from Maximo MXAPIWODETAIL API.

    This service provides:
    - Fetching planned materials for specific tasks
    - Site-aware material filtering
    - Status-based material access (APPR, INPRG, WMATL)
    - Efficient API calls with proper error handling
    """

    def __init__(self, token_manager):
        """
        Initialize the Task Planned Materials Service.

        Args:
            token_manager: Authentication token manager with session
        """
        self.token_manager = token_manager
        self.logger = logging.getLogger(__name__)

        # Planned materials are now available for all task statuses
        self.valid_statuses = []  # Empty list means all statuses are valid

        # Cache for planned materials (short-lived for real-time accuracy)
        self._materials_cache = {}
        self._cache_timeout = 300  # 5 minutes cache timeout

        # Clear cache on initialization to ensure fresh data with new implementation
        self._materials_cache.clear()
        self.logger.info("📦 MATERIALS: Service initialized with fresh cache")

    def is_session_valid(self) -> bool:
        """Check if the current session is valid."""
        return (hasattr(self.token_manager, 'username') and
                self.token_manager.username and
                hasattr(self.token_manager, 'session'))

    def should_show_planned_materials(self, task_status: str) -> bool:
        """
        Determine if planned materials should be shown for a task based on its status.

        Now returns True for all statuses as per user requirement.

        Args:
            task_status: Current status of the task

        Returns:
            bool: Always True - planned materials available for all task statuses
        """
        return True  # Materials now available for all task statuses

    def get_task_planned_materials(self, task_wonum: str, site_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Fetch planned materials for a specific task.

        Args:
            task_wonum: Work order number of the task
            site_id: Site ID for filtering materials

        Returns:
            tuple: (materials_list, metadata)
        """
        start_time = time.time()

        # Validate session
        if not self.is_session_valid():
            self.logger.error("Cannot fetch planned materials: Not logged in")
            return [], {'error': 'Not logged in', 'load_time': 0}

        # Check cache first
        cache_key = f"{task_wonum}_{site_id}"
        if self._is_cache_valid(cache_key):
            self.logger.info(f"📦 MATERIALS: Using cached data for task {task_wonum}")
            return self._materials_cache[cache_key]['data'], {
                'load_time': time.time() - start_time,
                'source': 'cache'
            }

        try:
            # Fetch planned materials from Maximo API
            materials = self._fetch_planned_materials_from_api(task_wonum, site_id)

            # Cache the results
            self._materials_cache[cache_key] = {
                'data': materials,
                'timestamp': time.time()
            }

            load_time = time.time() - start_time
            self.logger.info(f"📦 MATERIALS: Fetched {len(materials)} materials for task {task_wonum} in {load_time:.3f}s")

            return materials, {
                'load_time': load_time,
                'source': 'api',
                'count': len(materials)
            }

        except Exception as e:
            self.logger.error(f"Error fetching planned materials for task {task_wonum}: {str(e)}")
            return [], {
                'error': str(e),
                'load_time': time.time() - start_time
            }

    def _fetch_planned_materials_from_api(self, task_wonum: str, site_id: str) -> List[Dict[str, Any]]:
        """
        Fetch planned materials from Maximo MXAPIWODETAIL API using showplanmaterial relationship.

        Args:
            task_wonum: Work order number of the task
            site_id: Site ID for filtering

        Returns:
            List of planned material dictionaries
        """
        base_url = getattr(self.token_manager, 'base_url', '')
        api_url = f"{base_url}/oslc/os/mxapiwodetail"

        # Query wpmaterial table using the collection reference approach
        # This method fetches the wpmaterial_collectionref from the work order and then fetches materials from that collection

        # First, get the work order to find the wpmaterial_collectionref
        oslc_filter = f'wonum="{task_wonum}"'
        if site_id and site_id != "UNKNOWN":
            oslc_filter += f' and siteid="{site_id}"'

        params = {
            "oslc.select": "wonum,siteid,wpmaterial_collectionref",  # Get the collection reference
            "oslc.where": oslc_filter,
            "oslc.pageSize": "1",
            "lean": "1"
        }

        self.logger.info(f"📦 MATERIALS: Fetching planned materials for task {task_wonum}")
        self.logger.info(f"📦 MATERIALS: API URL: {api_url}")
        self.logger.info(f"📦 MATERIALS: Filter: {oslc_filter}")
        self.logger.info(f"📦 MATERIALS: OSLC Select: {params['oslc.select']}")

        response = self.token_manager.session.get(
            api_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"},
            allow_redirects=True
        )

        self.logger.info(f"📦 MATERIALS: Response status: {response.status_code}")

        if response.status_code != 200:
            self.logger.error(f"📦 MATERIALS: API call failed with status {response.status_code}")
            self.logger.error(f"📦 MATERIALS: Response text: {response.text}")
            raise Exception(f"API call failed: {response.status_code}")

        try:
            data = response.json()
            self.logger.info(f"📦 MATERIALS: Response data type: {type(data)}")

            # Extract the wpmaterial_collectionref from the work order
            materials = []

            if isinstance(data, dict):
                work_orders = data.get('member', data.get('rdfs:member', []))
                self.logger.info(f"📦 MATERIALS: Found {len(work_orders)} work orders in response")

                if work_orders and len(work_orders) > 0:
                    work_order = work_orders[0]
                    self.logger.info(f"📦 MATERIALS: Work order wonum: {work_order.get('wonum', 'UNKNOWN')}")

                    # Get the wpmaterial collection reference
                    collection_ref = work_order.get('wpmaterial_collectionref')
                    if collection_ref:
                        self.logger.info(f"📦 MATERIALS: Found wpmaterial_collectionref: {collection_ref}")

                        # Fix the hostname in the collection reference URL if needed
                        # Sometimes Maximo returns collection refs with different hostnames
                        base_url = getattr(self.token_manager, 'base_url', '')
                        if base_url and 'manage.v2x.maximotest.gov2x.com' in collection_ref:
                            # Extract the correct hostname from our base_url
                            import re
                            hostname_match = re.search(r'https://([^/]+)', base_url)
                            if hostname_match:
                                correct_hostname = hostname_match.group(1)
                                # Replace any hostname in the collection ref with the correct one
                                collection_ref = re.sub(r'https://[^/]+', f'https://{correct_hostname}', collection_ref)
                                self.logger.info(f"📦 MATERIALS: Fixed collection ref URL: {collection_ref}")

                        # Fetch materials from the collection reference
                        wpmaterials = self._fetch_from_collection_ref(collection_ref)

                        if wpmaterials:
                            self.logger.info(f"📦 MATERIALS: Found {len(wpmaterials)} materials from collection ref")

                            for i, material_data in enumerate(wpmaterials):
                                self.logger.info(f"📦 MATERIALS: Raw material {i+1} data: {material_data}")
                                if isinstance(material_data, dict):
                                    self.logger.info(f"📦 MATERIALS: Material {i+1} keys: {list(material_data.keys())}")

                                    # Check if this is just a localref - if so, fetch the actual material data
                                    if 'localref' in material_data and len(material_data.keys()) == 1:
                                        localref = material_data['localref']
                                        self.logger.info(f"📦 MATERIALS: Material {i+1} is a localref, fetching actual data from: {localref}")

                                        # Fix hostname in localref if needed
                                        base_url = getattr(self.token_manager, 'base_url', '')
                                        if base_url and 'manage.v2x.maximotest.gov2x.com' in localref:
                                            import re
                                            hostname_match = re.search(r'https://([^/]+)', base_url)
                                            if hostname_match:
                                                correct_hostname = hostname_match.group(1)
                                                localref = re.sub(r'https://[^/]+', f'https://{correct_hostname}', localref)
                                                self.logger.info(f"📦 MATERIALS: Fixed localref URL: {localref}")

                                        # Fetch the actual material data
                                        try:
                                            localref_response = self.token_manager.session.get(
                                                localref,
                                                timeout=(5.0, 30),
                                                headers={"Accept": "application/json"},
                                                allow_redirects=True
                                            )

                                            if localref_response.status_code == 200:
                                                actual_material_data = localref_response.json()
                                                self.logger.info(f"📦 MATERIALS: Fetched actual material data: {actual_material_data}")
                                                material_data = actual_material_data
                                            else:
                                                self.logger.warning(f"📦 MATERIALS: Failed to fetch localref data, status: {localref_response.status_code}")
                                                continue
                                        except Exception as e:
                                            self.logger.warning(f"📦 MATERIALS: Error fetching localref data: {str(e)}")
                                            continue

                                    cleaned_material = self._clean_material_data(material_data)
                                    if cleaned_material:
                                        self.logger.info(f"📦 MATERIALS: Cleaned material {i+1}: {cleaned_material['itemnum']} - {cleaned_material['description']}")
                                        materials.append(cleaned_material)
                                    else:
                                        self.logger.warning(f"📦 MATERIALS: Material {i+1} was filtered out during cleaning")
                        else:
                            self.logger.info(f"📦 MATERIALS: No materials found in collection reference")
                    else:
                        self.logger.warning(f"📦 MATERIALS: No wpmaterial_collectionref found in work order")
                else:
                    self.logger.info(f"📦 MATERIALS: No work order found for task {task_wonum}")

            self.logger.info(f"📦 MATERIALS: Found {len(materials)} planned materials for task {task_wonum}")
            return materials

        except Exception as e:
            self.logger.error(f"📦 MATERIALS: Error parsing API response: {str(e)}")
            raise Exception(f"Error parsing planned materials data: {str(e)}")

    def _fetch_from_collection_ref(self, collection_ref_url: str) -> List[Dict[str, Any]]:
        """
        Fetch planned materials from a collection reference URL.

        Args:
            collection_ref_url: The collection reference URL to fetch from

        Returns:
            List of material dictionaries
        """
        try:
            self.logger.info(f"📦 MATERIALS: Fetching from collection ref: {collection_ref_url}")

            response = self.token_manager.session.get(
                collection_ref_url,
                timeout=(5.0, 30),
                headers={"Accept": "application/json"},
                allow_redirects=True
            )

            self.logger.info(f"📦 MATERIALS: Collection ref response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                self.logger.info(f"📦 MATERIALS: Collection ref data type: {type(data)}")
                self.logger.info(f"📦 MATERIALS: Collection ref data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

                # Extract materials from the collection response
                if isinstance(data, dict):
                    materials = data.get('member', data.get('rdfs:member', []))
                    self.logger.info(f"📦 MATERIALS: Found {len(materials)} materials in collection ref")
                    return materials
                else:
                    self.logger.warning(f"📦 MATERIALS: Collection ref response is not a dict")
                    return []
            else:
                self.logger.error(f"📦 MATERIALS: Collection ref failed with status {response.status_code}")
                return []

        except Exception as e:
            self.logger.error(f"📦 MATERIALS: Error fetching from collection ref: {str(e)}")
            return []

    def _clean_material_data(self, material_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Clean and normalize planned material data.

        Args:
            material_data: Raw material data from API

        Returns:
            Cleaned material dictionary or None if invalid
        """
        try:
            # Helper function to get field value (try both spi: prefix and direct)
            def get_field(field_name):
                return material_data.get(field_name, material_data.get(f'spi:{field_name}', ''))

            # Extract and clean material fields - include ALL available fields from Maximo
            cleaned_material = {
                # Basic item information
                'itemnum': get_field('itemnum'),
                'description': get_field('description'),
                'description_longdescription': get_field('description_longdescription'),

                # Quantities and units
                'itemqty': float(get_field('itemqty') or 0),
                'orderunit': get_field('orderunit') or get_field('unit') or 'EA',
                'unit': get_field('unit') or get_field('orderunit') or 'EA',

                # Cost information
                'unitcost': float(get_field('unitcost') or 0),
                'linecost': float(get_field('linecost') or 0),
                'rate': float(get_field('rate') or 0),
                'plusplineprice': float(get_field('plusplineprice') or 0),
                'plusplistprice': float(get_field('plusplistprice') or 0),
                'unitcosthaschanged': bool(get_field('unitcosthaschanged')),
                'ratehaschanged': bool(get_field('ratehaschanged')),

                # Location and vendor information
                'storeloc': get_field('storeloc'),
                'vendor': get_field('vendor'),
                'itemsetid': get_field('itemsetid'),
                'orgid': get_field('orgid'),

                # Request and reservation information
                'directreq': bool(get_field('directreq')),
                'requestby': get_field('requestby'),
                'requiredate': get_field('requiredate'),
                'restype': get_field('restype'),
                'restype_description': get_field('restype_description'),

                # Line type and condition
                'linetype': get_field('linetype'),
                'linetype_description': get_field('linetype_description'),
                'conditioncode': get_field('conditioncode'),

                # Additional fields
                'wpitemid': get_field('wpitemid'),
                'displaywonum': get_field('displaywonum'),
                'hours': float(get_field('hours') or 0),
                'mktplcitem': bool(get_field('mktplcitem')),
                'pluspcustprovided': bool(get_field('pluspcustprovided')),

                # System fields
                '_rowstamp': get_field('_rowstamp'),
                'href': get_field('href'),
                'localref': get_field('localref'),
            }

            # Only return material if it has a valid item number
            if cleaned_material['itemnum']:
                return cleaned_material
            else:
                self.logger.debug("📦 MATERIALS: Skipping material without item number")
                return None

        except Exception as e:
            self.logger.error(f"📦 MATERIALS: Error cleaning material data: {str(e)}")
            return None

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._materials_cache:
            return False

        cache_age = time.time() - self._materials_cache[cache_key]['timestamp']
        return cache_age < self._cache_timeout

    def clear_cache(self):
        """Clear the materials cache."""
        self._materials_cache.clear()
        self.logger.info("📦 MATERIALS: Cache cleared")

    def check_workorder_materials_availability(self, parent_wonum: str, site_id: str) -> Dict[str, Any]:
        """
        Check if a parent work order has any planned materials across all its tasks.

        This is optimized for batch checking and provides material count information.

        Args:
            parent_wonum: Parent work order number
            site_id: Site ID for the work order

        Returns:
            Dict with availability info: {
                'has_materials': bool,
                'total_materials': int,
                'tasks_with_materials': int,
                'cache_hit': bool
            }
        """
        cache_key = f"wo_materials_{parent_wonum}_{site_id}"

        # Check cache first
        if self._is_cache_valid(cache_key):
            self.logger.info(f"📦 WO MATERIALS: Using cached availability for WO {parent_wonum}")
            cached_data = self._materials_cache[cache_key]['data']
            cached_data['cache_hit'] = True
            return cached_data

        try:
            self.logger.info(f"📦 WO MATERIALS: Checking materials availability for parent WO {parent_wonum}")

            # Get all tasks for this parent work order
            base_url = getattr(self.token_manager, 'base_url', '')
            api_url = f"{base_url}/oslc/os/mxapiwodetail"

            # Query for all tasks under this parent work order
            oslc_filter = f'parent="{parent_wonum}" and istask=1'
            if site_id and site_id != "UNKNOWN":
                oslc_filter += f' and siteid="{site_id}"'

            params = {
                "oslc.select": "wonum,wpmaterial_collectionref",  # Only get what we need for performance
                "oslc.where": oslc_filter,
                "oslc.pageSize": "100",  # Get up to 100 tasks
                "lean": "1"
            }

            self.logger.info(f"📦 WO MATERIALS: Fetching tasks for parent {parent_wonum}")

            response = self.token_manager.session.get(
                api_url,
                params=params,
                timeout=(5.0, 30),
                headers={"Accept": "application/json"},
                allow_redirects=True
            )

            if response.status_code != 200:
                self.logger.error(f"📦 WO MATERIALS: API call failed with status {response.status_code}")
                return {'has_materials': False, 'total_materials': 0, 'tasks_with_materials': 0, 'cache_hit': False}

            data = response.json()
            tasks = data.get('member', data.get('rdfs:member', []))

            self.logger.info(f"📦 WO MATERIALS: Found {len(tasks)} tasks for parent WO {parent_wonum}")

            total_materials = 0
            tasks_with_materials = 0

            # Check each task for materials (using collection reference count)
            for task in tasks:
                task_wonum = task.get('wonum', '')
                collection_ref = task.get('wpmaterial_collectionref', '')

                if collection_ref:
                    # Quick check: fetch collection reference to count materials
                    try:
                        # Fix hostname if needed
                        if 'manage.v2x.maximotest.gov2x.com' in collection_ref:
                            import re
                            hostname_match = re.search(r'https://([^/]+)', base_url)
                            if hostname_match:
                                correct_hostname = hostname_match.group(1)
                                collection_ref = re.sub(r'https://[^/]+', f'https://{correct_hostname}', collection_ref)

                        # Quick count query - just get the count, not full data
                        count_response = self.token_manager.session.get(
                            collection_ref + "?oslc.select=itemnum&lean=1",
                            timeout=(3.0, 10),  # Shorter timeout for count queries
                            headers={"Accept": "application/json"},
                            allow_redirects=True
                        )

                        if count_response.status_code == 200:
                            count_data = count_response.json()
                            materials = count_data.get('member', count_data.get('rdfs:member', []))
                            material_count = len(materials)

                            if material_count > 0:
                                total_materials += material_count
                                tasks_with_materials += 1
                                self.logger.info(f"📦 WO MATERIALS: Task {task_wonum} has {material_count} materials")

                    except Exception as e:
                        self.logger.warning(f"📦 WO MATERIALS: Error checking materials for task {task_wonum}: {str(e)}")
                        continue

            # Prepare result
            result = {
                'has_materials': total_materials > 0,
                'total_materials': total_materials,
                'tasks_with_materials': tasks_with_materials,
                'cache_hit': False
            }

            # Cache the result
            self._materials_cache[cache_key] = {
                'data': result.copy(),  # Store without cache_hit flag
                'timestamp': time.time()
            }

            self.logger.info(f"📦 WO MATERIALS: Parent WO {parent_wonum} - {total_materials} materials across {tasks_with_materials} tasks")
            return result

        except Exception as e:
            self.logger.error(f"📦 WO MATERIALS: Error checking availability for WO {parent_wonum}: {str(e)}")
            return {'has_materials': False, 'total_materials': 0, 'tasks_with_materials': 0, 'cache_hit': False}

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'cache_size': len(self._materials_cache),
            'cache_timeout': self._cache_timeout,
            'valid_statuses': self.valid_statuses
        }

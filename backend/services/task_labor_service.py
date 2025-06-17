#!/usr/bin/env python3
"""
Task Labor Service for Work Orders
Handles fetching labor records for tasks using MXAPIWODETAIL/labtrans endpoint
Following the exact same pattern as TaskPlannedMaterialsService
"""

import logging
import time
import json
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class TaskLaborService:
    """
    Service for fetching labor records for work order tasks.
    
    This service handles:
    - Fetching labor records using MXAPIWODETAIL/labtrans
    - Site-aware labor filtering
    - Intelligent caching (5-minute timeout)
    - Status-based access control
    """
    
    def __init__(self, token_manager):
        """
        Initialize the service with token manager.
        
        Args:
            token_manager: Authenticated token manager instance
        """
        self.token_manager = token_manager
        self.logger = logging.getLogger(f'{__name__}.{self.__class__.__name__}')
        
        # Cache for labor data (5-minute timeout)
        self._labor_cache = {}
        self._cache_timeout = 300  # 5 minutes
        
        # Status-based access control
        self._allowed_statuses = ['APPR', 'ASSIGN', 'WMATL', 'INPRG', 'READY', 'COMP']
        
        self.logger.info("🔧 TASK LABOR SERVICE: Initialized")
    
    def get_task_labor(self, task_wonum: str, site_id: str = None, 
                      task_status: str = None, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get labor records for a specific task.
        
        Args:
            task_wonum: Task work order number
            site_id: Site ID for filtering (optional)
            task_status: Task status for access control
            use_cache: Whether to use cached results
            
        Returns:
            Dictionary with success status, labor records, and metadata
        """
        try:
            # Check if labor should be shown for this status
            if task_status and task_status not in self._allowed_statuses:
                return {
                    'success': True,
                    'show_labor': False,
                    'message': f'Labor records not available for status: {task_status}',
                    'labor': [],
                    'metadata': {'status_restricted': True}
                }
            
            # Check cache first
            cache_key = f"{task_wonum}_{site_id or 'UNKNOWN'}"
            if use_cache and self._is_cache_valid(cache_key):
                self.logger.info(f"🔧 TASK LABOR: Using cached labor for {task_wonum}")
                cached_data = self._labor_cache[cache_key]['data']
                return {
                    'success': True,
                    'show_labor': True,
                    'labor': cached_data,
                    'metadata': {'cached': True, 'count': len(cached_data)}
                }
            
            # Fetch labor records
            labor_records = self._fetch_task_labor_records(task_wonum, site_id)
            
            # Cache the results
            self._labor_cache[cache_key] = {
                'data': labor_records,
                'timestamp': time.time()
            }
            
            self.logger.info(f"🔧 TASK LABOR: Found {len(labor_records)} labor records for {task_wonum}")
            
            return {
                'success': True,
                'show_labor': True,
                'labor': labor_records,
                'metadata': {'cached': False, 'count': len(labor_records)}
            }
            
        except Exception as e:
            self.logger.error(f"🔧 TASK LABOR: Error getting labor for {task_wonum}: {str(e)}")
            return {
                'success': False,
                'show_labor': False,
                'error': str(e),
                'labor': [],
                'metadata': {'error': True}
            }
    
    def _fetch_task_labor_records(self, task_wonum: str, site_id: str = None) -> List[Dict]:
        """
        Fetch labor records for a task using MXAPIWODETAIL/labtrans endpoint.
        
        Args:
            task_wonum: Task work order number
            site_id: Site ID for filtering
            
        Returns:
            List of labor record dictionaries
        """
        base_url = getattr(self.token_manager, 'base_url', '')
        api_url = f"{base_url}/oslc/os/mxapiwodetail"
        
        # Query labtrans table using the collection reference approach
        # This method fetches the labtrans_collectionref from the work order and then fetches labor from that collection
        
        # First, get the work order to find the labtrans_collectionref
        oslc_filter = f'wonum="{task_wonum}"'
        if site_id and site_id != "UNKNOWN":
            oslc_filter += f' and siteid="{site_id}"'
        
        params = {
            "oslc.select": "wonum,siteid,labtrans_collectionref",  # Get the collection reference
            "oslc.where": oslc_filter,
            "oslc.pageSize": "1",
            "lean": "1"
        }
        
        self.logger.info(f"🔧 TASK LABOR: Getting work order details for {task_wonum}")
        self.logger.info(f"🔧 TASK LABOR: API URL: {api_url}")
        self.logger.info(f"🔧 TASK LABOR: Filter: {oslc_filter}")
        
        response = self.token_manager.session.get(
            api_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"}
        )
        
        if response.status_code != 200:
            self.logger.error(f"🔧 TASK LABOR: Failed to get work order details: {response.status_code}")
            raise Exception(f"Failed to get work order details: {response.status_code}")
        
        data = response.json()
        if not data.get('member'):
            self.logger.warning(f"🔧 TASK LABOR: No work order found for {task_wonum}")
            return []
        
        work_order = data['member'][0]
        labtrans_ref = work_order.get('labtrans_collectionref')
        
        if not labtrans_ref:
            self.logger.info(f"🔧 TASK LABOR: No labtrans collection reference for {task_wonum}")
            return []
        
        # Now fetch the labor records from the collection reference
        self.logger.info(f"🔧 TASK LABOR: Fetching labor from collection: {labtrans_ref}")
        
        # Select comprehensive labor fields including REGULARHRS
        labor_select_fields = [
            "laborcode", "craft", "skilllevel", "laborhrs", "regularhrs", 
            "premiumpayhours", "startdate", "finishdate", "labtransid",
            "taskid", "vendor", "contractnum", "linecost", "rate"
        ]
        
        labor_params = {
            "oslc.select": ",".join(labor_select_fields),
            "oslc.pageSize": "100",  # Get up to 100 labor records
            "lean": "1"
        }
        
        labor_response = self.token_manager.session.get(
            labtrans_ref,
            params=labor_params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"}
        )
        
        if labor_response.status_code != 200:
            self.logger.error(f"🔧 TASK LABOR: Failed to fetch labor records: {labor_response.status_code}")
            raise Exception(f"Failed to fetch labor records: {labor_response.status_code}")
        
        labor_data = labor_response.json()
        labor_records = labor_data.get('member', [])
        
        self.logger.info(f"🔧 TASK LABOR: Retrieved {len(labor_records)} labor records")
        
        # Process and enhance labor records
        processed_records = []
        for record in labor_records:
            processed_record = self._process_labor_record(record)
            processed_records.append(processed_record)
        
        return processed_records
    
    def _process_labor_record(self, record: Dict) -> Dict:
        """
        Process and enhance a labor record.
        
        Args:
            record: Raw labor record from API
            
        Returns:
            Processed labor record
        """
        # Ensure numeric fields are properly formatted
        numeric_fields = ['laborhrs', 'regularhrs', 'premiumpayhours', 'linecost', 'rate', 'taskid']
        for field in numeric_fields:
            if field in record and record[field] is not None:
                try:
                    record[field] = float(record[field])
                except (ValueError, TypeError):
                    record[field] = 0.0
        
        # Format dates
        date_fields = ['startdate', 'finishdate']
        for field in date_fields:
            if field in record and record[field]:
                # Keep the original date format from Maximo
                pass
        
        return record
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._labor_cache:
            return False
        
        cache_age = time.time() - self._labor_cache[cache_key]['timestamp']
        return cache_age < self._cache_timeout
    
    def clear_cache(self) -> Dict[str, Any]:
        """Clear the labor cache."""
        cache_size = len(self._labor_cache)
        self._labor_cache.clear()
        self.logger.info(f"🔧 TASK LABOR: Cleared cache ({cache_size} entries)")
        
        return {
            'success': True,
            'message': f'Cleared {cache_size} cached labor entries',
            'cleared_count': cache_size
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self._labor_cache)
        valid_entries = sum(1 for key in self._labor_cache.keys() if self._is_cache_valid(key))
        
        return {
            'success': True,
            'total_entries': total_entries,
            'valid_entries': valid_entries,
            'expired_entries': total_entries - valid_entries,
            'cache_timeout_seconds': self._cache_timeout
        }

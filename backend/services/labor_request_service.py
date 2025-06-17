#!/usr/bin/env python3
"""
Labor Request Service for Work Orders
Based on MaterialRequestService model, adapted for labor addition to work orders
"""

import logging
import time
import json
from typing import Dict, Optional, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class LaborRequestService:
    """
    Service for adding labor requests to work orders using MXAPIWODETAIL API.
    
    This service handles:
    - Adding labor to work orders using AddChange action
    - Task-level labor assignments
    - Session-based authentication using token manager
    - Proper payload construction following Maximo API requirements
    """
    
    def __init__(self, token_manager, enhanced_profile_service=None):
        """Initialize the labor request service."""
        self.token_manager = token_manager
        self.enhanced_profile_service = enhanced_profile_service
        self.logger = logging.getLogger(f'{__name__}.{self.__class__.__name__}')
        
        # Performance tracking
        self._performance_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0,
            'last_request_time': None
        }
        
        # Debug logging for service initialization
        self.logger.info(f"🔧 INIT: LaborRequestService initialized")
        self.logger.info(f"🔧 INIT: enhanced_profile_service: {'✅ Available' if enhanced_profile_service else '❌ None'}")
        
    def add_labor_request(self, wonum: str, siteid: str, laborcode: str,
                         regularhrs: float, taskid: int, craft: Optional[str] = None,
                         startdate: Optional[str] = None, starttime: Optional[str] = None,
                         finishdate: Optional[str] = None, finishtime: Optional[str] = None,
                         payrate: Optional[float] = None, notes: Optional[str] = None,
                         task_wonum: Optional[str] = None, transtype: Optional[str] = None) -> Dict[str, Any]:
        """
        Add a labor request to a work order.
        
        Args:
            wonum: Work order number (parent work order)
            siteid: Site ID
            laborcode: Labor code to add
            regularhrs: Number of regular labor hours
            taskid: Task ID (numeric task identifier)
            craft: Optional craft specification
            startdate: Optional start date (ISO format)
            finishdate: Optional finish date (ISO format)
            notes: Optional notes
            task_wonum: Optional task work order number (for task-level requests)
            
        Returns:
            Dict containing success status and response data
        """
        start_time = time.time()
        
        try:
            # Validate session
            if not self.is_session_valid():
                self.logger.error("Cannot add labor: Not logged in")
                return {'success': False, 'error': 'Not logged in'}
            
            # Validate required parameters
            if not all([wonum, siteid, laborcode, regularhrs, taskid]):
                missing = [param for param, value in [
                    ('wonum', wonum), ('siteid', siteid), ('laborcode', laborcode),
                    ('regularhrs', regularhrs), ('taskid', taskid)
                ] if not value]
                self.logger.error(f"Missing required parameters: {missing}")
                return {'success': False, 'error': f'Missing required parameters: {missing}'}

            # Validate regular hours
            try:
                regularhrs = float(regularhrs)
                if regularhrs <= 0:
                    return {'success': False, 'error': 'Regular hours must be greater than 0'}
            except (ValueError, TypeError):
                return {'success': False, 'error': 'Invalid regular hours value'}
            
            # Get user information
            username = getattr(self.token_manager, 'username', 'SYSTEM')
            
            # Always use parent wonum for the top-level payload, not task wonum
            target_wonum = wonum  # Use parent work order number

            self.logger.info(f"🔧 LABOR REQUEST: Adding labor {laborcode} ({regularhrs}h) to Parent WO {target_wonum}, Task {taskid}")

            # Get work order data (following MaterialRequestService pattern)
            wo_data = self._get_work_order_full(target_wonum, siteid)
            if not wo_data:
                return {
                    'success': False,
                    'error': f'Work order {target_wonum} not found or not accessible'
                }

            # Construct the labor payload
            labor_payload = self._construct_labor_payload(
                wo_data=wo_data,
                laborcode=laborcode,
                regularhrs=regularhrs,
                taskid=taskid,
                craft=craft,
                startdate=startdate,
                starttime=starttime,
                finishdate=finishdate,
                finishtime=finishtime,
                payrate=payrate,
                notes=notes,
                username=username,
                transtype=transtype
            )

            # Make the API request
            result = self._make_labor_request(target_wonum, labor_payload)
            
            # Update performance stats
            request_time = time.time() - start_time
            self._update_performance_stats(request_time, result.get('success', False))
            
            if result.get('success'):
                self.logger.info(f"✅ LABOR REQUEST: Successfully added labor {laborcode} to WO {target_wonum}")
            else:
                self.logger.error(f"❌ LABOR REQUEST: Failed to add labor {laborcode} to WO {target_wonum}: {result.get('error')}")
            
            return result
            
        except Exception as e:
            request_time = time.time() - start_time
            self._update_performance_stats(request_time, False)
            self.logger.error(f"Exception in add_labor_request: {e}")
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}
    
    def is_session_valid(self) -> bool:
        """Check if the current session is valid."""
        return (hasattr(self.token_manager, 'username') and 
                self.token_manager.username and 
                hasattr(self.token_manager, 'session') and 
                self.token_manager.session)
    
    def _construct_labor_payload(self, wo_data: Dict, laborcode: str, regularhrs: float,
                                taskid: int, craft: Optional[str] = None,
                                startdate: Optional[str] = None, starttime: Optional[str] = None,
                                finishdate: Optional[str] = None, finishtime: Optional[str] = None,
                                payrate: Optional[float] = None, notes: Optional[str] = None,
                                username: str = 'SYSTEM', transtype: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Construct the labor payload for the API request following MaterialRequestService pattern.

        Args:
            wo_data: Work order data dictionary
            laborcode: Labor code
            regularhrs: Regular labor hours
            taskid: Task ID
            craft: Optional craft
            startdate: Optional start date
            finishdate: Optional finish date
            notes: Optional notes
            username: Username for the request

        Returns:
            Labor payload list (AddChange format)
        """
        wonum = wo_data.get('wonum')
        siteid = wo_data.get('siteid')

        # Create new labor entry following EXACT MxLoader pattern
        new_labor = {
            "laborcode": laborcode,
            "taskid": taskid,
            "genapprservreceipt": 1  # Always approved like MxLoader
        }

        # Add start date in ISO format like MxLoader
        if startdate:
            new_labor["startdate"] = f"{startdate}T00:00:00"

        # Add start time in MxLoader format (1970-01-01T + time)
        if starttime:
            new_labor["starttime"] = f"1970-01-01T{starttime}:00"

        # Add finish time in MxLoader format (1970-01-01T + time)
        if finishtime:
            new_labor["finishtime"] = f"1970-01-01T{finishtime}:00"

        # Add transaction type if provided
        if transtype:
            new_labor["transtype"] = transtype

        # Create AddChange payload with ONLY wonum and siteid (like MxLoader)
        addchange_payload = [{
            "_action": "AddChange",
            "wonum": wonum,  # Parent work order number
            "siteid": siteid,
            "labtrans": [new_labor]
        }]

        # LOG THE ENTIRE PAYLOAD STRUCTURE
        self.logger.info("🎯 COMPLETE LABOR PAYLOAD BEING SENT TO MAXIMO:")
        self.logger.info("="*60)
        self.logger.info(f"👷 FULL ADDCHANGE PAYLOAD:")
        self.logger.info(json.dumps(addchange_payload, indent=2))
        self.logger.info("="*60)
        self.logger.info(f"👷 LABOR PAYLOAD ONLY:")
        self.logger.info(json.dumps(new_labor, indent=2))
        self.logger.info("="*60)

        return addchange_payload
    
    def _make_labor_request(self, wonum: str, payload: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Make the actual labor request to the MXAPIWODETAIL API following MaterialRequestService pattern.

        Args:
            wonum: Work order number
            payload: Labor payload (AddChange format)

        Returns:
            Response dictionary
        """
        try:
            base_url = getattr(self.token_manager, 'base_url', '')
            api_url = f"{base_url}/oslc/os/mxapiwodetail"

            # Use the exact same parameters and headers as MaterialRequestService
            params = {
                'lean': '1',
                'ignorecollectionref': '1',
                'ignorekeyref': '1',
                'ignorers': '1',
                'mxlaction': 'addchange'
            }

            headers = {
                'x-method-override': 'BULK',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            self.logger.info(f"🔧 LABOR API: Making request to {api_url}")
            self.logger.debug(f"🔧 LABOR API: Payload: {json.dumps(payload, indent=2)}")

            response = self.token_manager.session.post(
                api_url,
                json=payload,
                params=params,
                headers=headers,
                timeout=(3.05, 30)  # Same timeout as materials
            )

            self.logger.info(f"🔍 LABOR API: Response status: {response.status_code}")

            if response.status_code >= 400:
                return {
                    'success': False,
                    'error': f'API call failed with status {response.status_code}: {response.text}'
                }

            result_data = response.json() if response.content else {}

            # Handle response exactly like MaterialRequestService
            if isinstance(result_data, list) and len(result_data) > 0:
                response_data = result_data[0]
                if '_responsedata' in response_data and 'Error' in response_data['_responsedata']:
                    error = response_data['_responsedata']['Error']
                    error_message = error.get('message', 'Unknown error')
                    error_code = error.get('reasonCode', 'Unknown code')
                    return {
                        'success': False,
                        'error': f"Maximo Error [{error_code}]: {error_message}",
                        'error_code': error_code
                    }
                elif '_responsemeta' in response_data and response_data['_responsemeta'].get('status') == '204':
                    # Clear labor cache after successful addition
                    self._clear_labor_cache(wonum)
                    return {
                        'success': True,
                        'message': f'Labor successfully added to work order {wonum}',
                        'data': result_data
                    }

            # Clear labor cache after successful addition
            self._clear_labor_cache(wonum)
            return {
                'success': True,
                'message': f'Labor successfully added to work order {wonum}',
                'data': result_data
            }

        except Exception as e:
            self.logger.error(f"Exception in _make_labor_request: {e}")
            return {
                'success': False,
                'error': f'Request failed: {str(e)}'
            }

    def _format_datetime_for_maximo(self, date_str: str, time_str: str) -> str:
        """
        Format date and time strings to Maximo-compatible datetime format.

        Args:
            date_str: Date string in YYYY-MM-DD format (e.g., "2025-06-16")
            time_str: Time string in various formats (e.g., "02:15", "14:30", "2:15 PM")

        Returns:
            Datetime string in ISO format for Maximo (e.g., "2025-06-16T07:15:00")
        """
        if not date_str or not time_str:
            return ""

        try:
            # Clean up the time string
            time_str = time_str.strip()

            # Parse time - handle HH:MM format
            if ':' in time_str:
                time_parts = time_str.split(':')
                if len(time_parts) >= 2:
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    # Ensure valid time
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        # Format as ISO datetime
                        return f"{date_str}T{hour:02d}:{minute:02d}:00"

            # Default fallback - use midnight
            return f"{date_str}T00:00:00"

        except Exception as e:
            self.logger.warning(f"⚠️ DATETIME FORMAT: Failed to format datetime '{date_str}' + '{time_str}': {e}")
            return f"{date_str}T00:00:00" if date_str else ""

    def _update_performance_stats(self, response_time: float, success: bool):
        """Update performance statistics."""
        self._performance_stats['total_requests'] += 1
        self._performance_stats['last_request_time'] = time.time()
        
        if success:
            self._performance_stats['successful_requests'] += 1
        else:
            self._performance_stats['failed_requests'] += 1
        
        # Update average response time
        total_requests = self._performance_stats['total_requests']
        current_avg = self._performance_stats['avg_response_time']
        self._performance_stats['avg_response_time'] = (
            (current_avg * (total_requests - 1) + response_time) / total_requests
        )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return self._performance_stats.copy()

    def _get_work_order_full(self, wonum: str, siteid: str) -> Optional[Dict]:
        """Get complete work order data (following MaterialRequestService pattern)."""
        try:
            base_url = getattr(self.token_manager, 'base_url', '')
            api_url = f"{base_url}/oslc/os/mxapiwodetail"

            params = {
                'oslc.where': f'wonum="{wonum}" and siteid="{siteid}"',
                'oslc.select': '*',
                'lean': '1'
            }

            response = self.token_manager.session.get(
                api_url,
                params=params,
                timeout=(3.05, 30),
                headers={"Accept": "application/json"}
            )

            if response.status_code == 200:
                data = response.json()
                if 'member' in data and data['member']:
                    return data['member'][0]
            return None

        except Exception as e:
            return None

    def _clear_labor_cache(self, wonum: str):
        """
        Clear labor cache after successful labor addition.

        Args:
            wonum: Work order number
        """
        # Clear labor cache if task_labor_service is available
        # Note: This would need to be injected if we want to clear the cache
        # For now, just log that we would clear it
        self.logger.info(f"🔄 CACHE: Would clear labor cache after adding labor to WO {wonum}")
        # TODO: Implement cache clearing when task_labor_service is available

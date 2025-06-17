#!/usr/bin/env python3
"""
Material Request Service for Work Orders
Based on successful_material_addition.py model, adapted for Flask app session management
"""

import logging
import time
import json
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class MaterialRequestService:
    """
    Service for adding material requests to work orders using MXAPIWODETAIL API.
    
    This service handles:
    - Adding materials to work orders using AddChange action
    - Direct request vs location-based requests
    - Session-based authentication using token manager
    - Proper payload construction following Maximo API requirements
    """
    
    def __init__(self, token_manager, task_materials_service=None, enhanced_profile_service=None, inventory_search_service=None):
        """
        Initialize the material request service.

        Args:
            token_manager: The MaximoTokenManager instance for API calls
            task_materials_service: The TaskPlannedMaterialsService instance for cache management
            enhanced_profile_service: The EnhancedProfileService instance for getting PersonID
            inventory_search_service: The InventorySearchService instance for inventory cache management
        """
        self.token_manager = token_manager
        self.task_materials_service = task_materials_service
        self.enhanced_profile_service = enhanced_profile_service
        self.inventory_search_service = inventory_search_service
        self.logger = logger

        # Debug logging for service initialization
        self.logger.info(f"🔧 INIT: MaterialRequestService initialized")
        self.logger.info(f"🔧 INIT: task_materials_service: {'✅ Available' if task_materials_service else '❌ None'}")
        self.logger.info(f"🔧 INIT: enhanced_profile_service: {'✅ Available' if enhanced_profile_service else '❌ None'}")
        self.logger.info(f"🔧 INIT: inventory_search_service: {'✅ Available' if inventory_search_service else '❌ None'}")
        
    def add_material_request(self, wonum: str, siteid: str, itemnum: str,
                           quantity: float, taskid: int, location: Optional[str] = None,
                           directreq: bool = True, notes: Optional[str] = None,
                           requestby: Optional[str] = None, task_wonum: Optional[str] = None) -> Dict[str, Any]:
        """
        Add a material request to a work order.

        Args:
            wonum (str): Parent work order number (e.g. "2021-1744762")
            siteid (str): Site ID
            itemnum (str): Item number to request
            quantity (float): Quantity to request
            taskid (int): Numeric task ID for Maximo API (e.g. 10, 20, 30)
            location (str, optional): Location for material (if not direct request)
            directreq (bool): Whether this is a direct request (default: True)
            notes (str, optional): Additional notes for the request
            requestby (str, optional): Person ID who is requesting the material
            task_wonum (str, optional): Task work order number for validation (e.g. "2021-1835482")

        Returns:
            Dict containing success status and response data
        """
        try:
            wo_data = self._get_work_order_full(wonum, siteid)
            if not wo_data:
                return {
                    'success': False,
                    'error': f'Work order {wonum} not found or not accessible'
                }

            # DEBUG: Log work order type and task information
            if wo_data.get('istask') == 1:
                actual_taskid = wo_data.get('taskid')
                self.logger.info(f"🔍 TASK DEBUG: Work order {wonum} is a TASK with taskid={actual_taskid}")
                self.logger.info(f"🔍 TASK DEBUG: Material will be added to parent WO with taskid={taskid}")
            else:
                self.logger.info(f"🔍 TASK DEBUG: Work order {wonum} is a PARENT work order")
                self.logger.info(f"🔍 TASK DEBUG: Material will be added to parent WO with taskid={taskid}")

            # Additional validation if task_wonum is provided
            if task_wonum:
                self.logger.info(f"🔍 TASK DEBUG: Task wonum provided for validation: {task_wonum}")
                # Optionally validate that the task_wonum exists and belongs to this parent WO
                # This validation can be added later if needed

            if not self._validate_item_for_site(itemnum, siteid):
                return {
                    'success': False,
                    'error': f'Item {itemnum} is not valid for site {siteid}'
                }

            result = self._add_material_with_addchange(wo_data, itemnum, quantity, taskid, location, directreq, notes, requestby)
            return result

        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to add material request: {str(e)}'
            }
    
    def _get_work_order_full(self, wonum: str, siteid: str) -> Optional[Dict]:
        """Get complete work order data."""
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
    
    def _validate_item_for_site(self, itemnum: str, siteid: str) -> bool:
        """
        Validate that the item exists and is valid for the site.
        This is a simplified validation - in production you might want more thorough checks.
        """
        try:
            base_url = getattr(self.token_manager, 'base_url', '')
            
            # Check if item exists in inventory for this site
            inventory_url = f"{base_url}/oslc/os/mxapiinventory"
            params = {
                'oslc.where': f'itemnum="{itemnum}" and siteid="{siteid}"',
                'oslc.select': 'itemnum,siteid,status',
                'oslc.pageSize': '1',
                'lean': '1'
            }
            
            response = self.token_manager.session.get(
                inventory_url,
                params=params,
                timeout=(3.05, 10),
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'member' in data and data['member']:
                    return True
            
            # If not found in inventory, check if it exists in item master
            item_url = f"{base_url}/oslc/os/mxapiitem"
            params = {
                'oslc.where': f'itemnum="{itemnum}"',
                'oslc.select': 'itemnum,status',
                'oslc.pageSize': '1',
                'lean': '1'
            }
            
            response = self.token_manager.session.get(
                item_url,
                params=params,
                timeout=(3.05, 10),
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'member' in data and data['member']:
                    item = data['member'][0]
                    # Check if item is active
                    return item.get('status', '').upper() == 'ACTIVE'
            
            return False

        except Exception as e:
            return False
    
    def _add_material_with_addchange(self, wo_data: Dict, itemnum: str, quantity: float,
                                   taskid: str, location: Optional[str], directreq: bool, notes: Optional[str],
                                   requestby: Optional[str]) -> Dict[str, Any]:
        """
        Add material using AddChange action, following the successful_material_addition.py model.
        """
        try:
            wonum = wo_data.get('wonum')
            siteid = wo_data.get('siteid')

            # Create new material entry EXACTLY like successful_material_addition.py
            new_material = {
                "itemnum": itemnum,
                "itemqty": quantity,
                "directreq": directreq,
                "requestby": self._get_validated_requestby(requestby, directreq)  # Use validated requestby
            }

            # Add taskid (MANDATORY - this is the key fix for adding to specific task)
            new_material["taskid"] = taskid

            # Add location if provided (exactly like successful_material_addition.py)
            if location:
                new_material["location"] = location

            # Add notes as remarks if provided
            if notes:
                new_material["remarks"] = notes
            
            # Create AddChange payload EXACTLY like successful_material_addition.py
            addchange_payload = [{
                "_action": "AddChange",
                "wonum": wonum,
                "siteid": siteid,
                "description": wo_data.get('description'),
                "status": wo_data.get('status'),
                "assetnum": wo_data.get('assetnum'),
                "location": wo_data.get('location'),
                "wpmaterial": [new_material]  # Only the new material, not existing ones
            }]

            # LOG THE ENTIRE PAYLOAD STRUCTURE
            self.logger.info("🎯 COMPLETE PAYLOAD BEING SENT TO MAXIMO:")
            self.logger.info("="*60)
            self.logger.info(f"📦 FULL ADDCHANGE PAYLOAD:")
            self.logger.info(json.dumps(addchange_payload, indent=2))
            self.logger.info("="*60)
            self.logger.info(f"📦 MATERIAL PAYLOAD ONLY:")
            self.logger.info(json.dumps(new_material, indent=2))
            self.logger.info("="*60)

            base_url = getattr(self.token_manager, 'base_url', '')
            api_url = f"{base_url}/oslc/os/mxapiwodetail"

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

            response = self.token_manager.session.post(
                api_url,
                json=addchange_payload,
                params=params,
                headers=headers,
                timeout=(3.05, 30)
            )

            if response.status_code >= 400:
                return {
                    'success': False,
                    'error': f'API call failed with status {response.status_code}: {response.text}'
                }

            result_data = response.json() if response.content else {}

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
                    # Clear materials cache after successful addition
                    self._clear_materials_cache(wonum, siteid)
                    return {
                        'success': True,
                        'message': f'Material {itemnum} added successfully to work order {wonum}',
                        'data': result_data
                    }

            # Clear materials cache after successful addition
            self._clear_materials_cache(wonum, siteid)
            return {
                'success': True,
                'message': f'Material {itemnum} added successfully to work order {wonum}',
                'data': result_data
            }

        except Exception as e:
            error_msg = str(e)

            # Check for specific Maximo person validation error
            if "BMXAA3097E" in error_msg or "person does not exist or is not active" in error_msg.lower():
                self.logger.error(f"❌ PERSON VALIDATION: Maximo rejected requestby='{requestby}' for location-based request")
                return {
                    'success': False,
                    'error': f'Person validation failed: The person "{requestby}" does not exist or is not active in Maximo. This error typically occurs with location-based requests (directreq=0). Try using a direct request instead.',
                    'error_code': 'PERSON_VALIDATION_FAILED',
                    'suggestion': 'Use direct request (directreq=1) or verify the person exists and is active in Maximo'
                }

            return {
                'success': False,
                'error': f'Failed to add material: {error_msg}'
            }

    def _get_validated_requestby(self, requestby: str, directreq: bool) -> str:
        """
        Get validated requestby value based on request type.

        For location-based requests (directreq=0), Maximo requires the exact PersonID.
        For direct requests (directreq=1), Maximo is more lenient.

        Args:
            requestby: Original requestby value
            directreq: Whether this is a direct request

        Returns:
            Validated requestby value
        """
        if directreq:
            # Direct requests: Use the provided value as-is (more lenient)
            self.logger.info(f"🔍 REQUESTBY: Direct request - using provided value: {requestby}")
            return requestby
        else:
            # Location-based requests: Use PersonID from Enhanced Profile
            self.logger.info(f"🔍 REQUESTBY: Location-based request - getting PersonID from Enhanced Profile")

            if self.enhanced_profile_service:
                try:
                    user_profile = self.enhanced_profile_service.get_user_profile()
                    if user_profile and user_profile.get('personid'):
                        person_id = user_profile.get('personid')
                        self.logger.info(f"✅ REQUESTBY: Using PersonID from Enhanced Profile: {person_id}")
                        return person_id
                    else:
                        self.logger.warning(f"⚠️ REQUESTBY: No PersonID found in Enhanced Profile, using fallback: {requestby}")
                        return requestby
                except Exception as e:
                    self.logger.error(f"❌ REQUESTBY: Error getting PersonID from Enhanced Profile: {e}")
                    self.logger.warning(f"⚠️ REQUESTBY: Using fallback value: {requestby}")
                    return requestby
            else:
                self.logger.warning(f"⚠️ REQUESTBY: No Enhanced Profile service available, using provided value: {requestby}")
                return requestby

    def _clear_materials_cache(self, wonum: str, siteid: str):
        """
        Clear materials and inventory cache after successful material addition.

        Args:
            wonum: Work order number
            siteid: Site ID
        """
        # Clear materials cache
        if self.task_materials_service:
            try:
                self.task_materials_service.clear_cache()
                self.logger.info(f"🔄 CACHE: Cleared materials cache after adding material to WO {wonum}")
            except Exception as e:
                self.logger.warning(f"🔄 CACHE: Failed to clear materials cache: {str(e)}")
        else:
            self.logger.warning("🔄 CACHE: No task_materials_service available for cache clearing")

        # Clear inventory cache to ensure real-time quantity updates
        if self.inventory_search_service:
            try:
                self.inventory_search_service.clear_cache()
                self.logger.info(f"🔄 CACHE: Cleared inventory cache after adding material to WO {wonum}")
            except Exception as e:
                self.logger.warning(f"🔄 CACHE: Failed to clear inventory cache: {str(e)}")
        else:
            self.logger.warning("🔄 CACHE: No inventory_search_service available for cache clearing")


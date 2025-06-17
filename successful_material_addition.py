#!/usr/bin/env python3
"""
Successful Material Addition - Using valid item for the site
Based on the working MxLoader approach with correct item validation
"""

import os
import requests
import json
from dotenv import load_dotenv
import urllib3
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SuccessfulMaterialAddition:
    def __init__(self):
        load_dotenv()
        self.base_url = os.getenv('MAXIMO_BASE_URL')
        self.api_key = os.getenv('MAXIMO_API_KEY')
        self.verify_ssl = os.getenv('MAXIMO_VERIFY_SSL', 'True').lower() == 'true'
        
        self.session = requests.Session()
        self.session.headers.update({
            'apikey': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def make_request(self, method: str, endpoint: str, data=None, params=None, headers=None):
        url = f"{self.base_url}/api/os/{endpoint}"
        
        # Add any additional headers
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)
        
        response = self.session.request(
            method=method, 
            url=url, 
            json=data, 
            params=params, 
            headers=request_headers,
            verify=self.verify_ssl
        )
        
        print(f"{method} {url} - Status: {response.status_code}")
        
        if response.status_code >= 400:
            print(f"Error: {response.text}")
            return None
        
        return response.json() if response.content else {}
    
    def get_work_order_full(self, wonum):
        """Get complete work order data"""
        response = self.make_request('GET', 'MXAPIWODETAIL', params={
            'oslc.where': f'WONUM="{wonum}"',
            'oslc.select': '*',
            'lean': '1'
        })
        
        if response and 'member' in response and response['member']:
            return response['member'][0]
        return None
    
    def get_existing_material_as_template(self, wo):
        """Get an existing material from the work order to use as template"""
        print(f"🔍 Using existing material as template")

        existing_materials = wo.get('wpmaterial', [])
        if existing_materials:
            template_material = existing_materials[0]
            itemnum = template_material.get('itemnum')
            print(f"✅ Found template material: {itemnum}")
            print(f"   Description: {template_material.get('description')}")
            print(f"   Order Unit: {template_material.get('orderunit')}")
            return itemnum

        return None
    
    def add_material_with_valid_item(self, wonum, itemnum=None, location=None, directreq=True, quantity=1):
        """Add material using a valid item for the site"""
        print(f"🎯 ADDING MATERIAL WITH VALID ITEM")

        # Get work order
        wo = self.get_work_order_full(wonum)
        if not wo:
            print(f"❌ Work order {wonum} not found")
            return None

        siteid = wo.get('siteid')
        print(f"✅ Work Order: {wonum} (Site: {siteid})")

        # Find valid item if not provided
        if not itemnum:
            itemnum = self.get_existing_material_as_template(wo)
            if not itemnum:
                print(f"❌ No existing materials found to use as template")
                return None

            print(f"✅ Using template item: {itemnum}")

        # Get existing materials
        existing_materials = wo.get('wpmaterial', [])
        print(f"✅ Existing materials: {len(existing_materials)}")

        # Debug: Check what date fields exist in existing materials
        if existing_materials:
            sample_material = existing_materials[0]
            date_fields = [key for key in sample_material.keys() if 'date' in key.lower()]
            if date_fields:
                print(f"🔍 Date fields found in existing materials: {date_fields}")
                for field in date_fields:
                    print(f"   {field}: {sample_material.get(field)}")
            else:
                print(f"🔍 No date fields found in existing materials")

        # Create new material entry
        new_material = {
            "itemnum": itemnum,
            "itemqty": quantity,
            "directreq": directreq,
            "requestby": "TINU.THOMAS"  # Explicitly set the requestedby field
        }

        # Try without setting requiredate - let Maximo handle it
        print(f"🔍 Not setting requiredate - letting Maximo handle it automatically")
        print(f"✅ Setting requestedby to: TINU.THOMAS")

        # Add location if provided
        if location:
            new_material["location"] = location
            print(f"✅ Using location: {location}")

        print(f"✅ Direct request: {directreq}")
        print(f"✅ Quantity: {quantity}")

        # Don't include existing materials - only add the new one
        # This avoids issues with old dates in existing materials
        new_materials_only = [new_material]

        # Create AddChange payload exactly like MxLoader
        addchange_payload = [{
            "_action": "AddChange",
            "wonum": wonum,
            "siteid": siteid,
            "description": wo.get('description'),
            "status": wo.get('status'),
            "assetnum": wo.get('assetnum'),
            "location": wo.get('location'),
            "wpmaterial": new_materials_only
        }]

        print(f"📦 AddChange Payload (showing new material only):")
        print(json.dumps(new_material, indent=2))

        # Use the exact MxLoader parameters and headers
        params = {
            'lean': '1',
            'ignorecollectionref': '1',
            'ignorekeyref': '1',
            'ignorers': '1',
            'mxlaction': 'addchange'
        }

        headers = {
            'x-method-override': 'BULK'
        }

        # Make the request exactly like MxLoader
        response = self.make_request('POST', 'MXAPIWODETAIL',
                                   data=addchange_payload,
                                   params=params,
                                   headers=headers)

        return response
    
    def verify_material_addition(self, wonum, itemnum):
        """Verify that the material was added successfully"""
        print(f"🔍 VERIFYING MATERIAL ADDITION")
        
        wo = self.get_work_order_full(wonum)
        if not wo:
            return False
        
        materials = wo.get('wpmaterial', [])
        print(f"✅ Total materials after addition: {len(materials)}")
        
        # Look for the new material
        for material in materials:
            if material.get('itemnum') == itemnum:
                print(f"✅ SUCCESS! Found new material:")
                print(f"   Item: {material.get('itemnum')}")
                print(f"   Quantity: {material.get('itemqty')}")
                print(f"   Description: {material.get('description')}")
                return True
        
        print(f"❌ Material {itemnum} not found in work order")
        return False

def main():
    """Successfully add material using valid item with specific parameters"""
    adder = SuccessfulMaterialAddition()

    # Target
    task_wonum = "2021-1984417"

    print(f"🚀 SUCCESSFUL MATERIAL ADDITION WITH LOCATION")
    print(f"📋 Task: {task_wonum}")

    try:
        # Add material with specific parameters: directreq=1 (True) - direct request
        result = adder.add_material_with_valid_item(
            wonum=task_wonum,
            itemnum=None,  # Will use template from existing materials
            location='LCVK-CMW-AJ',  # No location for direct request
            directreq=False,  # directreq=0 (False) - direct request like MxLoader example
            quantity=1
        )

        if result:
            print(f"\n🎉 API CALL SUCCESSFUL! 🎉")
            print(f"📄 Response: {json.dumps(result, indent=2)}")

            # Check if there were any errors in the response
            if isinstance(result, list) and len(result) > 0:
                response_data = result[0]
                if '_responsedata' in response_data and 'Error' in response_data['_responsedata']:
                    error = response_data['_responsedata']['Error']
                    print(f"❌ Error in response: {error.get('message')}")
                    return None
                elif '_responsemeta' in response_data and response_data['_responsemeta'].get('status') == '204':
                    print(f"✅ SUCCESS! Material added successfully (Status 204)")
                    print(f"✅ Added with directreq=1 (direct request)")

                    # Verify the addition
                    print(f"\n🔍 VERIFYING ADDITION...")
                    wo_after = adder.get_work_order_full(task_wonum)
                    if wo_after and 'wpmaterial' in wo_after:
                        materials_count = len(wo_after['wpmaterial'])
                        print(f"✅ Work order now has {materials_count} planned materials")

                        # Show all materials
                        print(f"\n📋 ALL MATERIALS:")
                        for i, material in enumerate(wo_after['wpmaterial'], 1):
                            location_info = f" - Location: {material.get('location', 'N/A')}" if material.get('location') else ""
                            directreq_info = f" - DirectReq: {material.get('directreq', 'N/A')}"
                            # Check multiple possible field names for requestedby
                            requestedby_value = material.get('requestedby') or material.get('requestby') or material.get('REQUESTEDBY') or material.get('REQUESTBY')
                            requestedby_info = f" - RequestedBy: {requestedby_value}" if requestedby_value else ""
                            print(f"   {i}. {material.get('itemnum')} - Qty: {material.get('itemqty')}{location_info}{directreq_info}{requestedby_info}")

                        # Show detailed info for the last material (newly added)
                        if wo_after['wpmaterial']:
                            last_material = wo_after['wpmaterial'][-1]
                            print(f"\n🔍 DETAILED INFO FOR LAST MATERIAL (NEWLY ADDED):")
                            print(f"   All fields: {list(last_material.keys())}")
                            # Look for any field containing 'request'
                            request_fields = [k for k in last_material.keys() if 'request' in k.lower()]
                            if request_fields:
                                print(f"   Request-related fields: {request_fields}")
                                for field in request_fields:
                                    print(f"   {field}: {last_material.get(field)}")
                            else:
                                print(f"   No request-related fields found")

                    return result

        else:
            print(f"❌ API call failed")

    except Exception as e:
        print(f"❌ Exception occurred: {e}")

    return None

if __name__ == "__main__":
    results = main()

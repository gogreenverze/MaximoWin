#!/usr/bin/env python3
"""
Debug script to test planned materials retrieval approaches.

This script tests different methods to retrieve planned materials for tasks:
1. Direct task wonum query (current approach - not working)
2. Using wpmaterial_collectionref from task data
3. Using showplanmaterial relationship query
4. Parent work order + task filter approach

Author: Augment Agent
Date: 2025-06-03
"""

import requests
import json
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.auth.token_manager import MaximoTokenManager

def test_planned_materials_approaches():
    """Test different approaches to retrieve planned materials."""
    
    # Initialize token manager
    DEFAULT_MAXIMO_URL = "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"
    token_manager = MaximoTokenManager(DEFAULT_MAXIMO_URL)
    
    if not token_manager.is_logged_in():
        print("❌ Not logged in. Please log in first.")
        return
    
    print("🔍 Testing planned materials retrieval approaches...")
    print(f"🔗 Base URL: {token_manager.base_url}")
    
    # Test data from the logs
    task_wonum = "2021-1984417"
    parent_wonum = "2021-1744762"  # From the logs
    site_id = "LCVKWT"  # From the logs
    
    print(f"\n📋 Test Data:")
    print(f"   Task WONUM: {task_wonum}")
    print(f"   Parent WONUM: {parent_wonum}")
    print(f"   Site ID: {site_id}")
    
    # Approach 1: Current approach (direct task wonum query)
    print(f"\n🧪 APPROACH 1: Direct task wonum query (current - not working)")
    test_direct_task_query(token_manager, task_wonum, site_id)
    
    # Approach 2: Query parent work order for all tasks and their materials
    print(f"\n🧪 APPROACH 2: Parent work order + task filter")
    test_parent_workorder_approach(token_manager, parent_wonum, task_wonum, site_id)
    
    # Approach 3: Use showplanmaterial relationship
    print(f"\n🧪 APPROACH 3: showplanmaterial relationship query")
    test_showplanmaterial_approach(token_manager, parent_wonum, task_wonum, site_id)
    
    # Approach 4: Get task details first, then use wpmaterial_collectionref
    print(f"\n🧪 APPROACH 4: Task details + wpmaterial_collectionref")
    test_task_collectionref_approach(token_manager, task_wonum, site_id)

def test_direct_task_query(token_manager, task_wonum, site_id):
    """Test the current direct task query approach."""
    try:
        api_url = f"{token_manager.base_url}/oslc/os/mxapiwodetail"
        
        params = {
            "oslc.select": "wonum,siteid,wpmaterial.itemnum,wpmaterial.description,wpmaterial.itemqty,wpmaterial.unitcost,wpmaterial.linecost,wpmaterial.storeloc,wpmaterial.itemsetid,wpmaterial.vendor,wpmaterial.directreq",
            "oslc.where": f'wonum="{task_wonum}" and siteid="{site_id}"',
            "oslc.pageSize": "1",
            "lean": "1"
        }
        
        print(f"   🔗 URL: {api_url}")
        print(f"   🔍 Filter: {params['oslc.where']}")
        print(f"   📋 Select: {params['oslc.select']}")
        
        response = token_manager.session.get(api_url, params=params, timeout=(5.0, 30))
        
        print(f"   📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            member_count = len(data.get('member', []))
            print(f"   📦 Members found: {member_count}")
            
            if member_count > 0:
                wo = data['member'][0]
                wpmaterials = wo.get('wpmaterial', [])
                print(f"   🧱 WP Materials: {len(wpmaterials)}")
                if wpmaterials:
                    for i, mat in enumerate(wpmaterials[:3]):  # Show first 3
                        print(f"      {i+1}. {mat.get('itemnum', 'N/A')} - {mat.get('description', 'N/A')}")
            else:
                print(f"   ❌ No work order found for task {task_wonum}")
        else:
            print(f"   ❌ API Error: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")

def test_parent_workorder_approach(token_manager, parent_wonum, task_wonum, site_id):
    """Test querying parent work order with task filter."""
    try:
        api_url = f"{token_manager.base_url}/oslc/os/mxapiwodetail"
        
        # Query for both parent and tasks with their materials
        params = {
            "oslc.select": "wonum,siteid,parent,istask,wpmaterial.itemnum,wpmaterial.description,wpmaterial.itemqty,wpmaterial.unitcost,wpmaterial.linecost,wpmaterial.storeloc,wpmaterial.itemsetid,wpmaterial.vendor,wpmaterial.directreq",
            "oslc.where": f'(wonum="{parent_wonum}" or (parent="{parent_wonum}" and istask=1)) and siteid="{site_id}"',
            "oslc.pageSize": "50",
            "lean": "1"
        }
        
        print(f"   🔗 URL: {api_url}")
        print(f"   🔍 Filter: {params['oslc.where']}")
        print(f"   📋 Select: {params['oslc.select']}")
        
        response = token_manager.session.get(api_url, params=params, timeout=(5.0, 30))
        
        print(f"   📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            members = data.get('member', [])
            print(f"   📦 Total members found: {len(members)}")
            
            # Find our specific task
            target_task = None
            for member in members:
                if member.get('wonum') == task_wonum:
                    target_task = member
                    break
            
            if target_task:
                print(f"   ✅ Found target task: {task_wonum}")
                wpmaterials = target_task.get('wpmaterial', [])
                print(f"   🧱 WP Materials for task: {len(wpmaterials)}")
                if wpmaterials:
                    for i, mat in enumerate(wpmaterials[:3]):  # Show first 3
                        print(f"      {i+1}. {mat.get('itemnum', 'N/A')} - {mat.get('description', 'N/A')}")
                else:
                    print(f"   ℹ️ No materials found for task {task_wonum}")
            else:
                print(f"   ❌ Target task {task_wonum} not found in results")
                
        else:
            print(f"   ❌ API Error: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")

def test_showplanmaterial_approach(token_manager, parent_wonum, task_wonum, site_id):
    """Test using showplanmaterial relationship."""
    try:
        api_url = f"{token_manager.base_url}/oslc/os/mxapiwodetail"
        
        # Use showplanmaterial relationship as mentioned in memories
        params = {
            "oslc.select": "wonum,siteid,showplanmaterial.itemnum,showplanmaterial.description,showplanmaterial.itemqty,showplanmaterial.unitcost,showplanmaterial.linecost,showplanmaterial.storeloc,showplanmaterial.itemsetid,showplanmaterial.vendor,showplanmaterial.directreq",
            "oslc.where": f'wonum in (select wonum from workorder where (wonum="{parent_wonum}" or (parent="{parent_wonum}" and istask=1)) and siteid="{site_id}")',
            "oslc.pageSize": "50",
            "lean": "1"
        }
        
        print(f"   🔗 URL: {api_url}")
        print(f"   🔍 Filter: {params['oslc.where']}")
        print(f"   📋 Select: {params['oslc.select']}")
        
        response = token_manager.session.get(api_url, params=params, timeout=(5.0, 30))
        
        print(f"   📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            members = data.get('member', [])
            print(f"   📦 Total members found: {len(members)}")
            
            # Look for materials
            total_materials = 0
            for member in members:
                wonum = member.get('wonum', 'N/A')
                materials = member.get('showplanmaterial', [])
                if materials:
                    total_materials += len(materials)
                    print(f"   🧱 Materials for {wonum}: {len(materials)}")
                    if wonum == task_wonum:
                        print(f"   ✅ Found materials for target task {task_wonum}:")
                        for i, mat in enumerate(materials[:3]):  # Show first 3
                            print(f"      {i+1}. {mat.get('itemnum', 'N/A')} - {mat.get('description', 'N/A')}")
            
            print(f"   📊 Total materials found: {total_materials}")
                
        else:
            print(f"   ❌ API Error: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")

def test_task_collectionref_approach(token_manager, task_wonum, site_id):
    """Test getting task details first, then using wpmaterial_collectionref."""
    try:
        # First, get the task details to find the wpmaterial_collectionref
        api_url = f"{token_manager.base_url}/oslc/os/mxapiwodetail"
        
        params = {
            "oslc.select": "wonum,siteid,wpmaterial_collectionref",
            "oslc.where": f'wonum="{task_wonum}"',
            "oslc.pageSize": "1",
            "lean": "1"
        }
        
        print(f"   🔗 Step 1 - Get task details:")
        print(f"   🔗 URL: {api_url}")
        print(f"   🔍 Filter: {params['oslc.where']}")
        
        response = token_manager.session.get(api_url, params=params, timeout=(5.0, 30))
        
        print(f"   📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            members = data.get('member', [])
            
            if members:
                task = members[0]
                collection_ref = task.get('wpmaterial_collectionref')
                print(f"   📋 wpmaterial_collectionref: {collection_ref}")
                
                if collection_ref:
                    print(f"\n   🔗 Step 2 - Follow collection reference:")
                    # Follow the collection reference
                    mat_response = token_manager.session.get(collection_ref, timeout=(5.0, 30))
                    print(f"   📊 Materials Status: {mat_response.status_code}")
                    
                    if mat_response.status_code == 200:
                        mat_data = mat_response.json()
                        materials = mat_data.get('member', [])
                        print(f"   🧱 Materials found: {len(materials)}")
                        
                        if materials:
                            for i, mat in enumerate(materials[:3]):  # Show first 3
                                print(f"      {i+1}. {mat.get('itemnum', 'N/A')} - {mat.get('description', 'N/A')}")
                        else:
                            print(f"   ℹ️ No materials in collection reference")
                    else:
                        print(f"   ❌ Materials API Error: {mat_response.status_code}")
                else:
                    print(f"   ℹ️ No wpmaterial_collectionref found for task")
            else:
                print(f"   ❌ Task {task_wonum} not found")
        else:
            print(f"   ❌ API Error: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")

if __name__ == "__main__":
    test_planned_materials_approaches()

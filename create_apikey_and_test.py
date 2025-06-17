#!/usr/bin/env python3
"""
Create API key and test status change with proper authentication.
"""
import sys
import os
import subprocess
import tempfile
import json

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.auth.token_manager import MaximoTokenManager

# Configuration
BASE_URL = "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"
WORK_ORDER_NUM = "15643629"
WORKORDER_ID = "36148539"
NEW_STATUS = "INPRG"

def create_api_key(token_manager):
    """Create an API key using the current session."""
    print("🔑 Creating API key...")

    # Create API key using the session
    apikey_url = f"{token_manager.base_url}/oslc/apitoken/create"

    try:
        response = token_manager.session.post(
            apikey_url,
            json={"expiration": -1},  # Never expires
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30
        )

        print(f"API Key creation response: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response text: {response.text}")

        if response.status_code == 200:
            try:
                api_data = response.json()
                api_key = api_data.get('apikey')
                if api_key:
                    print(f"✅ API Key created successfully: {api_key[:10]}...{api_key[-10:]}")
                    return api_key
                else:
                    print(f"❌ No API key in response: {api_data}")
                    return None
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON response: {e}")
                # Try to extract API key from text response
                if "apikey" in response.text.lower():
                    print("🔍 Trying to extract API key from text response...")
                    # Look for patterns like apikey=value or "apikey":"value"
                    import re
                    patterns = [
                        r'"apikey"\s*:\s*"([^"]+)"',
                        r'apikey\s*=\s*([^\s&]+)',
                        r'apikey:\s*([^\s\n]+)'
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, response.text, re.IGNORECASE)
                        if match:
                            api_key = match.group(1)
                            print(f"✅ Extracted API Key: {api_key[:10]}...{api_key[-10:]}")
                            return api_key
                print("❌ Could not extract API key from response")
                return None
        else:
            print(f"❌ Failed to create API key: {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Error creating API key: {e}")
        return None

def test_status_change_with_apikey(api_key):
    """Test status change using API key authentication."""
    if not api_key:
        print("❌ No API key available")
        return

    print(f"\n🔧 Testing Maximo Work Order Status Change with API Key")
    print("=" * 60)
    print(f"Work Order: {WORK_ORDER_NUM}")
    print(f"Workorder ID: {WORKORDER_ID}")
    print(f"New Status: {NEW_STATUS}")
    print(f"API Key: {api_key[:10]}...{api_key[-10:]}")
    print("")

    # Method 1: Using /api route with apikey header (recommended for app server auth)
    print("📋 Method 1: Using /api route with apikey header")
    url1 = f"{BASE_URL}/api/os/mxapiwodetail?action=wsmethod:changeStatus"
    data1 = f'[{{"wonum": "{WORK_ORDER_NUM}", "status": "{NEW_STATUS}"}}]'

    cmd1 = [
        'curl', '-X', 'POST',
        url1,
        '-H', 'Accept: application/json',
        '-H', 'Content-Type: application/json',
        '-H', f'apikey: {api_key}',
        '-H', 'X-method-override: BULK',
        '-d', data1,
        '-v'
    ]

    print(f"URL: {url1}")
    print(f"Data: {data1}")
    print("Running curl command...")

    try:
        result1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=30)
        print(f"Exit code: {result1.returncode}")
        print(f"STDOUT:\n{result1.stdout}")
        if result1.stderr:
            print(f"STDERR:\n{result1.stderr}")
    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
    except Exception as e:
        print(f"❌ Error running curl: {e}")

    print("\n" + "-" * 60 + "\n")

    # Method 2: Using /api route with workorderid and apikey header
    print("📋 Method 2: Using /api route with workorderid and apikey header")
    url2 = f"{BASE_URL}/api/os/mxapiwodetail/{WORKORDER_ID}"
    data2 = f'{{"status": "{NEW_STATUS}"}}'

    cmd2 = [
        'curl', '-X', 'POST',
        url2,
        '-H', 'Accept: application/json',
        '-H', 'Content-Type: application/json',
        '-H', f'apikey: {api_key}',
        '-d', data2,
        '-v'
    ]

    print(f"URL: {url2}")
    print(f"Data: {data2}")
    print("Running curl command...")

    try:
        result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)
        print(f"Exit code: {result2.returncode}")
        print(f"STDOUT:\n{result2.stdout}")
        if result2.stderr:
            print(f"STDERR:\n{result2.stderr}")
    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
    except Exception as e:
        print(f"❌ Error running curl: {e}")

    print("\n" + "-" * 60 + "\n")

    # Method 3: Using /oslc route with apikey query parameter
    print("📋 Method 3: Using /oslc route with apikey query parameter")
    url3 = f"{BASE_URL}/oslc/os/mxapiwodetail/{WORKORDER_ID}?apikey={api_key}"
    data3 = f'{{"status": "{NEW_STATUS}"}}'

    cmd3 = [
        'curl', '-X', 'POST',
        url3,
        '-H', 'Accept: application/json',
        '-H', 'Content-Type: application/json',
        '-d', data3,
        '-v'
    ]

    print(f"URL: {url3}")
    print(f"Data: {data3}")
    print("Running curl command...")

    try:
        result3 = subprocess.run(cmd3, capture_output=True, text=True, timeout=30)
        print(f"Exit code: {result3.returncode}")
        print(f"STDOUT:\n{result3.stdout}")
        if result3.stderr:
            print(f"STDERR:\n{result3.stderr}")
    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
    except Exception as e:
        print(f"❌ Error running curl: {e}")

def main():
    """Main function."""
    print("🚀 Starting Maximo API Key Test")
    print("=" * 50)

    # Initialize token manager
    token_manager = MaximoTokenManager(BASE_URL)

    # Check if logged in
    if not token_manager.is_logged_in():
        print("❌ Not logged in to Maximo. Please login first through the web app.")
        return

    print(f"✅ Logged in to Maximo as: {getattr(token_manager, 'username', 'Unknown')}")

    # Create API key
    api_key = create_api_key(token_manager)

    if not api_key:
        print("❌ Failed to create API key")
        return

    # Test status change with API key
    test_status_change_with_apikey(api_key)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Test Maximo work order status change using API key authentication.
This script will be used once the API key is created through the Maximo web interface.
"""
import subprocess
import sys

# Configuration
BASE_URL = "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"
WORK_ORDER_NUM = "15643629"
WORKORDER_ID = "36148539"
NEW_STATUS = "INPRG"

# API Key - From .env file
API_KEY = "dj9sia0tu2s0sktv3oq815amtv06ior0ahlsn70o"

def test_api_key_authentication():
    """Test API key authentication with different methods."""

    # API key is loaded from .env file

    print(f"🔧 Testing Maximo Work Order Status Change with API Key")
    print("=" * 60)
    print(f"Work Order: {WORK_ORDER_NUM}")
    print(f"Workorder ID: {WORKORDER_ID}")
    print(f"New Status: {NEW_STATUS}")
    print(f"API Key: {API_KEY[:10]}...{API_KEY[-10:] if len(API_KEY) > 20 else API_KEY}")
    print("")

    # Method 1: Using /api route with apikey header and action=wsmethod:changeStatus
    print("📋 Method 1: Using /api route with apikey header and changeStatus action")
    url1 = f"{BASE_URL}/api/os/mxapiwodetail?action=wsmethod:changeStatus"
    data1 = f'[{{"wonum": "{WORK_ORDER_NUM}", "status": "{NEW_STATUS}"}}]'

    cmd1 = [
        'curl', '-X', 'POST',
        url1,
        '-H', 'Accept: application/json',
        '-H', 'Content-Type: application/json',
        '-H', f'apikey: {API_KEY}',
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

        # Check for success indicators
        if result1.returncode == 0 and "200" in result1.stderr:
            print("✅ Method 1 appears to be successful!")
        elif "302" in result1.stderr:
            print("❌ Method 1 failed - still getting redirects (check API key)")
        else:
            print("⚠️ Method 1 result unclear - check output above")

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
        '-H', f'apikey: {API_KEY}',
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

        # Check for success indicators
        if result2.returncode == 0 and "200" in result2.stderr:
            print("✅ Method 2 appears to be successful!")
        elif "302" in result2.stderr:
            print("❌ Method 2 failed - still getting redirects (check API key)")
        else:
            print("⚠️ Method 2 result unclear - check output above")

    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
    except Exception as e:
        print(f"❌ Error running curl: {e}")

    print("\n" + "-" * 60 + "\n")

    # Method 3: Using /api route with apikey as query parameter
    print("📋 Method 3: Using /api route with apikey as query parameter")
    url3 = f"{BASE_URL}/api/os/mxapiwodetail/{WORKORDER_ID}?apikey={API_KEY}"
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

        # Check for success indicators
        if result3.returncode == 0 and "200" in result3.stderr:
            print("✅ Method 3 appears to be successful!")
        elif "302" in result3.stderr:
            print("❌ Method 3 failed - still getting redirects (check API key)")
        else:
            print("⚠️ Method 3 result unclear - check output above")

    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
    except Exception as e:
        print(f"❌ Error running curl: {e}")

    print("\n" + "=" * 60)
    print("🔧 Test completed!")
    print("\n📋 Next Steps:")
    print("   1. If any method shows ✅ success, use that method in the Flask app")
    print("   2. If all methods show ❌ redirects, verify the API key is correct")
    print("   3. If methods show ⚠️ unclear results, check the detailed output")

def main():
    """Main function."""
    print("🚀 Starting Maximo API Key Authentication Test")
    print("=" * 50)

    test_api_key_authentication()

if __name__ == "__main__":
    main()

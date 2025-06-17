#!/usr/bin/env python3
"""
Extract cookies from the current Maximo session and test status change with curl.
"""
import sys
import os
import subprocess
import tempfile

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.auth.token_manager import MaximoTokenManager

# Configuration
BASE_URL = "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"
WORK_ORDER_NUM = "15643629"
WORKORDER_ID = "36148539"
NEW_STATUS = "INPRG"

def extract_cookies_to_file(token_manager):
    """Extract cookies from token manager session and save to a file for curl."""
    if not hasattr(token_manager, 'session') or not token_manager.session.cookies:
        print("❌ No session or cookies found in token manager")
        return None
    
    # Create a temporary file for cookies
    cookie_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    
    print(f"🍪 Extracting cookies to: {cookie_file.name}")
    
    # Write cookies in Netscape format for curl
    cookie_file.write("# Netscape HTTP Cookie File\n")
    cookie_file.write("# This is a generated file! Do not edit.\n\n")
    
    for cookie in token_manager.session.cookies:
        # Format: domain, domain_specified, path, secure, expires, name, value
        domain = cookie.domain or BASE_URL.split('//')[1].split('/')[0]
        domain_specified = "TRUE" if cookie.domain_specified else "FALSE"
        path = cookie.path or "/"
        secure = "TRUE" if cookie.secure else "FALSE"
        expires = str(int(cookie.expires)) if cookie.expires else "0"
        name = cookie.name
        value = cookie.value
        
        cookie_line = f"{domain}\t{domain_specified}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n"
        cookie_file.write(cookie_line)
        
        print(f"  📝 {name}: {value[:20]}{'...' if len(value) > 20 else ''}")
    
    cookie_file.close()
    return cookie_file.name

def test_curl_methods(cookie_file):
    """Test different curl methods for status change."""
    if not cookie_file:
        print("❌ No cookie file available")
        return
    
    print(f"\n🔧 Testing Maximo Work Order Status Change with curl")
    print("=" * 60)
    print(f"Work Order: {WORK_ORDER_NUM}")
    print(f"Workorder ID: {WORKORDER_ID}")
    print(f"New Status: {NEW_STATUS}")
    print(f"Base URL: {BASE_URL}")
    print(f"Cookie File: {cookie_file}")
    print("")
    
    # Method 1: Using action=wsmethod:changeStatus (IBM recommended)
    print("📋 Method 1: Using action=wsmethod:changeStatus")
    url1 = f"{BASE_URL}/oslc/os/mxapiwodetail?action=wsmethod:changeStatus"
    data1 = f'[{{"wonum": "{WORK_ORDER_NUM}", "status": "{NEW_STATUS}"}}]'
    
    cmd1 = [
        'curl', '-X', 'POST',
        url1,
        '-H', 'Accept: application/json',
        '-H', 'Content-Type: application/json',
        '-H', 'X-method-override: BULK',
        '-d', data1,
        '-b', cookie_file,
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
    
    # Method 2: Using workorderid directly
    print("📋 Method 2: Using workorderid directly")
    url2 = f"{BASE_URL}/oslc/os/mxapiwodetail/{WORKORDER_ID}"
    data2 = f'{{"status": "{NEW_STATUS}"}}'
    
    cmd2 = [
        'curl', '-X', 'POST',
        url2,
        '-H', 'Accept: application/json',
        '-H', 'Content-Type: application/json',
        '-d', data2,
        '-b', cookie_file,
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
    
    # Method 3: Using POST with x-method-override PATCH
    print("📋 Method 3: Using POST with x-method-override PATCH")
    url3 = f"{BASE_URL}/oslc/os/mxapiwodetail/{WORKORDER_ID}"
    data3 = f'{{"status": "{NEW_STATUS}"}}'
    
    cmd3 = [
        'curl', '-X', 'POST',
        url3,
        '-H', 'Accept: application/json',
        '-H', 'Content-Type: application/json',
        '-H', 'X-method-override: PATCH',
        '-d', data3,
        '-b', cookie_file,
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
    print("🚀 Starting Maximo Status Change Test")
    print("=" * 50)
    
    # Initialize token manager
    token_manager = MaximoTokenManager(BASE_URL)
    
    # Check if logged in
    if not token_manager.is_logged_in():
        print("❌ Not logged in to Maximo. Please login first through the web app.")
        return
    
    print(f"✅ Logged in to Maximo as: {getattr(token_manager, 'username', 'Unknown')}")
    
    # Extract cookies
    cookie_file = extract_cookies_to_file(token_manager)
    
    if not cookie_file:
        print("❌ Failed to extract cookies")
        return
    
    try:
        # Test curl methods
        test_curl_methods(cookie_file)
    finally:
        # Clean up cookie file
        try:
            os.unlink(cookie_file)
            print(f"\n🧹 Cleaned up cookie file: {cookie_file}")
        except Exception as e:
            print(f"⚠️ Failed to clean up cookie file: {e}")

if __name__ == "__main__":
    main()

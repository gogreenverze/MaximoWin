"""
API routes for the Maximo OAuth application.
"""
import time
import json
import hashlib
import logging
from flask import Blueprint, jsonify, session, request


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('api_routes')

# Create a Blueprint for API routes
api_bp = Blueprint('api', __name__)

# Token manager will be set when the blueprint is registered with the app
token_manager = None

def init_api(app, tm):
    """Initialize the API blueprint with the token manager."""
    global token_manager
    token_manager = tm
    app.register_blueprint(api_bp, url_prefix='/api')

@api_bp.route('/check-apikey')
def check_apikey():
    """Temporary endpoint to check mxapiapikey methods."""
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})

    # Get the token manager
    if not token_manager.is_logged_in():
        return jsonify({'error': 'No valid token manager'})

    results = {
        'username': session['username'],
        'base_url': token_manager.base_url,
        'logged_in': token_manager.is_logged_in(),
        'tests': []
    }

    # Test 1: Try to access whoami with regular OAuth
    try:
        whoami_url = f"{token_manager.base_url}/oslc/whoami"
        response = token_manager.session.get(
            whoami_url,
            headers={"Accept": "application/json"},
            timeout=(3.05, 10)
        )

        results['tests'].append({
            'name': 'OAuth whoami',
            'url': whoami_url,
            'status_code': response.status_code,
            'success': response.status_code == 200,
            'response': response.json() if response.status_code == 200 else str(response.text)[:200]
        })
    except Exception as e:
        results['tests'].append({
            'name': 'OAuth whoami',
            'error': str(e)
        })

    # Test 2: Try with mmxapiapikey header (test value)
    try:
        whoami_url = f"{token_manager.base_url}/oslc/whoami"
        response = token_manager.session.get(
            whoami_url,
            headers={
                "Accept": "application/json",
                "mmxapiapikey": "test_value"
            },
            timeout=(3.05, 10)
        )

        results['tests'].append({
            'name': 'mmxapiapikey whoami',
            'url': whoami_url,
            'status_code': response.status_code,
            'success': response.status_code == 200,
            'response': response.json() if response.status_code == 200 else str(response.text)[:200]
        })
    except Exception as e:
        results['tests'].append({
            'name': 'mmxapiapikey whoami',
            'error': str(e)
        })

    # Test 3: Try REST API with mmxapiapikey
    try:
        rest_url = f"{token_manager.base_url}/api/os/mxuser"
        response = token_manager.session.get(
            rest_url,
            headers={
                "Accept": "application/json",
                "mmxapiapikey": "test_value"
            },
            timeout=(3.05, 10)
        )

        results['tests'].append({
            'name': 'mmxapiapikey REST API',
            'url': rest_url,
            'status_code': response.status_code,
            'success': response.status_code == 200,
            'response': response.json() if response.status_code == 200 else str(response.text)[:200]
        })
    except Exception as e:
        results['tests'].append({
            'name': 'mmxapiapikey REST API',
            'error': str(e)
        })

    # Test 4: Try to get API key info
    try:
        apikey_url = f"{token_manager.base_url}/oslc/apikey"
        response = token_manager.session.get(
            apikey_url,
            headers={"Accept": "application/json"},
            timeout=(3.05, 10)
        )

        results['tests'].append({
            'name': 'API Key Info',
            'url': apikey_url,
            'status_code': response.status_code,
            'success': response.status_code == 200,
            'response': response.json() if response.status_code == 200 else str(response.text)[:200]
        })
    except Exception as e:
        results['tests'].append({
            'name': 'API Key Info',
            'error': str(e)
        })

    return jsonify(results)

@api_bp.route('/fetch-assets')
def fetch_assets():
    """Fetch operating assets for the logged-in user's default site using mxapiapikey header."""
    import requests

    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})

    # Verify that we're still logged in
    if not token_manager.is_logged_in():
        return jsonify({'error': 'Session expired'})

    # Step 1: Get the user profile to find the default site
    user_profile = token_manager.get_user_profile(use_mock=False, use_cache=True)

    if not user_profile:
        return jsonify({'error': 'Could not get user profile'})

    # Get default site from user profile
    default_site = user_profile.get('defaultSite')
    username = user_profile.get('loginUserName') or session['username']

    if not default_site:
        return jsonify({'error': 'No default site found in user profile'})

    # Step 2: Try to fetch assets using OAuth first (as a fallback)
    try:
        # Prepare API endpoint for assets
        assets_url = f"{token_manager.base_url}/api/os/mxapiasset"

        # Prepare query parameters to filter assets
        # Filter for operating assets in the user's default site
        query_params = {
            "lean": "1",  # Get lean response for better performance
            "oslc.select": "assetnum,description,status,siteid",  # Select specific fields
            "oslc.where": f"status=\"OPERATING\" and siteid=\"{default_site}\"",  # Filter criteria
            "oslc.pageSize": "100"  # Limit results
        }

        # First try with OAuth (using the token_manager's session)
        oauth_start_time = time.time()
        oauth_response = token_manager.session.get(
            assets_url,
            params=query_params,
            headers={"Accept": "application/json"},
            timeout=(3.05, 15)
        )
        oauth_time = time.time() - oauth_start_time

        # Now try with mxapiapikey header
        # Generate a consistent API key based on username and current date
        # This is just for testing - in production you would use a real API key
        date_str = time.strftime("%Y-%m-%d")
        api_key_seed = f"{username}:{date_str}:maximo_test_key"
        generated_api_key = hashlib.sha256(api_key_seed.encode()).hexdigest()

        # Prepare headers with generated API key
        api_headers = {
            "Accept": "application/json",
            "mxapiapikey": generated_api_key,  # Correct header name: mxapiapikey
            "x-user-context": username  # Include user context
        }

        # Try with API key
        api_start_time = time.time()
        api_response = requests.get(
            assets_url,
            params=query_params,
            headers=api_headers,
            timeout=(3.05, 15)
        )
        api_time = time.time() - api_start_time

        # Determine which response to use
        if api_response.status_code == 200:
            # API key method worked
            response = api_response
            method_used = "API Key"
            response_time = api_time
        elif oauth_response.status_code == 200:
            # OAuth method worked
            response = oauth_response
            method_used = "OAuth"
            response_time = oauth_time
        else:
            # Neither method worked, return the API key response
            return jsonify({
                'error': f'Error fetching assets with mxapiapikey. Status code: {api_response.status_code}',
                'oauth_status': oauth_response.status_code,
                'api_key_status': api_response.status_code,
                'response': api_response.text[:500]
            })

        # Process the successful response
        try:
            assets_data = response.json()

            # Format the assets for display
            formatted_assets = []

            if 'member' in assets_data:
                assets = assets_data['member']

                for asset in assets:
                    formatted_assets.append({
                        'assetnum': asset.get('assetnum', 'N/A'),
                        'siteid': asset.get('siteid', 'N/A'),
                        'status': asset.get('status', 'N/A'),
                        'description': asset.get('description', 'N/A')
                    })

            return jsonify({
                'success': True,
                'username': username,
                'default_site': default_site,
                'asset_count': len(formatted_assets),
                'method_used': method_used,
                'response_time': response_time,
                'oauth_time': oauth_time,
                'api_key_time': api_time,
                'assets': formatted_assets
            })
        except Exception as e:
            return jsonify({'error': f'Error parsing assets response: {str(e)}'})
    except Exception as e:
        return jsonify({'error': f'Exception during assets request: {str(e)}'})







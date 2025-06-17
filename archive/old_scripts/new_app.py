from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import secrets
import threading
import time
import requests
from backend.auth import MaximoTokenManager
from backend.api import init_api
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app with custom template and static folders
app = Flask(__name__,
            template_folder='frontend/templates',
            static_folder='frontend/static')
app.secret_key = secrets.token_hex(16)

# Default Maximo URL for UAT environment
DEFAULT_MAXIMO_URL = "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"

# Initialize token manager globally for reuse
token_manager = MaximoTokenManager(DEFAULT_MAXIMO_URL)

# Initialize API routes with the token manager
# This needs to be done after the app is created
init_api(app, token_manager)

# Background authentication flag
background_auth_in_progress = False
background_auth_result = None

@app.route('/')
def index():
    """Render the login page."""
    # Check if we already have a valid session
    if 'username' in session and token_manager.is_logged_in():
        return redirect(url_for('welcome'))

    # Clear any existing invalid session
    session.clear()
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    """Handle login form submission."""
    global background_auth_in_progress, background_auth_result

    username = request.form.get('username')
    password = request.form.get('password')
    remember_me = request.form.get('remember_me') == 'on'

    if not username or not password:
        flash('Please enter both username and password', 'error')
        return redirect(url_for('index'))

    # Start background authentication
    background_auth_in_progress = True
    background_auth_result = None

    def auth_worker():
        global background_auth_in_progress, background_auth_result
        try:
            # Attempt to login
            success = token_manager.login(username, password)
            background_auth_result = {'success': success, 'error': None}
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            background_auth_result = {'success': False, 'error': str(e)}
        finally:
            background_auth_in_progress = False

    # Start authentication in background
    auth_thread = threading.Thread(target=auth_worker)
    auth_thread.daemon = True
    auth_thread.start()

    # Store username in session
    session['username'] = username
    session['login_started'] = time.time()

    # Redirect to loading page
    return redirect(url_for('auth_status'))

@app.route('/auth-status')
def auth_status():
    """Check authentication status and redirect accordingly."""
    global background_auth_in_progress, background_auth_result

    if 'username' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('index'))

    # If authentication is complete
    if not background_auth_in_progress and background_auth_result:
        if background_auth_result['success']:
            # Clear the result to avoid memory leaks
            result = background_auth_result
            background_auth_result = None

            # Try to get user profile to store default site and insert site
            try:
                # Use the optimized profile retrieval with caching
                user_profile = token_manager.get_user_profile(use_mock=False, use_cache=True)
                if user_profile:
                    # Note: The profile data is already cleaned (no spi: prefixes)
                    session['default_site'] = user_profile.get('defaultSite', '')
                    session['insert_site'] = user_profile.get('insertSite', '')
                    session['first_name'] = user_profile.get('firstName', '')
                    session['last_name'] = user_profile.get('lastName', '')
            except Exception as e:
                logger.warning(f"Error getting user profile during login: {e}")

            return redirect(url_for('welcome'))
        else:
            # Authentication failed
            error = background_auth_result.get('error', 'Unknown error')
            background_auth_result = None
            session.clear()
            flash(f'Login failed: {error}', 'error')
            return redirect(url_for('index'))

    # If still in progress, show loading page
    return render_template('loading.html', username=session.get('username'))

@app.route('/api/auth-status')
def api_auth_status():
    """API endpoint to check authentication status."""
    global background_auth_in_progress, background_auth_result

    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'No login in progress'})

    if background_auth_in_progress:
        # Calculate how long authentication has been running
        start_time = session.get('login_started', time.time())
        elapsed = time.time() - start_time
        return jsonify({
            'status': 'in_progress',
            'elapsed': elapsed,
            'username': session.get('username')
        })

    if background_auth_result:
        if background_auth_result['success']:
            return jsonify({'status': 'success'})
        else:
            error = background_auth_result.get('error', 'Unknown error')
            return jsonify({'status': 'error', 'message': error})

    return jsonify({'status': 'unknown'})

@app.route('/welcome')
def welcome():
    """Render the welcome page."""
    if 'username' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('index'))

    # Verify that we're still logged in
    if not token_manager.is_logged_in():
        flash('Your session has expired. Please login again.', 'warning')
        session.clear()
        return redirect(url_for('index'))

    # Get login time
    login_time = session.get('login_started', time.time())
    login_duration = time.time() - login_time

    import time as time_module

    try:
        return render_template(
            'welcome.html',
            username=session['username'],
            login_duration=login_duration,
            token_expires_at=token_manager.expires_at,
            time=time_module
        )
    except Exception as e:
        logger.error(f"Error rendering welcome page: {e}")
        flash('An error occurred while loading the welcome page. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/profile')
def profile():
    """Render the user profile page."""
    if 'username' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('index'))

    # Verify that we're still logged in
    if not token_manager.is_logged_in():
        flash('Your session has expired. Please login again.', 'warning')
        session.clear()
        return redirect(url_for('index'))

    try:
        # Try to refresh the session first
        try:
            # Force a token refresh to ensure we have a valid session
            token_manager._refresh_token()
        except Exception as e:
            logger.warning(f"Error refreshing token: {e}")

        # Get user profile data with lightning-fast caching
        start_time = time.time()
        user_profile = token_manager.get_user_profile(use_mock=False, use_cache=True)
        profile_fetch_time = time.time() - start_time
        logger.info(f"Profile data retrieved in {profile_fetch_time:.3f} seconds")

        if not user_profile:
            logger.warning("Failed to fetch user profile data, using session data")
            # Create a minimal profile with data from the session
            user_profile = {
                "firstName": session.get('first_name', ''),
                "lastName": session.get('last_name', ''),
                "displayName": session['username'],
                "userName": session['username'],
                "loginUserName": session['username'],
                "defaultSite": session.get('default_site', ''),
                "insertSite": session.get('insert_site', '')
            }

        # Get available sites with caching enabled for better performance
        available_sites = token_manager.get_available_sites(use_mock=False, use_cache=True)

        # Ensure we have at least the current default and insert sites in the list
        if available_sites and user_profile:
            # Get current default and insert sites (now using cleaned keys without prefixes)
            default_site = user_profile.get('defaultSite', '')
            insert_site = user_profile.get('insertSite', '')

            # Check if they're in the available sites list
            default_site_exists = any(site.get('siteid') == default_site for site in available_sites)
            insert_site_exists = any(site.get('siteid') == insert_site for site in available_sites)

            # Add them if they're not in the list
            if default_site and not default_site_exists:
                available_sites.append({
                    'siteid': default_site,
                    'description': user_profile.get('defaultSiteDescription', default_site)
                })

            if insert_site and not insert_site_exists:
                available_sites.append({
                    'siteid': insert_site,
                    'description': insert_site
                })

            # Sort the sites by siteid
            available_sites.sort(key=lambda x: x.get('siteid', ''))

        # Create a default user profile with empty values if any required fields are missing
        # Using cleaned field names (no spi: prefixes)
        default_profile = {
            "firstName": "",
            "lastName": "",
            "displayName": "",
            "personid": "",
            "userName": session['username'],
            "loginID": "",
            "loginUserName": session['username'],
            "email": "",
            "country": "",
            "stateprovince": "",
            "phone": "",
            "primaryPhone": "",
            "timezone": "",
            "systimezone": "UTC",
            "baseLang": "EN",
            "baseCurrency": "USD",
            "baseCalendar": "gregorian",
            "dateformat": "M/d/yy",
            "canUseInactiveSites": "False",
            "defaultStoreroom": "",
            "defaultRepairSite": "None",
            "defaultRepairFacility": "None",
            "defaultOrg": "",
            "defaultSiteDescription": "",
            "defaultStoreroomSite": "None",
            "insertSite": "",
            "defaultSite": ""
        }

        # Merge the default profile with the actual profile
        for key, value in default_profile.items():
            if key not in user_profile:
                user_profile[key] = value

        return render_template(
            'profile.html',
            username=session['username'],
            user_profile=user_profile,
            available_sites=available_sites if available_sites else []
        )
    except Exception as e:
        logger.error(f"Error rendering profile page: {e}")
        flash('An error occurred while loading the profile page. Please try again.', 'error')
        return redirect(url_for('welcome'))

@app.route('/update-default-site', methods=['POST'])
def update_default_site():
    """Update the user's default site or insert site."""
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'})

    # Verify that we're still logged in
    if not token_manager.is_logged_in():
        return jsonify({'status': 'error', 'message': 'Session expired'})

    site_id = request.form.get('site_id')
    if not site_id:
        return jsonify({'status': 'error', 'message': 'No site ID provided'})

    # Determine which site type to update (default or insert)
    site_type = request.form.get('site_type', 'default')
    site_type_display = "insert site" if site_type == 'insert' else "default site"

    # Make an API call to update the user's site setting
    try:
        # Construct the API URL for updating the user's profile
        update_url = f"{token_manager.base_url}/oslc/userprofile"

        # Prepare the update data based on site type
        # Note: We still need to use the spi: prefix for the API call
        if site_type == 'insert':
            update_data = {
                "spi:insertSite": site_id
            }
            # Also update the session
            session['insert_site'] = site_id
        else:
            update_data = {
                "spi:defaultSite": site_id
            }
            # Also update the session
            session['default_site'] = site_id

        logger.info(f"Updating {site_type_display} to {site_id}")

        # Make the API call with PATCH first (most efficient)
        try:
            response = token_manager.session.patch(
                update_url,
                json=update_data,
                headers={"Content-Type": "application/json"},
                timeout=(3.05, 10)  # Reduced timeout
            )

            # If successful, return immediately
            if response.status_code in [200, 201, 204]:
                logger.info(f"Successfully updated {site_type_display} to {site_id} with PATCH")

                # Force a refresh of the sites cache
                try:
                    token_manager.get_available_sites(use_mock=False, use_cache=False, force_refresh=True)
                except Exception as cache_error:
                    logger.warning(f"Error refreshing sites cache: {cache_error}")

                return jsonify({
                    'status': 'success',
                    'message': f'{site_type_display.capitalize()} updated to {site_id}',
                    'site_id': site_id,
                    'site_type': site_type
                })
        except Exception as patch_error:
            logger.warning(f"PATCH request failed: {patch_error}")

        # If PATCH failed, try PUT with minimal data
        try:
            # We don't need the full profile, just the essential fields
            # Note: We still need to use the spi: prefix for the API call
            minimal_profile = {
                "spi:userName": session['username']
            }

            # Add the site field we're updating
            if site_type == 'insert':
                minimal_profile["spi:insertSite"] = site_id
            else:
                minimal_profile["spi:defaultSite"] = site_id

            response = token_manager.session.put(
                update_url,
                json=minimal_profile,
                headers={"Content-Type": "application/json"},
                timeout=(3.05, 10)  # Reduced timeout
            )

            if response.status_code in [200, 201, 204]:
                logger.info(f"Successfully updated {site_type_display} to {site_id} with PUT")

                # Force a refresh of the sites cache
                try:
                    token_manager.get_available_sites(use_mock=False, use_cache=False, force_refresh=True)
                except Exception as cache_error:
                    logger.warning(f"Error refreshing sites cache: {cache_error}")

                return jsonify({
                    'status': 'success',
                    'message': f'{site_type_display.capitalize()} updated to {site_id}',
                    'site_id': site_id,
                    'site_type': site_type
                })
            else:
                logger.error(f"Failed to update {site_type_display}. Status code: {response.status_code}")
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to update {site_type_display}. Status code: {response.status_code}'
                })
        except Exception as put_error:
            logger.error(f"PUT request failed: {put_error}")
            raise  # Re-raise to be caught by the outer exception handler

    except Exception as e:
        logger.error(f"Error updating {site_type_display}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error updating {site_type_display}: {str(e)}'
        })

@app.route('/logout')
def logout():
    """Handle logout."""
    username = session.get('username', 'User')

    # Clear session
    session.clear()

    # Logout from token manager
    token_manager.logout()

    flash(f'{username} has been logged out', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5004)

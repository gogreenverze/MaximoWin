"""
Main application file for Maximo OAuth.
This file sets up the Flask application and routes.
"""
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import sys
import secrets
import threading
import time
import datetime
import requests
import json
from backend.auth import MaximoTokenManager
from backend.api import init_api, init_sync_routes
from backend.services import EnhancedProfileService, EnhancedWorkOrderService
from backend.services.site_access_service import SiteAccessService
from backend.services.labor_search_service import LaborSearchService
from backend.services.labor_request_service import LaborRequestService

import logging
import json

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app with custom template and static folders
# Use resource path function to handle PyInstaller packaging
template_folder = get_resource_path('frontend/templates')
static_folder = get_resource_path('frontend/static')

# Fallback to legacy folders if new structure doesn't exist
if not os.path.exists(template_folder):
    template_folder = get_resource_path('templates')
if not os.path.exists(static_folder):
    static_folder = get_resource_path('static')

app = Flask(__name__,
            template_folder=template_folder,
            static_folder=static_folder)
app.secret_key = secrets.token_hex(16)

# Default Maximo URL for UAT environment
DEFAULT_MAXIMO_URL = "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"

# Initialize token manager globally for reuse
token_manager = MaximoTokenManager(DEFAULT_MAXIMO_URL)

# Initialize enhanced profile service
enhanced_profile_service = EnhancedProfileService(token_manager)

# Initialize enhanced work order service
enhanced_workorder_service = EnhancedWorkOrderService(token_manager, enhanced_profile_service)

# Initialize labor services
labor_search_service = LaborSearchService(token_manager)
labor_request_service = LaborRequestService(token_manager, enhanced_profile_service)



# Initialize API routes with the token manager
# This needs to be done after the app is created
init_api(app, token_manager)

# Initialize sync routes
init_sync_routes(app)

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

            # Clear any existing profile caches to ensure fresh data (memory + disk)
            try:
                if 'enhanced_profile_service' in globals():
                    enhanced_profile_service.clear_cache('all')
                if 'enhanced_workorder_service' in globals():
                    enhanced_workorder_service.clear_cache('all')

                # Clear ALL disk cache files to prevent cross-user contamination
                import os
                import glob
                cache_patterns = [
                    'cache/profile_*.pkl',
                    'cache/enhanced_profile_*.pkl',
                    'cache/workorder_*.pkl',
                    'cache/sites_*.pkl'
                ]

                for pattern in cache_patterns:
                    for cache_file in glob.glob(pattern):
                        try:
                            os.remove(cache_file)
                            logger.info(f"✅ LOGIN: Removed stale disk cache file: {cache_file}")
                        except Exception as e:
                            logger.warning(f"Could not remove cache file {cache_file}: {e}")

                logger.info("✅ LOGIN: Cleared all caches (memory + disk) for fresh profile data")
            except Exception as e:
                logger.warning(f"Error clearing caches during login: {e}")

            # Try to get fresh user profile (force refresh to avoid stale data)
            try:
                # Force fresh profile retrieval - no cache for login
                user_profile = token_manager.get_user_profile(use_mock=False, use_cache=False, force_refresh=True)
                if user_profile:
                    # Note: The profile data is already cleaned (no spi: prefixes)
                    session['default_site'] = user_profile.get('defaultSite', '')
                    session['insert_site'] = user_profile.get('insertSite', '')
                    session['first_name'] = user_profile.get('firstName', '')
                    session['last_name'] = user_profile.get('lastName', '')

                    logger.info(f"✅ LOGIN: Fresh profile data loaded for user {session['username']}")
                else:
                    logger.error("Failed to fetch fresh user profile during login")
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

        # No hardcoded fallback values - must fetch from Maximo API
        if not user_profile:
            logger.error("Failed to fetch user profile from Maximo API - no fallback values allowed")
            flash('Unable to load profile data. Please login again for fresh authentication.', 'error')
            session.clear()
            return redirect(url_for('index'))

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

        # No hardcoded fallback values - must fetch from Maximo API
        # If profile fetch fails, redirect to login for fresh authentication
        if not user_profile:
            logger.error("Failed to fetch user profile from Maximo API - no fallback values allowed")
            flash('Unable to load profile data. Please login again for fresh authentication.', 'error')
            session.clear()
            return redirect(url_for('index'))

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

@app.route('/enhanced-profile')
def enhanced_profile():
    """Render the enhanced user profile page with optimized performance."""
    if 'username' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('index'))

    # Verify session using enhanced service (with caching)
    if not enhanced_profile_service.is_session_valid():
        flash('Your session has expired. Please login again.', 'warning')
        session.clear()
        return redirect(url_for('index'))

    try:
        # Record start time for performance comparison
        overall_start_time = time.time()

        # Get session data for fallback
        session_data = {
            'username': session['username'],
            'first_name': session.get('first_name', ''),
            'last_name': session.get('last_name', ''),
            'default_site': session.get('default_site', ''),
            'insert_site': session.get('insert_site', '')
        }

        # Use enhanced service to build complete profile
        user_profile, available_sites = enhanced_profile_service.build_complete_profile(session_data)

        # Get performance statistics
        perf_stats = enhanced_profile_service.get_performance_stats()

        overall_time = time.time() - overall_start_time
        logger.info(f"🚀 ENHANCED PROFILE: Total page load time: {overall_time:.3f}s")
        logger.info(f"📊 ENHANCED STATS: Cache hit rate: {perf_stats['cache_hit_rate']:.1f}%, "
                   f"Avg response: {perf_stats['average_response_time']:.3f}s, "
                   f"Total requests: {perf_stats['total_requests']}")

        return render_template(
            'enhanced_profile.html',
            username=session['username'],
            user_profile=user_profile,
            available_sites=available_sites,
            performance_stats=perf_stats,
            page_load_time=overall_time
        )
    except Exception as e:
        logger.error(f"Error rendering enhanced profile page: {e}")
        flash('An error occurred while loading the enhanced profile page. Please try again.', 'error')
        return redirect(url_for('welcome'))

@app.route('/enhanced-workorders')
def enhanced_workorders():
    """Render the enhanced work orders page with optimized performance."""
    if 'username' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('index'))

    # Verify session using enhanced service (with caching)
    if not enhanced_workorder_service.is_session_valid():
        flash('Your session has expired. Please login again.', 'warning')
        session.clear()
        return redirect(url_for('index'))

    try:
        # Record start time for performance comparison
        overall_start_time = time.time()



        # Get user's site ID for display (no work order fetching for lazy loading)
        try:
            user_site_id = enhanced_workorder_service._get_user_site_id()
        except:
            user_site_id = "Unknown"

        overall_time = time.time() - overall_start_time
        logger.info(f"⚡ ENHANCED WORKORDERS: Lightning-fast page load: {overall_time:.3f}s")
        logger.info(f"🔍 ENHANCED WO: Ready for search with site ID: {user_site_id}")

        # Return empty page ready for search
        return render_template(
            'enhanced_workorders.html',
            username=session['username'],
            user_site_id=user_site_id,
            page_load_time=overall_time
        )
    except Exception as e:
        logger.error(f"Error rendering enhanced work orders page: {e}")
        flash('An error occurred while loading the enhanced work orders page. Please try again.', 'error')
        return redirect(url_for('welcome'))

@app.route('/debug-workorders')
def debug_workorders():
    """Debug route to test different work order filters."""
    if 'username' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('index'))

    # Verify session
    if not enhanced_workorder_service.is_session_valid():
        flash('Your session has expired. Please login again.', 'warning')
        session.clear()
        return redirect(url_for('index'))

    try:
        # Get user's site ID
        user_site_id = enhanced_workorder_service._get_user_site_id()
        if not user_site_id:
            return f"<h1>Debug: No user site ID found</h1>"

        # Test different filters
        base_url = getattr(enhanced_workorder_service.token_manager, 'base_url', '')
        api_url = f"{base_url}/oslc/os/mxapiwodetail"

        debug_results = []

        # Test 1: All work orders for site (no status filter)
        try:
            params1 = {
                "oslc.select": "wonum,status,siteid,istask,historyflag",
                "oslc.where": f"siteid=\"{user_site_id}\"",
                "oslc.pageSize": "10"
            }
            response1 = enhanced_workorder_service.token_manager.session.get(
                api_url, params=params1, timeout=(5.0, 15)
            )
            if response1.status_code == 200:
                data1 = response1.json()
                count1 = len(data1.get('member', []))
                debug_results.append(f"Test 1 - All WOs for site {user_site_id}: {count1} found")
            else:
                debug_results.append(f"Test 1 - Failed: {response1.status_code}")
        except Exception as e:
            debug_results.append(f"Test 1 - Error: {str(e)}")

        # Test 2: Enhanced status filter work orders (matching new implementation)
        try:
            params2 = {
                "oslc.select": "wonum,status,siteid,istask,historyflag,woclass",
                "oslc.where": f"(status=\"APPR\" or status=\"ASSIGN\" or status=\"READY\" or status=\"INPRG\" or status=\"PACK\" or status=\"DEFER\" or status=\"WAPPR\" or status=\"WGOVT\" or status=\"AWARD\" or status=\"MTLCXD\" or status=\"MTLISD\" or status=\"PISSUE\" or status=\"RTI\" or status=\"WMATL\" or status=\"WSERV\" or status=\"WSCH\") and (woclass=\"WORKORDER\" or woclass=\"ACTIVITY\") and siteid=\"{user_site_id}\"",
                "oslc.pageSize": "10"
            }
            response2 = enhanced_workorder_service.token_manager.session.get(
                api_url, params=params2, timeout=(5.0, 15)
            )
            if response2.status_code == 200:
                data2 = response2.json()
                count2 = len(data2.get('member', []))
                debug_results.append(f"Test 2 - Enhanced status filter (multiple statuses + woclass) for site {user_site_id}: {count2} found")
            else:
                debug_results.append(f"Test 2 - Failed: {response2.status_code}")
        except Exception as e:
            debug_results.append(f"Test 2 - Error: {str(e)}")

        # Test 3: Any status, non-task, non-history
        try:
            params3 = {
                "oslc.select": "wonum,status,siteid,istask,historyflag",
                "oslc.where": f"siteid=\"{user_site_id}\" and istask=0 and historyflag=0",
                "oslc.pageSize": "10"
            }
            response3 = enhanced_workorder_service.token_manager.session.get(
                api_url, params=params3, timeout=(5.0, 15)
            )
            if response3.status_code == 200:
                data3 = response3.json()
                count3 = len(data3.get('member', []))
                debug_results.append(f"Test 3 - Non-task, non-history for site {user_site_id}: {count3} found")

                # Show sample statuses
                if count3 > 0:
                    statuses = set()
                    for wo in data3.get('member', [])[:5]:
                        statuses.add(wo.get('status', 'Unknown'))
                    debug_results.append(f"Sample statuses found: {', '.join(statuses)}")
            else:
                debug_results.append(f"Test 3 - Failed: {response3.status_code}")
        except Exception as e:
            debug_results.append(f"Test 3 - Error: {str(e)}")

        # Return debug results
        html = f"""
        <h1>Work Order Debug Results for Site: {user_site_id}</h1>
        <ul>
        """
        for result in debug_results:
            html += f"<li>{result}</li>"
        html += """
        </ul>
        <p><a href="/enhanced-workorders">Back to Enhanced Work Orders</a></p>
        <p><a href="/welcome">Back to Welcome</a></p>
        """

        return html

    except Exception as e:
        return f"<h1>Debug Error: {str(e)}</h1>"

@app.route('/force-fresh-login')
def force_fresh_login():
    """Force a completely fresh login to get valid session."""
    # Clear all session data
    session.clear()

    # Clear token manager cache and force logout
    try:
        import os
        # Remove token cache files
        cache_dir = os.path.join(os.path.dirname(__file__), 'cache')
        if os.path.exists(cache_dir):
            for file in os.listdir(cache_dir):
                if file.endswith('.json'):
                    os.remove(os.path.join(cache_dir, file))

        # Clear token manager session
        if hasattr(token_manager, 'session'):
            token_manager.session.cookies.clear()

        # Clear enhanced service caches
        if 'enhanced_profile_service' in globals():
            enhanced_profile_service.clear_cache()
        if 'enhanced_workorder_service' in globals():
            enhanced_workorder_service.clear_cache()

        # Force token manager to clear tokens
        if hasattr(token_manager, 'clear_tokens'):
            token_manager.clear_tokens()

    except Exception as e:
        print(f"Error clearing caches: {e}")

    flash('All caches and tokens cleared. Please login again for fresh session.', 'info')
    return redirect(url_for('index'))

@app.route('/test-fresh-workorders')
def test_fresh_workorders():
    """Test work orders with completely fresh authentication."""
    if 'username' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('index'))

    try:
        # Force fresh login
        username = session.get('username', '')
        password = session.get('password', '')

        if not username or not password:
            flash('Session expired. Please login again.', 'warning')
            return redirect(url_for('index'))

        # Create a completely fresh session
        import requests
        from requests.auth import HTTPBasicAuth

        fresh_session = requests.Session()
        base_url = "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"

        # Test different site filters to find work orders (updated to match new implementation)
        test_filters = [
            'siteid="LCVKWT"',
            '(status="APPR" or status="ASSIGN" or status="READY" or status="INPRG" or status="PACK" or status="DEFER" or status="WAPPR" or status="WGOVT" or status="AWARD" or status="MTLCXD" or status="MTLISD" or status="PISSUE" or status="RTI" or status="WMATL" or status="WSERV" or status="WSCH") and siteid="LCVKWT"',
            '(woclass="WORKORDER" or woclass="ACTIVITY") and siteid="LCVKWT"',
            'siteid="LCVKWT" and istask=0 and historyflag=0',
            '(status="APPR" or status="ASSIGN" or status="READY" or status="INPRG" or status="PACK" or status="DEFER" or status="WAPPR" or status="WGOVT" or status="AWARD" or status="MTLCXD" or status="MTLISD" or status="PISSUE" or status="RTI" or status="WMATL" or status="WSERV" or status="WSCH") and (woclass="WORKORDER" or woclass="ACTIVITY") and siteid="LCVKWT" and istask=0 and historyflag=0'
        ]

        html = f"""
        <h1>Fresh Work Order Test</h1>
        <h2>Testing different filters for site LCVKWT</h2>
        """

        for i, filter_clause in enumerate(test_filters, 1):
            html += f"<h3>Test {i}: {filter_clause}</h3>"

            params = {
                "oslc.select": "wonum,description,status,siteid,priority",
                "oslc.where": filter_clause,
                "oslc.pageSize": "10"
            }

            try:
                # Use basic auth for fresh request
                response = fresh_session.get(
                    f"{base_url}/oslc/os/mxapiwodetail",
                    params=params,
                    auth=HTTPBasicAuth(username, password),
                    timeout=30
                )

                html += f"<p><strong>Status:</strong> {response.status_code}</p>"

                if response.status_code == 200:
                    try:
                        data = response.json()
                        if isinstance(data, dict) and 'member' in data:
                            workorders = data['member']
                            html += f"<p><strong>Found:</strong> {len(workorders)} work orders</p>"

                            if workorders:
                                html += "<table border='1'><tr><th>WO Number</th><th>Description</th><th>Status</th><th>Site</th></tr>"
                                for wo in workorders[:5]:
                                    html += f"""
                                    <tr>
                                        <td>{wo.get('wonum', 'N/A')}</td>
                                        <td>{wo.get('description', 'N/A')[:50]}</td>
                                        <td>{wo.get('status', 'N/A')}</td>
                                        <td>{wo.get('siteid', 'N/A')}</td>
                                    </tr>
                                    """
                                html += "</table>"
                                break  # Found work orders, stop testing
                        else:
                            html += f"<p><strong>Response:</strong> {response.text[:300]}</p>"
                    except Exception as e:
                        html += f"<p><strong>Parse Error:</strong> {str(e)}</p>"
                else:
                    html += f"<p><strong>Error:</strong> {response.text[:300]}</p>"

            except Exception as e:
                html += f"<p><strong>Request Error:</strong> {str(e)}</p>"

            html += "<hr>"

        html += """
        <p><a href="/enhanced-workorders">Back to Enhanced Work Orders</a></p>
        <p><a href="/welcome">Back to Welcome</a></p>
        """

        return html

    except Exception as e:
        return f"<h1>Fresh Test Error: {str(e)}</h1><p><a href='/welcome'>Back to Welcome</a></p>"

@app.route('/workorder/<wonum>')
def workorder_detail(wonum):
    """Work order detail page with robust session handling and error recovery."""
    # Check if user is logged in via session
    if 'username' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('index'))

    # Verify session is still valid
    if not enhanced_workorder_service.is_session_valid():
        flash('Your session has expired. Please login again.', 'warning')
        session.clear()
        return redirect(url_for('index'))

    try:
        # Record start time for performance
        start_time = time.time()

        # Step 1: Get user profile with session validation
        try:
            user_profile = enhanced_profile_service.get_user_profile()
            if user_profile and isinstance(user_profile, dict):
                user_site_id = user_profile.get('defaultSite', 'LCVKWT')
            else:
                user_site_id = 'LCVKWT'
                logger.warning("Profile service returned None, using fallback site LCVKWT")
        except Exception as e:
            user_site_id = 'LCVKWT'
            logger.warning(f"Profile service error: {e}, using fallback site LCVKWT")

        logger.info(f"🔍 WO DETAIL: Using site ID: {user_site_id} for work order: {wonum}")

        # Step 2: Get specific work order using enhanced lookup method (searches all sites)
        logger.info(f"🔍 WO DETAIL: Looking up work order {wonum} across all accessible sites")
        workorder = enhanced_workorder_service.get_workorder_by_wonum(wonum)

        if not workorder:
            logger.warning(f"Work order {wonum} not found in any accessible site")
            flash(f'Work order {wonum} not found or not accessible', 'error')
            return redirect(url_for('enhanced_workorders'))

        # Step 3: Get work order tasks with robust session handling
        tasks = []
        try:
            # Verify session is still valid before making tasks API call
            if not enhanced_workorder_service.is_session_valid():
                logger.warning("Session expired before tasks API call")
                tasks = []
            else:
                # Define API URL for tasks
                tasks_api_url = f"{token_manager.base_url}/oslc/os/mxapiwodetail"

                # Fetch tasks for this work order (tasks have parent = wonum and istask = 1)
                task_filter_clause = f'parent="{wonum}" and istask=1 and historyflag=0'
                logger.info(f"🔍 TASK DEBUG: Task filter: {task_filter_clause}")

                task_params = {
                    "oslc.select": "wonum,description,owner,siteid,parent,taskid,status,siteid,priority,worktype,location,assetnum,targstartdate,schedstart,schedfinish,assignedto,lead,supervisor,crew,persongroup,parent,istask,statusdate,reportdate,estdur,status_description",
                    "oslc.where": task_filter_clause,
                    "oslc.pageSize": "50"
                }

                task_response = token_manager.session.get(
                    tasks_api_url,
                    params=task_params,
                    timeout=(5.0, 30),
                    headers={"Accept": "application/json"},
                    allow_redirects=True
                )

                # Check for session expiration in task response
                if 'login' in task_response.url.lower():
                    logger.warning("Session expired during task fetch")
                    tasks = []
                elif task_response.status_code == 200:
                    try:
                        content_type = task_response.headers.get('content-type', '').lower()
                        if 'application/json' in content_type:
                            task_data = task_response.json()
                            logger.info(f"🔍 TASK DEBUG: Response data type: {type(task_data)}")
                            logger.info(f"🔍 TASK DEBUG: Response keys: {list(task_data.keys()) if isinstance(task_data, dict) else 'Not a dict'}")

                            if isinstance(task_data, dict):
                                # Check for both 'member' and 'rdfs:member' fields
                                if 'member' in task_data:
                                    tasks = task_data['member']
                                elif 'rdfs:member' in task_data:
                                    tasks = task_data['rdfs:member']
                                else:
                                    tasks = []

                                if tasks:
                                    logger.info(f"🎉 WO TASKS: Found {len(tasks)} tasks for work order {wonum}")
                                    # Log first task for debugging
                                    first_task = tasks[0]
                                    logger.info(f"🔍 TASK DEBUG: First task wonum: {first_task.get('wonum', first_task.get('spi:wonum', 'N/A'))}")
                                    logger.info(f"🔍 TASK DEBUG: First task description: {first_task.get('description', first_task.get('spi:description', 'N/A'))}")
                                    logger.info(f"🔍 TASK DEBUG: First task keys: {list(first_task.keys()) if isinstance(first_task, dict) else 'Not a dict'}")
                                    logger.info(f"🔍 TASK DEBUG: First task full data: {str(first_task)[:300]}")

                                    # Clean and normalize task data - handle both spi: prefixed and direct field names
                                    cleaned_tasks = []
                                    for task_data in tasks:
                                        if isinstance(task_data, dict):
                                            # Helper function to get field value (try both spi: prefix and direct)
                                            def get_field(field_name):
                                                return task_data.get(field_name, task_data.get(f'spi:{field_name}', ''))

                                            cleaned_task = {
                                                'wonum': get_field('wonum'),
                                                'description': get_field('description'),
                                                'status': get_field('status'),
                                                'worktype': get_field('worktype'),
                                                'priority': get_field('priority'),
                                                'worktype': get_field('worktype'),
                                                'assignedto': get_field('assignedto'),
                                                'owner': get_field('owner'),
                                                'parent': get_field('parent'),
                                                'istask': get_field('istask'),
                                                'owner_group': get_field('ownergroup'),
                                                'lead': get_field('lead'),
                                                'supervisor': get_field('supervisor'),
                                                'crew': get_field('crew'),
                                                'persongroup': get_field('persongroup'),
                                                'location': get_field('location'),
                                                'assetnum': get_field('assetnum'),
                                                'targstartdate': get_field('targstartdate'),
                                                'schedstart': get_field('schedstart'),
                                                'schedfinish': get_field('schedfinish'),
                                                'estdur': get_field('estdur') or 0,
                                                'parent': get_field('parent'),
                                                'istask': get_field('istask') or 1,
                                                'statusdate': get_field('statusdate'),
                                                'reportdate': get_field('reportdate'),
                                                'status_description': get_field('status_description'),
                                                'siteid': get_field('siteid'),
                                                'taskid': get_field('taskid'),
                                                'lead': get_field('lead'),
                                                'supervisor': get_field('supervisor'),
                                                'crew': get_field('crew'),
                                                'persongroup': get_field('persongroup'),
                                                'location': get_field('location'),
                                                'assetnum': get_field('assetnum'),
                                                'targstartdate': get_field('targstartdate'),
                                                'schedstart': get_field('schedstart'),
                                                'schedfinish': get_field('schedfinish'),
                                                'estdur': get_field('estdur') or 0,
                                                'parent': get_field('parent'),
                                                'istask': get_field('istask') or 1,
                                                'statusdate': get_field('statusdate'),
                                                'reportdate': get_field('reportdate'),
                                                'status_description': get_field('status_description')
                                            }
                                            cleaned_tasks.append(cleaned_task)

                                    tasks = cleaned_tasks
                                    logger.info(f"🔧 TASK DEBUG: Cleaned {len(tasks)} tasks")
                                    if tasks:
                                        logger.info(f"🔧 TASK DEBUG: First cleaned task: {tasks[0].get('wonum', 'N/A')} - {tasks[0].get('description', 'N/A')[:50]}")
                                        logger.info(f"🔧 TASK DEBUG: First task assignedto: '{tasks[0].get('assignedto', 'N/A')}'")
                                        logger.info(f"🔧 TASK DEBUG: First task lead: '{tasks[0].get('lead', 'N/A')}'")
                                        logger.info(f"🔧 TASK DEBUG: First task supervisor: '{tasks[0].get('supervisor', 'N/A')}'")
                                        logger.info(f"🔧 TASK DEBUG: First task crew: '{tasks[0].get('crew', 'N/A')}'")
                                        logger.info(f"🔧 TASK DEBUG: First task persongroup: '{tasks[0].get('persongroup', 'N/A')}'")
                                else:
                                    logger.info(f"🔍 TASK DEBUG: No tasks in member field")
                                    logger.info(f"🔍 TASK DEBUG: Response content: {str(task_data)[:200]}")
                                    logger.info(f"No tasks found for work order {wonum}")
                            else:
                                logger.info(f"🔍 TASK DEBUG: Response is not a dict")
                                logger.info(f"No tasks found for work order {wonum}")
                        else:
                            logger.warning(f"Got HTML response for tasks - session may have expired")
                            logger.info(f"🔍 TASK DEBUG: Content type: {content_type}")
                            tasks = []
                    except Exception as e:
                        logger.error(f"Error parsing task response: {e}")
                        logger.info(f"🔍 TASK DEBUG: Raw response: {task_response.text[:200]}")
                        tasks = []
                else:
                    logger.warning(f"Task API call failed: {task_response.status_code}")
                    logger.info(f"🔍 TASK DEBUG: Error response: {task_response.text[:200]}")
                    tasks = []

        except Exception as e:
            logger.error(f"Error fetching tasks: {e}")

        load_time = time.time() - start_time
        logger.info(f"🚀 WO DETAIL: Total load time: {load_time:.3f}s")

        return render_template(
            'workorder_detail.html',
            workorder=workorder,
            tasks=tasks,
            user_site_id=user_site_id,
            load_time=load_time,
            auth_method="Session Cookies (Winning Method)"
        )

    except Exception as e:
        logger.error(f"Work order detail error: {str(e)}")
        flash(f'Error loading work order details: {str(e)}', 'error')
        return redirect(url_for('enhanced_workorders'))

# Complete MXAPIWODETAIL Service Implementation
class MXAPIWODetailService:
    """Complete implementation of all MXAPIWODETAIL API methods and actions"""

    def __init__(self, token_manager):
        self.token_manager = token_manager
        self.logger = logging.getLogger(__name__)

        # Standard Maximo Work Order Status Transitions
        self.status_transitions = {
            'WAPPR': ['APPR', 'CAN'],  # Waiting for Approval -> Approved, Cancelled
            'APPR': ['INPRG', 'CAN', 'CLOSE'],  # Approved -> In Progress, Cancelled, Closed
            'ASSIGN': ['INPRG', 'APPR', 'CAN'],  # Assigned -> In Progress, Approved, Cancelled
            'INPRG': ['COMP', 'CAN', 'CLOSE'],  # In Progress -> Complete, Cancelled, Closed
            'COMP': ['CLOSE', 'INPRG'],  # Complete -> Closed, In Progress
            'CLOSE': [],  # Closed (final state)
            'CAN': []  # Cancelled (final state)
        }

        # Available WSMethods for Work Orders
        self.available_methods = {
            'changeStatus': 'Change work order status',
            'approve': 'Approve work order',
            'start': 'Start work order (set to INPRG)',
            'complete': 'Complete work order (set to COMP)',
            'close': 'Close work order (set to CLOSE)',
            'cancel': 'Cancel work order (set to CAN)',
            'assign': 'Assign work order',
            'unassign': 'Unassign work order',
            'addLabor': 'Add labor to work order',
            'addMaterial': 'Add material to work order',
            'addTool': 'Add tool to work order',
            'addService': 'Add service to work order',
            'createFollowUp': 'Create follow-up work order',
            'duplicate': 'Duplicate work order',
            'route': 'Route work order',
            'plan': 'Plan work order',
            'schedule': 'Schedule work order'
        }

    def get_api_url(self, action=None, resource_id=None):
        """Get the correct API URL for mxapiwodetail operations using session authentication"""
        # Use /oslc/ endpoint like the working work order calls, not /api/
        base_url = f"{self.token_manager.base_url}/oslc/os/mxapiwodetail"

        if resource_id:
            base_url += f"/{resource_id}"

        if action:
            base_url += f"?action={action}"

        return base_url

    def get_headers(self, method_override=None):
        """Get standard headers for API requests using session authentication"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        if method_override:
            headers["X-method-override"] = method_override

        return headers

    def get_workorder_resource_id(self, wonum):
        """Get the resource ID for a work order by querying the API"""
        try:
            # Query the work order to get its resource ID
            api_url = f"{self.token_manager.base_url}/oslc/os/mxapiwodetail"
            params = {
                "oslc.select": "wonum,rdf:about",
                "oslc.where": f'wonum="{wonum}"',
                "oslc.pageSize": "1"
            }

            self.logger.info(f"🔍 MXAPI: Querying resource ID for {wonum}")
            self.logger.info(f"🔍 MXAPI: URL: {api_url}")
            self.logger.info(f"🔍 MXAPI: Params: {params}")

            response = self.token_manager.session.get(
                api_url,
                params=params,
                timeout=(5.0, 15)
            )

            self.logger.info(f"🔍 MXAPI: Resource lookup response status: {response.status_code}")
            self.logger.info(f"🔍 MXAPI: Resource lookup response content: {response.text[:500]}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    self.logger.info(f"🔍 MXAPI: Parsed JSON keys: {list(data.keys())}")

                    members = data.get('rdfs:member', data.get('member', []))
                    self.logger.info(f"🔍 MXAPI: Found {len(members)} members")

                    if members:
                        first_member = members[0]
                        self.logger.info(f"🔍 MXAPI: First member keys: {list(first_member.keys())}")

                        # Try multiple ways to get the resource ID
                        resource_id = None

                        # Method 1: Try rdf:about field
                        rdf_about = first_member.get('rdf:about', '')
                        self.logger.info(f"🔍 MXAPI: rdf:about value: {rdf_about}")

                        if rdf_about:
                            # Extract resource ID from rdf:about URL
                            # Format: https://domain/maximo/oslc/os/mxapiwodetail/_RESOURCE_ID_
                            resource_id = rdf_about.split('/')[-1]
                            self.logger.info(f"🔍 MXAPI: Found resource ID from rdf:about for {wonum}: {resource_id}")
                            return resource_id

                        # Method 2: Try href field
                        href = first_member.get('href', '')
                        self.logger.info(f"🔍 MXAPI: href value: {href}")

                        if href:
                            # Extract resource ID from href URL
                            # Format: https://domain/maximo/oslc/os/mxapiwodetail/_RESOURCE_ID_
                            resource_id = href.split('/')[-1]
                            self.logger.info(f"🔍 MXAPI: Found resource ID from href for {wonum}: {resource_id}")
                            return resource_id

                        # Method 3: Try to construct resource ID from wonum and siteid
                        # This is a fallback method based on Maximo's typical resource ID format
                        if wonum:
                            # Maximo often uses base64-like encoding for resource IDs
                            # Try common patterns
                            import base64
                            try:
                                # Pattern 1: Simple encoding
                                potential_id = f"_TENWS1dULz{wonum}"
                                self.logger.info(f"🔍 MXAPI: Trying constructed resource ID for {wonum}: {potential_id}")
                                return potential_id
                            except Exception as e:
                                self.logger.warning(f"🔍 MXAPI: Could not construct resource ID: {e}")

                        self.logger.warning(f"🔍 MXAPI: No resource ID found in any field for {wonum}")
                    else:
                        self.logger.warning(f"⚠️ MXAPI: No members found for work order {wonum}")

                except ValueError as json_error:
                    self.logger.error(f"JSON parsing error for {wonum}: {str(json_error)}")
                    self.logger.error(f"Raw response: {response.text}")
            else:
                self.logger.error(f"HTTP error {response.status_code} for {wonum}: {response.text}")

            self.logger.warning(f"⚠️ MXAPI: Could not find resource ID for work order {wonum}")
            return None

        except Exception as e:
            self.logger.error(f"Error getting resource ID for {wonum}: {str(e)}")
            return None

    def execute_wsmethod(self, method_name, wonum=None, data=None, bulk=False, resource_id=None):
        """Execute any WSMethod on work order(s) with proper resource ID handling"""
        try:
            if method_name not in self.available_methods:
                return {
                    'success': False,
                    'error': f'Unknown method: {method_name}',
                    'available_methods': list(self.available_methods.keys())
                }

            # For individual work order operations, we need the resource ID
            if not bulk and wonum and not resource_id:
                resource_id = self.get_workorder_resource_id(wonum)
                if not resource_id:
                    return {
                        'success': False,
                        'error': f'Could not find resource ID for work order {wonum}. This is required for status changes.'
                    }

            # Prepare URL and data based on operation type
            action = f"wsmethod:{method_name}"

            if bulk and isinstance(data, list):
                # Bulk operation - use collection URL with BULK header
                api_url = self.get_api_url(action=action)
                request_data = data
                headers = self.get_headers("BULK")
                self.logger.info(f"🔄 MXAPI: Bulk operation - {len(data)} work orders")
            else:
                # Individual operation - use resource-specific URL
                if resource_id:
                    api_url = self.get_api_url(action=action, resource_id=resource_id)
                    request_data = data or {}
                    # Don't include wonum in data when using resource ID in URL
                    headers = self.get_headers("PATCH")
                    self.logger.info(f"🔄 MXAPI: Individual operation with resource ID: {resource_id}")
                else:
                    # Fallback to collection URL (may not work for all operations)
                    api_url = self.get_api_url(action=action)
                    request_data = data or {}
                    if wonum:
                        request_data['wonum'] = wonum
                    headers = self.get_headers("PATCH")
                    self.logger.info(f"🔄 MXAPI: Individual operation without resource ID (fallback)")

            self.logger.info(f"🔄 MXAPI: Executing {method_name} on work order(s)")
            self.logger.info(f"🔄 MXAPI: URL: {api_url}")
            self.logger.info(f"🔄 MXAPI: Data: {request_data}")
            self.logger.info(f"🔄 MXAPI: Headers: {headers}")

            # Execute request using session authentication (same as working work order calls)
            response = self.token_manager.session.post(
                api_url,
                json=request_data,
                headers=headers,
                timeout=(5.0, 30)
            )

            return self._process_response(response, method_name)

        except Exception as e:
            self.logger.error(f"Error executing {method_name}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _process_response(self, response, method_name):
        """Process Maximo API response and handle errors"""
        try:
            self.logger.info(f"🔍 MXAPI RESPONSE: Status: {response.status_code}")
            self.logger.info(f"🔍 MXAPI RESPONSE: Content: {response.text}")

            if response.status_code in [200, 201, 204]:
                try:
                    response_json = response.json()

                    # Check for Maximo errors in successful HTTP responses
                    if isinstance(response_json, list):
                        errors = []
                        successes = []

                        for item in response_json:
                            if '_responsedata' in item and 'Error' in item['_responsedata']:
                                error_info = item['_responsedata']['Error']
                                errors.append({
                                    'code': error_info.get('reasonCode', 'Unknown'),
                                    'message': error_info.get('message', 'Unknown error')
                                })
                            else:
                                successes.append(item)

                        if errors:
                            self.logger.error(f"❌ MXAPI ERRORS: {errors}")
                            return {
                                'success': False,
                                'errors': errors,
                                'successes': successes,
                                'method': method_name
                            }

                    self.logger.info(f"✅ MXAPI: {method_name} executed successfully")
                    return {
                        'success': True,
                        'data': response_json,
                        'method': method_name
                    }

                except ValueError:
                    # Non-JSON response but successful HTTP status
                    return {
                        'success': True,
                        'message': f'{method_name} executed successfully',
                        'method': method_name
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'details': response.text[:200],
                    'method': method_name
                }

        except Exception as e:
            self.logger.error(f"Error processing response: {str(e)}")
            return {'success': False, 'error': f'Response processing error: {str(e)}'}

# Initialize the complete MXAPIWODETAIL service
mxapi_service = MXAPIWODetailService(token_manager)

@app.route('/api/task/<task_wonum>/status', methods=['POST'])
def update_task_status(task_wonum):
    """Update task status using direct API call with fallback methods."""
    # Check if user is logged in
    if not hasattr(token_manager, 'username') or not token_manager.username:
        return jsonify({'success': False, 'error': 'Not logged in'})

    try:
        # Get the new status from request
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({'success': False, 'error': 'Status is required'})

        new_status = data['status']

        # Validate status
        valid_statuses = ['WAPPR', 'APPR', 'ASSIGN', 'INPRG', 'COMP', 'CLOSE', 'CAN']
        if new_status not in valid_statuses:
            return jsonify({'success': False, 'error': f'Invalid status: {new_status}'})

        logger.info(f"🔄 TASK STATUS: Updating task {task_wonum} -> {new_status}")

        # Method 1: Try using the MXAPI service first
        try:
            result = mxapi_service.execute_wsmethod(
                'changeStatus',
                wonum=task_wonum,
                data={'status': new_status}
            )

            if result.get('success'):
                logger.info(f"✅ TASK STATUS: Successfully updated via MXAPI service")
                return jsonify(result)
            else:
                logger.warning(f"⚠️ TASK STATUS: MXAPI service failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.warning(f"⚠️ TASK STATUS: MXAPI service exception: {e}")

        # Method 2: Direct API call using collection URL (fallback)
        logger.info(f"🔄 TASK STATUS: Trying direct API call for task {task_wonum}")

        base_url = getattr(token_manager, 'base_url', '')
        api_url = f"{base_url}/oslc/os/mxapiwodetail"

        # Use collection URL with action parameter
        action_url = f"{api_url}?action=wsmethod:changeStatus"

        # Prepare request data
        request_data = {
            'wonum': task_wonum,
            'status': new_status
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-method-override": "PATCH"
        }

        logger.info(f"🔄 TASK STATUS: Direct API URL: {action_url}")
        logger.info(f"🔄 TASK STATUS: Request data: {request_data}")

        response = token_manager.session.post(
            action_url,
            json=request_data,
            headers=headers,
            timeout=(5.0, 30)
        )

        logger.info(f"🔍 TASK STATUS: Response status: {response.status_code}")
        logger.info(f"🔍 TASK STATUS: Response content: {response.text[:500]}")

        if response.status_code in [200, 201, 204]:
            try:
                response_json = response.json()
                logger.info(f"✅ TASK STATUS: Successfully updated via direct API")
                return jsonify({
                    'success': True,
                    'data': response_json,
                    'method': 'direct_api'
                })
            except ValueError:
                # Non-JSON response but successful HTTP status
                logger.info(f"✅ TASK STATUS: Successfully updated (non-JSON response)")
                return jsonify({
                    'success': True,
                    'message': f'Task {task_wonum} status updated to {new_status}',
                    'method': 'direct_api'
                })
        else:
            logger.error(f"❌ TASK STATUS: Direct API failed with status {response.status_code}")
            return jsonify({
                'success': False,
                'error': f'HTTP {response.status_code}',
                'details': response.text[:200],
                'method': 'direct_api'
            })

    except Exception as e:
        logger.error(f"Error updating task status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# Complete MXAPIWODETAIL API Endpoints - All Methods Available
@app.route('/api/mxapiwodetail/methods', methods=['GET'])
def get_available_methods():
    """Get list of all available MXAPIWODETAIL methods"""
    return jsonify({
        'success': True,
        'methods': mxapi_service.available_methods,
        'status_transitions': mxapi_service.status_transitions
    })

@app.route('/api/mxapiwodetail/<wonum>/execute/<method_name>', methods=['POST'])
def execute_workorder_method(wonum, method_name):
    """Execute any MXAPIWODETAIL method on a specific work order"""
    try:
        data = request.get_json() or {}
        result = mxapi_service.execute_wsmethod(method_name, wonum=wonum, data=data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error executing {method_name} on {wonum}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mxapiwodetail/bulk/<method_name>', methods=['POST'])
def execute_bulk_workorder_method(method_name):
    """Execute any MXAPIWODETAIL method on multiple work orders (bulk operation)"""
    try:
        data = request.get_json()
        if not isinstance(data, list):
            return jsonify({'success': False, 'error': 'Bulk operations require an array of work order data'})

        # For bulk operations, we need to add href to each work order if not present
        enhanced_data = []
        for item in data:
            if 'wonum' in item and 'href' not in item:
                # Get the resource ID for this work order
                wonum = item['wonum']
                resource_id = mxapi_service.get_workorder_resource_id(wonum)
                if resource_id:
                    # Add href to the item
                    item['href'] = f"{mxapi_service.token_manager.base_url}/oslc/os/mxapiwodetail/{resource_id}"
                    logger.info(f"🔗 BULK: Added href for {wonum}: {item['href']}")
                else:
                    logger.warning(f"⚠️ BULK: Could not get resource ID for {wonum}")
            enhanced_data.append(item)

        result = mxapi_service.execute_wsmethod(method_name, data=enhanced_data, bulk=True)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error executing bulk {method_name}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# Specific method endpoints for common operations
@app.route('/api/workorder/<wonum>/approve', methods=['POST'])
def approve_workorder(wonum):
    """Approve a work order"""
    try:
        data = request.get_json() or {}
        result = mxapi_service.execute_wsmethod('approve', wonum=wonum, data=data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/workorder/<wonum>/start', methods=['POST'])
def start_workorder(wonum):
    """Start a work order (set to INPRG)"""
    try:
        data = request.get_json() or {}
        result = mxapi_service.execute_wsmethod('start', wonum=wonum, data=data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/workorder/<wonum>/complete', methods=['POST'])
def complete_workorder(wonum):
    """Complete a work order (set to COMP)"""
    try:
        data = request.get_json() or {}
        result = mxapi_service.execute_wsmethod('complete', wonum=wonum, data=data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/workorder/<wonum>/close', methods=['POST'])
def close_workorder(wonum):
    """Close a work order (set to CLOSE)"""
    try:
        data = request.get_json() or {}
        result = mxapi_service.execute_wsmethod('close', wonum=wonum, data=data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/workorder/<wonum>/cancel', methods=['POST'])
def cancel_workorder(wonum):
    """Cancel a work order (set to CAN)"""
    try:
        data = request.get_json() or {}
        result = mxapi_service.execute_wsmethod('cancel', wonum=wonum, data=data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/workorder/<wonum>/assign', methods=['POST'])
def assign_workorder(wonum):
    """Assign a work order to a person or group"""
    try:
        data = request.get_json() or {}
        result = mxapi_service.execute_wsmethod('assign', wonum=wonum, data=data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/workorder/<wonum>/duplicate', methods=['POST'])
def duplicate_workorder(wonum):
    """Duplicate a work order"""
    try:
        data = request.get_json() or {}
        result = mxapi_service.execute_wsmethod('duplicate', wonum=wonum, data=data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/workorder/<wonum>/route', methods=['POST'])
def route_workorder(wonum):
    """Route a work order"""
    try:
        data = request.get_json() or {}
        result = mxapi_service.execute_wsmethod('route', wonum=wonum, data=data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Enhanced status change with validation
@app.route('/api/workorder/<wonum>/change-status', methods=['POST'])
def change_workorder_status(wonum):
    """Change work order status with validation"""
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({'success': False, 'error': 'Status is required'})

        new_status = data['status']

        # Add status validation logic here if needed
        valid_statuses = ['WAPPR', 'APPR', 'ASSIGN', 'INPRG', 'COMP', 'CLOSE', 'CAN']
        if new_status not in valid_statuses:
            return jsonify({'success': False, 'error': f'Invalid status: {new_status}'})

        result = mxapi_service.execute_wsmethod('changeStatus', wonum=wonum, data={'status': new_status})
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Get tasks for a work order
@app.route('/api/workorder/<wonum>/tasks', methods=['GET'])
def get_workorder_tasks(wonum):
    """Get all tasks for a specific work order"""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        logger.info(f"🔍 TASKS: Fetching tasks for work order {wonum}")

        # Get tasks using the enhanced service
        base_url = getattr(enhanced_workorder_service.token_manager, 'base_url', '')
        api_url = f"{base_url}/oslc/os/mxapiwodetail"

        # Query for tasks (istask=1) that belong to this work order
        params = {
            "oslc.select": "wonum,description,status,siteid,priority,worktype,assignedto,location,assetnum,schedstart,estdur,parent,istask",
            "oslc.where": f'parent="{wonum}" and istask=1',
            "oslc.pageSize": "50"
        }

        response = enhanced_workorder_service.token_manager.session.get(
            api_url, params=params, timeout=(5.0, 15)
        )

        if response.status_code == 200:
            data = response.json()
            tasks = data.get('member', [])

            logger.info(f"🔍 TASKS: Found {len(tasks)} tasks for work order {wonum}")

            # Clean and format task data
            cleaned_tasks = []
            for task in tasks:
                cleaned_task = {
                    'wonum': task.get('wonum', ''),
                    'description': task.get('description', ''),
                    'owner': task.get('owner', ''),
                    'owner_group': task.get('ownergroup', ''),
                    'lead': task.get('lead', ''),
                    'supervisor': task.get('supervisor', ''),
                    'crew': task.get('crew', ''),
                    'persongroup': task.get('persongroup', ''),
                    'parent': task.get('parent', ''),
                    'istask': task.get('istask', 0),
                    'status': task.get('status', ''),
                    'status_description': task.get('status_description', ''),
                    'siteid': task.get('siteid', ''),
                    'priority': task.get('priority', ''),
                    'worktype': task.get('worktype', ''),
                    'assignedto': task.get('assignedto', ''),
                    'location': task.get('location', ''),
                    'assetnum': task.get('assetnum', ''),
                    'schedstart': task.get('schedstart', ''),
                    'estdur': task.get('estdur', ''),
                    'taskid': task.get('taskid', ''),
                    'istask': task.get('istask', 0)
                }
                cleaned_tasks.append(cleaned_task)

            return jsonify({
                'success': True,
                'tasks': cleaned_tasks,
                'count': len(cleaned_tasks),
                'parent_wonum': wonum
            })
        else:
            logger.error(f"Failed to fetch tasks: {response.status_code}")
            return jsonify({
                'success': False,
                'error': f'Failed to fetch tasks: {response.status_code}',
                'tasks': []
            })

    except Exception as e:
        logger.error(f"Error fetching tasks for {wonum}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'tasks': []
        })

# API Documentation Page
@app.route('/api-docs')
def api_documentation():
    """Complete API documentation for all MXAPIWODETAIL endpoints"""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Complete MXAPIWODETAIL API Documentation</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            body { background-color: #f8f9fa; }
            .api-header { background: linear-gradient(135deg, #007bff, #0056b3); color: white; padding: 30px 0; }
            .endpoint-card { margin: 20px 0; border-left: 4px solid #007bff; }
            .method-badge { font-size: 12px; padding: 4px 8px; border-radius: 4px; }
            .method-get { background: #28a745; color: white; }
            .method-post { background: #007bff; color: white; }
            .code-block { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 15px; margin: 10px 0; }
            .status-transition { background: #e9ecef; padding: 10px; border-radius: 4px; margin: 5px 0; }
        </style>
    </head>
    <body>
        <div class="api-header">
            <div class="container">
                <h1><i class="fas fa-code me-3"></i>Complete MXAPIWODETAIL API Documentation</h1>
                <p class="lead">All available Maximo Work Order API endpoints and methods</p>
            </div>
        </div>

        <div class="container mt-4">
            <!-- Overview Section -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-info-circle me-2"></i>API Overview</h3>
                </div>
                <div class="card-body">
                    <p>This API provides complete access to all IBM Maximo MXAPIWODETAIL methods and actions.
                    It supports both individual work order operations and bulk operations.</p>

                    <h5>Authentication</h5>
                    <p>All endpoints require user authentication. Make sure you're logged in before making API calls.</p>

                    <h5>Base URL</h5>
                    <div class="code-block">
                        <code>https://your-domain.com/api/</code>
                    </div>
                </div>
            </div>

            <!-- Available Methods -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-list me-2"></i>Available Methods</h3>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h5>Status Management</h5>
                            <ul>
                                <li><strong>changeStatus</strong> - Change work order status</li>
                                <li><strong>approve</strong> - Approve work order</li>
                                <li><strong>start</strong> - Start work order (set to INPRG)</li>
                                <li><strong>complete</strong> - Complete work order (set to COMP)</li>
                                <li><strong>close</strong> - Close work order (set to CLOSE)</li>
                                <li><strong>cancel</strong> - Cancel work order (set to CAN)</li>
                            </ul>
                        </div>
                        <div class="col-md-6">
                            <h5>Work Order Management</h5>
                            <ul>
                                <li><strong>assign</strong> - Assign work order</li>
                                <li><strong>unassign</strong> - Unassign work order</li>
                                <li><strong>duplicate</strong> - Duplicate work order</li>
                                <li><strong>route</strong> - Route work order</li>
                                <li><strong>plan</strong> - Plan work order</li>
                                <li><strong>schedule</strong> - Schedule work order</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Status Transitions -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-exchange-alt me-2"></i>Status Transitions</h3>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="status-transition">
                                <strong>WAPPR (Waiting for Approval)</strong><br>
                                Can transition to: APPR, CAN
                            </div>
                            <div class="status-transition">
                                <strong>APPR (Approved)</strong><br>
                                Can transition to: INPRG, CAN, CLOSE
                            </div>
                            <div class="status-transition">
                                <strong>ASSIGN (Assigned)</strong><br>
                                Can transition to: INPRG, APPR, CAN
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="status-transition">
                                <strong>INPRG (In Progress)</strong><br>
                                Can transition to: COMP, CAN, CLOSE
                            </div>
                            <div class="status-transition">
                                <strong>COMP (Complete)</strong><br>
                                Can transition to: CLOSE, INPRG
                            </div>
                            <div class="status-transition">
                                <strong>CLOSE/CAN (Final States)</strong><br>
                                No further transitions allowed
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Core Endpoints -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-cogs me-2"></i>Core API Endpoints</h3>
                </div>
                <div class="card-body">

                    <!-- Get Methods -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-get">GET</span> /api/mxapiwodetail/methods</h5>
                        <p>Get list of all available MXAPIWODETAIL methods and status transitions</p>
                        <div class="code-block">
                            <strong>Response:</strong><br>
                            <code>{
  "success": true,
  "methods": {...},
  "status_transitions": {...}
}</code>
                        </div>
                    </div>

                    <!-- Execute Method -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-post">POST</span> /api/mxapiwodetail/{wonum}/execute/{method_name}</h5>
                        <p>Execute any MXAPIWODETAIL method on a specific work order</p>
                        <div class="code-block">
                            <strong>Request Body:</strong><br>
                            <code>{
  "status": "INPRG",
  "memo": "Starting work",
  "assignedto": "JOHN.DOE"
}</code>
                        </div>
                    </div>

                    <!-- Bulk Operations -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-post">POST</span> /api/mxapiwodetail/bulk/{method_name}</h5>
                        <p>Execute any MXAPIWODETAIL method on multiple work orders (bulk operation)</p>
                        <div class="code-block">
                            <strong>Request Body:</strong><br>
                            <code>[
  {"wonum": "WO001", "status": "INPRG"},
  {"wonum": "WO002", "status": "COMP"},
  {"wonum": "WO003", "status": "CLOSE"}
]</code>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Specific Method Endpoints -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-tools me-2"></i>Specific Method Endpoints</h3>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h5>Status Change Operations</h5>
                            <ul class="list-unstyled">
                                <li><span class="method-badge method-post">POST</span> /api/workorder/{wonum}/approve</li>
                                <li><span class="method-badge method-post">POST</span> /api/workorder/{wonum}/start</li>
                                <li><span class="method-badge method-post">POST</span> /api/workorder/{wonum}/complete</li>
                                <li><span class="method-badge method-post">POST</span> /api/workorder/{wonum}/close</li>
                                <li><span class="method-badge method-post">POST</span> /api/workorder/{wonum}/cancel</li>
                                <li><span class="method-badge method-post">POST</span> /api/workorder/{wonum}/change-status</li>
                            </ul>
                        </div>
                        <div class="col-md-6">
                            <h5>Work Order Operations</h5>
                            <ul class="list-unstyled">
                                <li><span class="method-badge method-post">POST</span> /api/workorder/{wonum}/assign</li>
                                <li><span class="method-badge method-post">POST</span> /api/workorder/{wonum}/duplicate</li>
                                <li><span class="method-badge method-post">POST</span> /api/workorder/{wonum}/route</li>
                                <li><span class="method-badge method-post">POST</span> /api/task/{wonum}/status</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Examples -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-code me-2"></i>Usage Examples</h3>
                </div>
                <div class="card-body">

                    <h5>1. Change Work Order Status</h5>
                    <div class="code-block">
                        <strong>POST</strong> /api/workorder/WO12345/change-status<br>
                        <strong>Body:</strong> {"status": "INPRG"}
                    </div>

                    <h5>2. Approve Multiple Work Orders</h5>
                    <div class="code-block">
                        <strong>POST</strong> /api/mxapiwodetail/bulk/approve<br>
                        <strong>Body:</strong> [{"wonum": "WO001"}, {"wonum": "WO002"}]
                    </div>

                    <h5>3. Assign Work Order</h5>
                    <div class="code-block">
                        <strong>POST</strong> /api/workorder/WO12345/assign<br>
                        <strong>Body:</strong> {"assignedto": "JOHN.DOE", "ownergroup": "MAINT"}
                    </div>

                    <h5>4. Update Task Status</h5>
                    <div class="code-block">
                        <strong>POST</strong> /api/task/TASK001/status<br>
                        <strong>Body:</strong> {"status": "COMP"}
                    </div>
                </div>
            </div>

            <!-- Navigation -->
            <div class="text-center mt-4 mb-4">
                <a href="/welcome" class="btn btn-primary btn-lg me-3">
                    <i class="fas fa-home me-2"></i>Back to Welcome
                </a>
                <a href="/enhanced-workorders" class="btn btn-outline-secondary btn-lg me-3">
                    <i class="fas fa-clipboard-list me-2"></i>Work Orders
                </a>
                <a href="/api-docs/mxapisite" class="btn btn-outline-info btn-lg">
                    <i class="fas fa-building me-2"></i>Site Access API
                </a>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return html

@app.route('/test-fresh-profile')
def test_fresh_profile():
    """Test fresh profile retrieval with current session."""
    try:
        # Use the existing token manager session with cookies
        if not hasattr(token_manager, 'session'):
            return "<h1>No session available</h1>"

        # Get fresh profile data directly
        profile_url = f"{token_manager.base_url}/oslc/whoami"
        profile_response = token_manager.session.get(profile_url, timeout=30)

        html = f"""
        <h1>Fresh Profile Test</h1>
        <h2>Direct Profile API Call</h2>
        <p><strong>URL:</strong> {profile_url}</p>
        <p><strong>Status:</strong> {profile_response.status_code}</p>
        """

        if profile_response.status_code == 200:
            try:
                profile_data = profile_response.json()
                html += f"<h3>Profile Data Retrieved:</h3>"
                html += f"<pre>{json.dumps(profile_data, indent=2)}</pre>"

                # Extract key fields
                html += f"<h3>Key Profile Fields:</h3>"
                html += f"<ul>"
                html += f"<li><strong>Username:</strong> {profile_data.get('userName', 'N/A')}</li>"
                html += f"<li><strong>Display Name:</strong> {profile_data.get('displayName', 'N/A')}</li>"
                html += f"<li><strong>Default Site:</strong> {profile_data.get('defaultSite', 'N/A')}</li>"
                html += f"<li><strong>Insert Site:</strong> {profile_data.get('insertSite', 'N/A')}</li>"
                html += f"</ul>"

            except Exception as e:
                html += f"<p><strong>Parse Error:</strong> {str(e)}</p>"
                html += f"<p><strong>Raw Response:</strong> {profile_response.text[:1000]}</p>"
        else:
            html += f"<p><strong>Error:</strong> {profile_response.text[:500]}</p>"

        html += """
        <p><a href="/enhanced-profile">Back to Enhanced Profile</a></p>
        <p><a href="/welcome">Back to Welcome</a></p>
        """

        return html

    except Exception as e:
        return f"<h1>Fresh Profile Test Error: {str(e)}</h1><p><a href='/welcome'>Back to Welcome</a></p>"

@app.route('/direct-workorders')
def direct_workorders():
    """Direct work order fetch using current session cookies."""
    if 'username' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('index'))

    try:
        # Use the existing token manager session with cookies
        if not hasattr(token_manager, 'session'):
            return "<h1>No session available</h1>"

        # Get all sites first to find the correct one
        sites_url = f"{token_manager.base_url}/oslc/sites"
        sites_response = token_manager.session.get(sites_url, timeout=30)

        html = f"""
        <h1>Direct Work Order Fetch</h1>
        <h2>Step 1: Sites API Call</h2>
        <p><strong>URL:</strong> {sites_url}</p>
        <p><strong>Status:</strong> {sites_response.status_code}</p>
        """

        available_sites = []
        if sites_response.status_code == 200:
            try:
                sites_data = sites_response.json()
                if isinstance(sites_data, dict) and 'member' in sites_data:
                    available_sites = [site.get('siteid', 'Unknown') for site in sites_data['member'][:10]]
                    html += f"<p><strong>Available Sites:</strong> {', '.join(available_sites)}</p>"
                else:
                    html += f"<p><strong>Sites Response:</strong> {sites_response.text[:500]}</p>"
            except Exception as e:
                html += f"<p><strong>Sites Parse Error:</strong> {str(e)}</p>"
        else:
            html += f"<p><strong>Sites Error:</strong> {sites_response.text[:500]}</p>"

        # Try work orders with different site filters
        wo_url = f"{token_manager.base_url}/oslc/os/mxapiwodetail"

        # Test different site filters
        test_sites = available_sites[:3] if available_sites else ['IKWAJ', 'BEDFORD', 'CENTRAL']

        for test_site in test_sites:
            html += f"<h2>Step 2: Work Orders for Site {test_site}</h2>"

            params = {
                "oslc.select": "wonum,description,status,siteid,priority,worktype",
                "oslc.where": f"siteid=\"{test_site}\"",
                "oslc.pageSize": "5"
            }

            wo_response = token_manager.session.get(wo_url, params=params, timeout=30)
            html += f"<p><strong>Status:</strong> {wo_response.status_code}</p>"

            if wo_response.status_code == 200:
                try:
                    wo_data = wo_response.json()
                    if isinstance(wo_data, dict) and 'member' in wo_data:
                        workorders = wo_data['member']
                        html += f"<p><strong>Found:</strong> {len(workorders)} work orders</p>"

                        if workorders:
                            html += "<table border='1'><tr><th>WO Number</th><th>Description</th><th>Status</th><th>Site</th></tr>"
                            for wo in workorders[:5]:
                                html += f"""
                                <tr>
                                    <td>{wo.get('wonum', 'N/A')}</td>
                                    <td>{wo.get('description', 'N/A')[:50]}</td>
                                    <td>{wo.get('status', 'N/A')}</td>
                                    <td>{wo.get('siteid', 'N/A')}</td>
                                </tr>
                                """
                            html += "</table>"
                            break  # Found work orders, stop testing
                    else:
                        html += f"<p><strong>Response:</strong> {wo_response.text[:300]}</p>"
                except Exception as e:
                    html += f"<p><strong>Parse Error:</strong> {str(e)}</p>"
            else:
                html += f"<p><strong>Error:</strong> {wo_response.text[:300]}</p>"

        html += """
        <p><a href="/enhanced-workorders">Back to Enhanced Work Orders</a></p>
        <p><a href="/force-fresh-login">Force Fresh Login</a></p>
        <p><a href="/welcome">Back to Welcome</a></p>
        """

        return html

    except Exception as e:
        return f"<h1>Direct Test Error: {str(e)}</h1><p><a href='/welcome'>Back to Welcome</a></p>"

@app.route('/api/enhanced-workorders/available-sites', methods=['GET'])
def api_get_available_sites():
    """API endpoint for getting user's available sites for work order search."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    # Verify session
    if not enhanced_workorder_service.is_session_valid():
        return jsonify({'error': 'Session expired'}), 401

    try:
        # Get available sites from enhanced profile service
        sites = enhanced_profile_service.get_available_sites(use_cache=True)

        # Get user's default site for pre-selection
        user_profile = enhanced_profile_service.get_user_profile()
        default_site = user_profile.get('defaultSite', '') if user_profile else ''



        logger.info(f"🏢 API SITES: Retrieved {len(sites)} available sites for work order search")

        return jsonify({
            'success': True,
            'sites': sites,
            'default_site': default_site,
            'total_count': len(sites)
        })

    except Exception as e:
        logger.error(f"Error fetching available sites: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/enhanced-workorders/search', methods=['POST'])
def api_search_workorders():
    """API endpoint for searching work orders with pagination and filtering."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    # Verify session
    if not enhanced_workorder_service.is_session_valid():
        return jsonify({'error': 'Session expired'}), 401

    try:
        data = request.get_json() or {}

        # Extract search parameters
        search_criteria = data.get('search_criteria', {})
        page = data.get('page', 1)
        page_size = data.get('page_size', 20)

        # Validate page size (max 50 for performance)
        page_size = min(max(page_size, 1), 50)

        logger.info(f"🔍 API SEARCH: Criteria: {search_criteria}, Page: {page}, Size: {page_size}")

        # Execute search
        result = enhanced_workorder_service.search_workorders(
            search_criteria=search_criteria,
            page=page,
            page_size=page_size
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in workorder search API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/enhanced-workorder-details/<wonum>')
def enhanced_workorder_details(wonum):
    """Display detailed information for a specific work order using enhanced service."""
    # Just redirect to the working workorder_detail route
    return redirect(url_for('workorder_detail', wonum=wonum))


# Complete MXAPIWODETAIL Service Implementation

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

@app.route('/sync')
def sync():
    """Render the database sync page."""
    if 'username' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('index'))

    # Verify that we're still logged in
    if not token_manager.is_logged_in():
        flash('Your session has expired. Please login again.', 'warning')
        session.clear()
        return redirect(url_for('index'))

    return render_template('sync.html')

@app.route('/test-profile')
def test_profile():
    """Simple test page to view and refresh profile data."""
    if 'username' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('index'))

    try:
        # Get current profile data
        user_profile = enhanced_profile_service.get_user_profile()

        # Get session data
        session_data = {
            'username': session.get('username', ''),
            'default_site': session.get('default_site', ''),
            'insert_site': session.get('insert_site', ''),
            'first_name': session.get('first_name', ''),
            'last_name': session.get('last_name', '')
        }

        # Create simple HTML page with refresh button
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Profile Test - {session['username']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .profile-box {{ border: 1px solid #ccc; padding: 15px; margin: 10px 0; }}
                .refresh-btn {{ background: #007bff; color: white; padding: 10px 20px; border: none; cursor: pointer; }}
                .refresh-btn:hover {{ background: #0056b3; }}
                .success {{ color: green; }}
                .error {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>Profile Test for {session['username']}</h1>

            <div class="profile-box">
                <h3>Current Session Data:</h3>
                <p><strong>Username:</strong> {session_data['username']}</p>
                <p><strong>Default Site:</strong> {session_data['default_site']}</p>
                <p><strong>Insert Site:</strong> {session_data['insert_site']}</p>
                <p><strong>First Name:</strong> {session_data['first_name']}</p>
                <p><strong>Last Name:</strong> {session_data['last_name']}</p>
            </div>

            <div class="profile-box">
                <h3>Current Profile Service Data:</h3>
                <p><strong>Default Site:</strong> {user_profile.get('defaultSite', 'None') if user_profile else 'No profile data'}</p>
                <p><strong>Insert Site:</strong> {user_profile.get('insertSite', 'None') if user_profile else 'No profile data'}</p>
                <p><strong>First Name:</strong> {user_profile.get('firstName', 'None') if user_profile else 'No profile data'}</p>
                <p><strong>Last Name:</strong> {user_profile.get('lastName', 'None') if user_profile else 'No profile data'}</p>
            </div>

            <button class="refresh-btn" onclick="refreshProfile()">🔄 Refresh Profile from Maximo</button>
            <div id="result"></div>

            <p><a href="/welcome">← Back to Welcome</a></p>

            <script>
                function refreshProfile() {{
                    document.getElementById('result').innerHTML = '<p>Refreshing profile...</p>';

                    fetch('/api/refresh-profile', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }}
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            document.getElementById('result').innerHTML =
                                '<p class="success">✅ Profile refreshed successfully!</p>' +
                                '<p>New Default Site: ' + data.defaultSite + '</p>' +
                                '<p>New Insert Site: ' + data.insertSite + '</p>' +
                                '<p><em>Refresh this page to see updated data</em></p>';
                        }} else {{
                            document.getElementById('result').innerHTML =
                                '<p class="error">❌ Error: ' + data.error + '</p>';
                        }}
                    }})
                    .catch(error => {{
                        document.getElementById('result').innerHTML =
                            '<p class="error">❌ Network error: ' + error + '</p>';
                    }});
                }}
            </script>
        </body>
        </html>
        """

        return html

    except Exception as e:
        logger.error(f"Error in test profile page: {e}")
        return f"<h1>Error: {str(e)}</h1><p><a href='/welcome'>Back to Welcome</a></p>"

@app.route('/api/enhanced-profile', methods=['GET'])
def api_enhanced_profile():
    """API endpoint to get user profile data from Enhanced Profile service."""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})

    try:
        # Get user profile from Enhanced Profile service
        profile = enhanced_profile_service.get_user_profile()

        if profile:
            return jsonify(profile)
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to get profile'
            })
    except Exception as e:
        logger.error(f"Error getting profile via API: {e}")
        return jsonify({
            'success': False,
            'error': f'Error getting profile: {str(e)}'
        })

@app.route('/api/refresh-profile', methods=['POST'])
def refresh_profile():
    """API endpoint to refresh user profile data (for site changes)."""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})

    try:
        username = session['username']
        logger.info(f"🔄 PROFILE REFRESH: Refreshing profile for user {username}")

        # Clear all profile caches
        if 'enhanced_profile_service' in globals():
            enhanced_profile_service.invalidate_user_profile_cache(username)
            logger.info("✅ PROFILE REFRESH: Enhanced profile cache invalidated")

        if 'enhanced_workorder_service' in globals():
            enhanced_workorder_service.clear_cache('all')
            logger.info("✅ PROFILE REFRESH: Work order cache cleared")

        # Clear token manager profile cache
        if hasattr(token_manager, '_clear_profile_cache'):
            token_manager._clear_profile_cache(username)
            logger.info("✅ PROFILE REFRESH: Token manager profile cache cleared")

        # Force fresh profile fetch
        fresh_profile = None
        if 'enhanced_profile_service' in globals():
            fresh_profile = enhanced_profile_service.force_profile_refresh(username)

        if not fresh_profile:
            # Fallback to token manager
            fresh_profile = token_manager.get_user_profile(use_mock=False, use_cache=False, force_refresh=True)

        if fresh_profile:
            # Update session with fresh profile data
            session['default_site'] = fresh_profile.get('defaultSite', '')
            session['insert_site'] = fresh_profile.get('insertSite', '')
            session['first_name'] = fresh_profile.get('firstName', '')
            session['last_name'] = fresh_profile.get('lastName', '')

            logger.info(f"✅ PROFILE REFRESH: Fresh profile loaded - default site: {fresh_profile.get('defaultSite', 'None')}")
            return jsonify({
                'success': True,
                'message': 'Profile refreshed successfully',
                'defaultSite': fresh_profile.get('defaultSite', ''),
                'insertSite': fresh_profile.get('insertSite', '')
            })
        else:
            logger.error("Failed to fetch fresh profile data")
            return jsonify({'success': False, 'error': 'Failed to refresh profile data'})

    except Exception as e:
        logger.error(f"Error refreshing profile: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/logout')
def logout():
    """Handle logout with complete profile and cache cleanup including disk files."""
    username = session.get('username', 'User')

    # Clear session first
    session.clear()

    # Clear all profile and work order caches (memory + disk)
    try:
        # Clear enhanced service caches (memory + disk)
        if 'enhanced_profile_service' in globals():
            enhanced_profile_service.clear_cache('all')
            # Force clear disk cache for current user
            enhanced_profile_service.invalidate_user_profile_cache(username)
            logger.info("✅ LOGOUT: Enhanced profile service cache cleared (memory + disk)")

        if 'enhanced_workorder_service' in globals():
            enhanced_workorder_service.clear_cache('all')
            logger.info("✅ LOGOUT: Enhanced work order service cache cleared")

        # Clear token manager profile cache (memory + disk)
        if hasattr(token_manager, '_clear_profile_cache'):
            token_manager._clear_profile_cache(username)
            logger.info("✅ LOGOUT: Token manager profile cache cleared (memory + disk)")

        # Clear ALL disk cache files to prevent cross-user contamination
        import os
        import glob
        cache_patterns = [
            'cache/profile_*.pkl',
            'cache/enhanced_profile_*.pkl',
            'cache/workorder_*.pkl',
            'cache/sites_*.pkl'
        ]

        for pattern in cache_patterns:
            for cache_file in glob.glob(pattern):
                try:
                    os.remove(cache_file)
                    logger.info(f"✅ LOGOUT: Removed disk cache file: {cache_file}")
                except Exception as e:
                    logger.warning(f"Could not remove cache file {cache_file}: {e}")

    except Exception as e:
        logger.warning(f"Error clearing caches during logout: {e}")

    # Logout from token manager (clears tokens and session cookies)
    token_manager.logout()

    logger.info(f"✅ LOGOUT: User {username} logged out with COMPLETE cache cleanup (memory + all disk files)")
    flash(f'{username} has been logged out', 'info')
    return redirect(url_for('index'))

class MXAPISTEService:
    """Service class for handling MXAPISTE operations"""

    def __init__(self, token_manager):
        self.token_manager = token_manager
        self.logger = logging.getLogger(__name__)

        # Available WSMethods for Sites
        self.available_methods = {
            'getSiteInfo': 'Get site information',
            'getSiteHierarchy': 'Get site hierarchy',
            'getSiteAssets': 'Get assets associated with site',
            'getSiteLocations': 'Get locations in site',
            'getSiteWorkOrders': 'Get work orders for site',
            'getSiteInventory': 'Get inventory for site',
            'getSitePersonnel': 'Get personnel assigned to site',
            'getSiteEquipment': 'Get equipment in site',
            'getSiteDocuments': 'Get documents associated with site',
            'getSiteHistory': 'Get site history'
        }

    def get_api_url(self, action=None, resource_id=None):
        """Get the correct API URL for mxapiste operations using session authentication"""
        base_url = f"{self.token_manager.base_url}/oslc/os/mxapiste"

        if resource_id:
            base_url += f"/{resource_id}"

        if action:
            base_url += f"?action={action}"

        return base_url

    def get_headers(self, method_override=None):
        """Get standard headers for API requests using session authentication"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        if method_override:
            headers["X-method-override"] = method_override

        return headers

    def get_site_resource_id(self, siteid):
        """Get the resource ID for a site by querying the API"""
        try:
            # Query the site to get its resource ID
            api_url = self.get_api_url()
            params = {
                "oslc.select": "siteid,rdf:about",
                "oslc.where": f'siteid="{siteid}"',
                "oslc.pageSize": "1"
            }

            self.logger.info(f"🔍 MXAPI: Querying resource ID for site {siteid}")
            self.logger.info(f"🔍 MXAPI: URL: {api_url}")
            self.logger.info(f"🔍 MXAPI: Params: {params}")

            response = self.token_manager.session.get(
                api_url,
                params=params,
                timeout=(5.0, 15)
            )

            self.logger.info(f"🔍 MXAPI: Resource lookup response status: {response.status_code}")
            self.logger.info(f"🔍 MXAPI: Resource lookup response content: {response.text[:500]}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'member' in data and len(data['member']) > 0:
                        return data['member'][0]['rdf:about'].split('/')[-1]
                except (KeyError, IndexError, ValueError) as e:
                    self.logger.error(f"Error parsing site resource ID: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting site resource ID: {str(e)}")
            return None

    def execute_wsmethod(self, method_name, siteid=None, data=None, bulk=False):
        """Execute a WSMethod on site(s)"""
        try:
            if method_name not in self.available_methods:
                return {
                    'success': False,
                    'error': f'Unknown method: {method_name}',
                    'available_methods': list(self.available_methods.keys())
                }

            # For individual site operations, we need the resource ID
            resource_id = None
            if not bulk and siteid:
                resource_id = self.get_site_resource_id(siteid)
                if not resource_id:
                    return {
                        'success': False,
                        'error': f'Could not find resource ID for site {siteid}'
                    }

            # Prepare URL and data based on operation type
            action = f"wsmethod:{method_name}"

            if bulk and isinstance(data, list):
                # Bulk operation - use collection URL with BULK header
                api_url = self.get_api_url(action=action)
                request_data = data
                headers = self.get_headers("BULK")
                self.logger.info(f"🔄 MXAPI: Bulk operation - {len(data)} sites")
            else:
                # Individual operation - use resource-specific URL
                if resource_id:
                    api_url = self.get_api_url(action=action, resource_id=resource_id)
                    request_data = data or {}
                    headers = self.get_headers("PATCH")
                    self.logger.info(f"🔄 MXAPI: Individual operation with resource ID: {resource_id}")
                else:
                    # Fallback to collection URL
                    api_url = self.get_api_url(action=action)
                    request_data = data or {}
                    if siteid:
                        request_data['siteid'] = siteid
                    headers = self.get_headers("PATCH")
                    self.logger.info(f"🔄 MXAPI: Individual operation without resource ID (fallback)")

            self.logger.info(f"🔄 MXAPI: Executing {method_name} on site(s)")
            self.logger.info(f"🔄 MXAPI: URL: {api_url}")
            self.logger.info(f"🔄 MXAPI: Data: {request_data}")
            self.logger.info(f"🔄 MXAPI: Headers: {headers}")

            # Execute request using session authentication
            response = self.token_manager.session.post(
                api_url,
                json=request_data,
                headers=headers,
                timeout=(5.0, 30)
            )

            return self._process_response(response, method_name)

        except Exception as e:
            self.logger.error(f"Error executing {method_name}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _process_response(self, response, method_name):
        """Process Maximo API response and handle errors"""
        try:
            self.logger.info(f"🔍 MXAPI RESPONSE: Status: {response.status_code}")
            self.logger.info(f"🔍 MXAPI RESPONSE: Content: {response.text}")

            if response.status_code in [200, 201, 204]:
                try:
                    response_json = response.json()

                    # Check for Maximo errors in successful HTTP responses
                    if isinstance(response_json, list):
                        errors = []
                        successes = []

                        for item in response_json:
                            if '_responsedata' in item and 'Error' in item['_responsedata']:
                                error_info = item['_responsedata']['Error']
                                errors.append({
                                    'code': error_info.get('reasonCode', 'Unknown'),
                                    'message': error_info.get('message', 'Unknown error')
                                })
                            else:
                                successes.append(item)

                        if errors:
                            self.logger.error(f"❌ MXAPI ERRORS: {errors}")
                            return {
                                'success': False,
                                'errors': errors,
                                'successes': successes,
                                'method': method_name
                            }

                    self.logger.info(f"✅ MXAPI: {method_name} executed successfully")
                    return {
                        'success': True,
                        'data': response_json,
                        'method': method_name
                    }

                except ValueError:
                    # Non-JSON response but successful HTTP status
                    return {
                        'success': True,
                        'message': f'{method_name} executed successfully',
                        'method': method_name
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'details': response.text[:200],
                    'method': method_name
                }

        except Exception as e:
            self.logger.error(f"Error processing response: {str(e)}")
            return {'success': False, 'error': f'Response processing error: {str(e)}'}

# Initialize the MXAPISTE service
mxapiste_service = MXAPISTEService(token_manager)

# Initialize the Task Planned Materials service
from backend.services.task_planned_materials_service import TaskPlannedMaterialsService
task_materials_service = TaskPlannedMaterialsService(token_manager)

# Initialize the Task Labor service
from backend.services.task_labor_service import TaskLaborService
task_labor_service = TaskLaborService(token_manager)

# Initialize the Inventory Search service
from backend.services.inventory_search_service import InventorySearchService
inventory_search_service = InventorySearchService(token_manager)

# Initialize the Material Request service
from backend.services.material_request_service import MaterialRequestService
material_request_service = MaterialRequestService(token_manager, task_materials_service, enhanced_profile_service, inventory_search_service)



# MXAPISTE API Endpoints
@app.route('/api/mxapiste/methods', methods=['GET'])
def get_available_site_methods():
    """Get list of all available MXAPISTE methods"""
    return jsonify({
        'success': True,
        'methods': mxapiste_service.available_methods
    })

@app.route('/api/mxapiste/<siteid>/execute/<method_name>', methods=['POST'])
def execute_site_method(siteid, method_name):
    """Execute any MXAPISTE method on a specific site"""
    try:
        data = request.get_json() or {}
        result = mxapiste_service.execute_wsmethod(method_name, siteid=siteid, data=data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error executing {method_name} on {siteid}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mxapiste/bulk/<method_name>', methods=['POST'])
def execute_bulk_site_method(method_name):
    """Execute any MXAPISTE method on multiple sites (bulk operation)"""
    try:
        data = request.get_json()
        if not isinstance(data, list):
            return jsonify({'success': False, 'error': 'Bulk operations require an array of site data'})

        # For bulk operations, we need to add href to each site if not present
        enhanced_data = []
        for item in data:
            if 'siteid' in item and 'href' not in item:
                # Get the resource ID for this site
                siteid = item['siteid']
                resource_id = mxapiste_service.get_site_resource_id(siteid)
                if resource_id:
                    # Add href to the item
                    item['href'] = f"{mxapiste_service.token_manager.base_url}/oslc/os/mxapiste/{resource_id}"
                    logger.info(f"🔗 BULK: Added href for {siteid}: {item['href']}")
                else:
                    logger.warning(f"⚠️ BULK: Could not get resource ID for {siteid}")
            enhanced_data.append(item)

        result = mxapiste_service.execute_wsmethod(method_name, data=enhanced_data, bulk=True)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error executing bulk {method_name}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# Specific method endpoints for common operations
@app.route('/api/site/<siteid>/info', methods=['GET'])
def get_site_info(siteid):
    """Get site information"""
    try:
        # Use mxapiperuser to get site info
        api_url = f"{token_manager.base_url}/oslc/os/mxapiperuser"
        params = {
            "oslc.select": "siteid,description,status,type,address,contact,phone,email",
            "oslc.where": f'siteid="{siteid}"',
            "oslc.pageSize": "1"
        }

        response = token_manager.session.get(
            api_url,
            params=params,
            timeout=(5.0, 15)
        )

        if response.status_code == 200:
            data = response.json()
            if 'member' in data and len(data['member']) > 0:
                site_data = data['member'][0]

                # Clean and format site data
                cleaned_site = {
                    'siteid': site_data.get('siteid', ''),
                    'description': site_data.get('description', ''),
                    'status': site_data.get('status', ''),
                    'type': site_data.get('type', ''),
                    'address': site_data.get('address', ''),
                    'contact': site_data.get('contact', ''),
                    'phone': site_data.get('phone', ''),
                    'email': site_data.get('email', '')
                }

                return jsonify({
                    'success': True,
                    'data': cleaned_site
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Could not find site {siteid}'
                })
        else:
            logger.error(f"Failed to fetch site info: {response.status_code}")
            return jsonify({
                'success': False,
                'error': f'Failed to fetch site info: {response.status_code}'
            })

    except Exception as e:
        logger.error(f"Error getting site info: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/site/<siteid>/hierarchy', methods=['GET'])
def get_site_hierarchy(siteid):
    """Get site hierarchy"""
    try:
        result = mxapiste_service.execute_wsmethod('getSiteHierarchy', siteid=siteid)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/site/<siteid>/assets', methods=['GET'])
def get_site_assets(siteid):
    """Get assets associated with site"""
    try:
        result = mxapiste_service.execute_wsmethod('getSiteAssets', siteid=siteid)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/site/<siteid>/locations', methods=['GET'])
def get_site_locations(siteid):
    """Get locations in site"""
    try:
        result = mxapiste_service.execute_wsmethod('getSiteLocations', siteid=siteid)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/site/<siteid>/workorders', methods=['GET'])
def get_site_workorders(siteid):
    """Get work orders for site"""
    try:
        result = mxapiste_service.execute_wsmethod('getSiteWorkOrders', siteid=siteid)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/site/<siteid>/inventory', methods=['GET'])
def get_site_inventory(siteid):
    """Get inventory for site"""
    try:
        result = mxapiste_service.execute_wsmethod('getSiteInventory', siteid=siteid)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/site/<siteid>/personnel', methods=['GET'])
def get_site_personnel(siteid):
    """Get personnel assigned to site"""
    try:
        result = mxapiste_service.execute_wsmethod('getSitePersonnel', siteid=siteid)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/site/<siteid>/equipment', methods=['GET'])
def get_site_equipment(siteid):
    """Get equipment in site"""
    try:
        result = mxapiste_service.execute_wsmethod('getSiteEquipment', siteid=siteid)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/site/<siteid>/documents', methods=['GET'])
def get_site_documents(siteid):
    """Get documents associated with site"""
    try:
        result = mxapiste_service.execute_wsmethod('getSiteDocuments', siteid=siteid)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/site/<siteid>/history', methods=['GET'])
def get_site_history(siteid):
    """Get site history"""
    try:
        result = mxapiste_service.execute_wsmethod('getSiteHistory', siteid=siteid)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# MXAPISITE API Documentation Page
@app.route('/api-docs/mxapiste')
def mxapiste_documentation():
    """Complete API documentation for all MXAPISTE endpoints"""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Complete MXAPISTE API Documentation</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            body { background-color: #f8f9fa; }
            .api-header { background: linear-gradient(135deg, #007bff, #0056b3); color: white; padding: 30px 0; }
            .endpoint-card { margin: 20px 0; border-left: 4px solid #007bff; }
            .method-badge { font-size: 12px; padding: 4px 8px; border-radius: 4px; }
            .method-get { background: #28a745; color: white; }
            .method-post { background: #007bff; color: white; }
            .code-block { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 15px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="api-header">
            <div class="container">
                <h1><i class="fas fa-building me-3"></i>Complete MXAPISTE API Documentation</h1>
                <p class="lead">All available Maximo Site API endpoints and methods</p>
            </div>
        </div>

        <div class="container mt-4">
            <!-- Overview Section -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-info-circle me-2"></i>API Overview</h3>
                </div>
                <div class="card-body">
                    <p>This API provides access to site-related information in Maximo, including site details, hierarchy, assets, and more.</p>

                    <h5>Authentication</h5>
                    <p>All endpoints require user authentication. Make sure you're logged in before making API calls.</p>

                    <h5>Base URL</h5>
                    <div class="code-block">
                        <code>https://your-domain.com/api/</code>
                    </div>
                </div>
            </div>

            <!-- Available Methods -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-list me-2"></i>Available Methods</h3>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h5>Site Information</h5>
                            <ul>
                                <li><strong>getSiteInfo</strong> - Get site information</li>
                                <li><strong>getSiteHierarchy</strong> - Get site hierarchy</li>
                                <li><strong>getSiteHistory</strong> - Get site history</li>
                            </ul>
                        </div>
                        <div class="col-md-6">
                            <h5>Site Resources</h5>
                            <ul>
                                <li><strong>getSiteAssets</strong> - Get assets associated with site</li>
                                <li><strong>getSiteLocations</strong> - Get locations in site</li>
                                <li><strong>getSiteWorkOrders</strong> - Get work orders for site</li>
                                <li><strong>getSiteInventory</strong> - Get inventory for site</li>
                                <li><strong>getSitePersonnel</strong> - Get personnel assigned to site</li>
                                <li><strong>getSiteEquipment</strong> - Get equipment in site</li>
                                <li><strong>getSiteDocuments</strong> - Get documents associated with site</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Core Endpoints -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-cogs me-2"></i>Core API Endpoints</h3>
                </div>
                <div class="card-body">
                    <!-- Get Methods -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-get">GET</span> /api/mxapiste/methods</h5>
                        <p>Get list of all available MXAPISTE methods</p>
                        <div class="code-block">
                            <strong>Response:</strong><br>
                            <code>{
  "success": true,
  "methods": {...}
}</code>
                        </div>
                    </div>

                    <!-- Execute Method -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-post">POST</span> /api/mxapiste/{siteid}/execute/{method_name}</h5>
                        <p>Execute any MXAPISTE method on a specific site</p>
                        <div class="code-block">
                            <strong>Request Body:</strong><br>
                            <code>{
  "parameters": {
    "key": "value"
  }
}</code>
                        </div>
                    </div>

                    <!-- Bulk Operations -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-post">POST</span> /api/mxapiste/bulk/{method_name}</h5>
                        <p>Execute any MXAPISTE method on multiple sites (bulk operation)</p>
                        <div class="code-block">
                            <strong>Request Body:</strong><br>
                            <code>[
  {"siteid": "SITE1", "parameters": {...}},
  {"siteid": "SITE2", "parameters": {...}}
]</code>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Specific Method Endpoints -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-tools me-2"></i>Specific Method Endpoints</h3>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h5>Site Information</h5>
                            <ul class="list-unstyled">
                                <li><span class="method-badge method-get">GET</span> /api/site/{siteid}/info</li>
                                <li><span class="method-badge method-get">GET</span> /api/site/{siteid}/hierarchy</li>
                                <li><span class="method-badge method-get">GET</span> /api/site/{siteid}/history</li>
                            </ul>
                        </div>
                        <div class="col-md-6">
                            <h5>Site Resources</h5>
                            <ul class="list-unstyled">
                                <li><span class="method-badge method-get">GET</span> /api/site/{siteid}/assets</li>
                                <li><span class="method-badge method-get">GET</span> /api/site/{siteid}/locations</li>
                                <li><span class="method-badge method-get">GET</span> /api/site/{siteid}/workorders</li>
                                <li><span class="method-badge method-get">GET</span> /api/site/{siteid}/inventory</li>
                                <li><span class="method-badge method-get">GET</span> /api/site/{siteid}/personnel</li>
                                <li><span class="method-badge method-get">GET</span> /api/site/{siteid}/equipment</li>
                                <li><span class="method-badge method-get">GET</span> /api/site/{siteid}/documents</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Examples -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-code me-2"></i>Usage Examples</h3>
                </div>
                <div class="card-body">
                    <h5>1. Get Site Information</h5>
                    <div class="code-block">
                        <strong>GET</strong> /api/site/LCVKWT/info<br>
                        <strong>Response:</strong> {
  "success": true,
  "data": {
    "siteid": "LCVKWT",
    "description": "Kwajalein Site",
    "status": "ACTIVE",
    "type": "OPERATIONAL"
  }
}
                    </div>

                    <h5>2. Get Site Assets</h5>
                    <div class="code-block">
                        <strong>GET</strong> /api/site/LCVKWT/assets<br>
                        <strong>Response:</strong> {
  "success": true,
  "data": {
    "assets": [
      {
        "assetnum": "ASSET001",
        "description": "Main Generator",
        "status": "OPERATING"
      }
    ]
  }
}
                    </div>

                    <h5>3. Execute Custom Method</h5>
                    <div class="code-block">
                        <strong>POST</strong> /api/mxapiste/LCVKWT/execute/getSiteHierarchy<br>
                        <strong>Body:</strong> {
  "parameters": {
    "includeInactive": false
  }
}
                    </div>
                </div>
            </div>

            <!-- Navigation -->
            <div class="text-center mt-4 mb-4">
                <a href="/welcome" class="btn btn-primary btn-lg me-3">
                    <i class="fas fa-home me-2"></i>Back to Welcome
                </a>
                <a href="/api-docs/mxapiperuser" class="btn btn-outline-secondary btn-lg">
                    <i class="fas fa-users me-2"></i>User API Docs
                </a>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return html

# MXAPIPERUSER API Documentation Page
@app.route('/api-docs/mxapiperuser')
def mxapiperuser_documentation():
    """Complete API documentation for all MXAPIPERUSER endpoints"""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Complete MXAPIPERUSER API Documentation</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            body { background-color: #f8f9fa; }
            .api-header { background: linear-gradient(135deg, #28a745, #1e7e34); color: white; padding: 30px 0; }
            .endpoint-card { margin: 20px 0; border-left: 4px solid #28a745; }
            .method-badge { font-size: 12px; padding: 4px 8px; border-radius: 4px; }
            .method-get { background: #28a745; color: white; }
            .method-post { background: #007bff; color: white; }
            .code-block { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 15px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="api-header">
            <div class="container">
                <h1><i class="fas fa-users me-3"></i>Complete MXAPIPERUSER API Documentation</h1>
                <p class="lead">All available Maximo User API endpoints and methods</p>
            </div>
        </div>

        <div class="container mt-4">
            <!-- Overview Section -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-info-circle me-2"></i>API Overview</h3>
                </div>
                <div class="card-body">
                    <p>This API provides access to user-related information in Maximo, including available sites and user details.</p>

                    <h5>Authentication</h5>
                    <p>All endpoints require user authentication. Make sure you're logged in before making API calls.</p>

                    <h5>Base URL</h5>
                    <div class="code-block">
                        <code>https://your-domain.com/api/</code>
                    </div>
                </div>
            </div>

            <!-- Available Sites -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-list me-2"></i>Available Sites</h3>
                </div>
                <div class="card-body">
                    <h5>Endpoint</h5>
                    <div class="code-block">
                        <span class="method-badge method-get">GET</span> /api/mxapiperuser
                    </div>

                    <h5>Example Response</h5>
                    <div class="code-block">
                        <code>{
  "success": true,
  "sites": [
    {
      "siteid": "LCVKWT",
      "description": "Kwajalein Site",
      "status": "ACTIVE"
    },
    {
      "siteid": "BEDFORD",
      "description": "Bedford Site",
      "status": "ACTIVE"
    }
  ]
}</code>
                    </div>
                </div>
            </div>

            <!-- Site Information -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-info-circle me-2"></i>Site Information</h3>
                </div>
                <div class="card-body">
                    <h5>Endpoint</h5>
                    <div class="code-block">
                        <span class="method-badge method-get">GET</span> /api/site/{siteid}/info
                    </div>

                    <h5>Example Request</h5>
                    <div class="code-block">
                        <code>GET /api/site/LCVKWT/info</code>
                    </div>

                    <h5>Example Response</h5>
                    <div class="code-block">
                        <code>{
  "success": true,
  "data": {
    "siteid": "LCVKWT",
    "description": "Kwajalein Site",
    "status": "ACTIVE",
    "type": "OPERATIONAL",
    "address": "Kwajalein Atoll, Marshall Islands",
    "contact": "John Doe",
    "phone": "+1-555-0123",
    "email": "contact@lcvkw.com"
  }
}</code>
                    </div>
                </div>
            </div>

            <!-- Navigation -->
            <div class="text-center mt-4 mb-4">
                <a href="/welcome" class="btn btn-primary btn-lg me-3">
                    <i class="fas fa-home me-2"></i>Back to Welcome
                </a>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return html

# Site Access API Documentation Page
@app.route('/api-docs/mxapisite')
def mxapisite_documentation():
    """Complete API documentation for Site Access endpoints"""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Site Access API Documentation</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            body { background-color: #f8f9fa; }
            .api-header { background: linear-gradient(135deg, #17a2b8, #138496); color: white; padding: 30px 0; }
            .endpoint-card { margin: 20px 0; border-left: 4px solid #17a2b8; }
            .method-badge { font-size: 12px; padding: 4px 8px; border-radius: 4px; }
            .method-get { background: #28a745; color: white; }
            .method-post { background: #007bff; color: white; }
            .code-block { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 15px; margin: 10px 0; }
            .authallsites-badge { background: #ffc107; color: #212529; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
            .mobile-responsive { font-size: 0.9rem; }
            @media (max-width: 768px) {
                .container { padding: 0.5rem; }
                .code-block { font-size: 0.8rem; padding: 10px; }
                .method-badge { font-size: 10px; }
            }
        </style>
    </head>
    <body>
        <div class="api-header">
            <div class="container">
                <h1><i class="fas fa-building me-3"></i>Site Access API Documentation</h1>
                <p class="lead">Lightning-fast site authorization data with AUTHALLSITES logic</p>
                <div class="mt-3">
                    <span class="badge bg-success me-2">Lightning Fast</span>
                    <span class="badge bg-info me-2">5-Min Cache</span>
                    <span class="authallsites-badge me-2">AUTHALLSITES Logic</span>
                    <span class="badge bg-warning text-dark">Mobile Friendly</span>
                </div>
            </div>
        </div>

        <div class="container mt-4">
            <!-- Overview Section -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-info-circle me-2"></i>API Overview</h3>
                </div>
                <div class="card-body">
                    <p>The Site Access API provides comprehensive access to user site authorization data from Maximo,
                    including person information, user accounts, group memberships, and site authorizations with
                    intelligent AUTHALLSITES logic.</p>

                    <div class="row mt-3">
                        <div class="col-md-6">
                            <h5><i class="fas fa-rocket me-2"></i>Performance Features</h5>
                            <ul>
                                <li><strong>Lightning-fast retrieval</strong> - Optimized queries</li>
                                <li><strong>5-minute intelligent caching</strong> - Reduced system load</li>
                                <li><strong>30-minute ALL sites cache</strong> - Maximum performance</li>
                                <li><strong>Optimized timeouts</strong> - 3.05s/8s/15s</li>
                            </ul>
                        </div>
                        <div class="col-md-6">
                            <h5><i class="fas fa-key me-2"></i>AUTHALLSITES Logic</h5>
                            <ul>
                                <li><strong>AUTHALLSITES=1</strong> - Shows ALL sites in system</li>
                                <li><strong>AUTHALLSITES=0</strong> - Shows specific site authorizations</li>
                                <li><strong>Automatic detection</strong> - Smart logic per user</li>
                                <li><strong>Distinct sites only</strong> - No duplicates</li>
                            </ul>
                        </div>
                    </div>

                    <h5 class="mt-3">Authentication</h5>
                    <p>All endpoints require valid Maximo authentication via session cookies.</p>

                    <h5>Base URL</h5>
                    <div class="code-block">
                        <code>http://127.0.0.1:5008/api/site-access</code>
                    </div>
                </div>
            </div>

            <!-- Core Endpoints -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-cogs me-2"></i>Core API Endpoints</h3>
                </div>
                <div class="card-body">

                    <!-- Person Data -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-get">GET</span> /api/site-access/{personid}/person</h5>
                        <p>Retrieve person table information with capitalized field names</p>
                        <div class="code-block">
                            <strong>Example:</strong> <code>GET /api/site-access/{personid}/person</code><br>
                            <strong>Response:</strong><br>
                            <code>{
  "success": true,
  "data": {
    "Personid": "{personid}",
    "Firstname": "Tinu",
    "Lastname": "Thomas",
    "Displayname": "Tinu Thomas",
    "Status": "ACTIVE",
    "Locationorg": "USNAVY",
    "Locationsite": "NSGBA"
  }
}</code>
                        </div>
                    </div>

                    <!-- MaxUser Data -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-get">GET</span> /api/site-access/{personid}/maxuser</h5>
                        <p>Retrieve maxuser table information with capitalized field names</p>
                        <div class="code-block">
                            <strong>Example:</strong> <code>GET /api/site-access/{personid}/maxuser</code><br>
                            <strong>Response:</strong><br>
                            <code>{
  "success": true,
  "data": {
    "Userid": "{personid}",
    "Loginid": "tinu.thomas@vectrus.com",
    "Status": "ACTIVE",
    "Type": "MAXUSER",
    "Defsite": "NSGBA"
  }
}</code>
                        </div>
                    </div>

                    <!-- Groups Data -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-get">GET</span> /api/site-access/{personid}/groups</h5>
                        <p>Retrieve group memberships with AUTHALLSITES information</p>
                        <div class="code-block">
                            <strong>Example:</strong> <code>GET /api/site-access/{personid}/groups</code><br>
                            <strong>Response:</strong><br>
                            <code>{
  "success": true,
  "data": [
    {
      "Group Name": "MAXADMIN",
      "Description": "Maximo Administrators",
      "AUTHALLSITES": "1"
    },
    {
      "Group Name": "MAXEVERYONE",
      "Description": "All Maximo Users",
      "AUTHALLSITES": "0"
    }
  ]
}</code>
                        </div>
                    </div>

                    <!-- Sites Data -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-get">GET</span> /api/site-access/{personid}/sites</h5>
                        <p>Retrieve site authorizations with intelligent AUTHALLSITES logic</p>
                        <div class="code-block">
                            <strong>AUTHALLSITES=1 Example:</strong> <code>GET /api/site-access/{admin-personid}/sites</code><br>
                            <strong>Response (ALL sites in system):</strong><br>
                            <code>{
  "success": true,
  "data": [
    {"Site ID": "BBOS", "Organization": "USNAVY"},
    {"Site ID": "CJORD", "Organization": "USARMY"},
    {"Site ID": "IKWAJ", "Organization": "USARMY"},
    {"Site ID": "LCVKWT", "Organization": "USARMY"},
    {"Site ID": "NSGBA", "Organization": "USNAVY"},
    {"Site ID": "THULE", "Organization": "USAF"}
  ]
}</code>
                        </div>
                        <div class="code-block">
                            <strong>AUTHALLSITES=0 Example:</strong> <code>GET /api/site-access/{user-personid}/sites</code><br>
                            <strong>Response (specific sites only):</strong><br>
                            <code>{
  "success": true,
  "data": [
    {"Site ID": "NSGBA", "Organization": "USNAVY"},
    {"Site ID": "LCVKWT", "Organization": "USARMY"},
    {"Site ID": "LGCAP", "Organization": "USARMY"},
    {"Site ID": "IKWAJ", "Organization": "USARMY"}
  ]
}</code>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Cache Management -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-database me-2"></i>Cache Management</h3>
                </div>
                <div class="card-body">

                    <!-- Clear Cache -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-post">POST</span> /api/site-access/cache/clear</h5>
                        <p>Clear all caches (site access + all sites cache)</p>
                        <div class="code-block">
                            <strong>Response:</strong><br>
                            <code>{
  "success": true,
  "message": "All caches cleared successfully"
}</code>
                        </div>
                    </div>

                    <!-- Cache Stats -->
                    <div class="mb-4">
                        <h5><span class="method-badge method-get">GET</span> /api/site-access/cache/stats</h5>
                        <p>Retrieve cache performance statistics</p>
                        <div class="code-block">
                            <strong>Response:</strong><br>
                            <code>{
  "success": true,
  "data": {
    "cached_entries": 5,
    "cache_duration": 300,
    "all_sites_cached": true,
    "all_sites_fresh": true,
    "all_sites_count": 16,
    "all_sites_cache_duration": 1800
  }
}</code>
                        </div>
                    </div>
                </div>
            </div>

            <!-- AUTHALLSITES Logic -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-key me-2"></i>AUTHALLSITES Logic Explained</h3>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h5><span class="authallsites-badge">AUTHALLSITES=1</span> Users</h5>
                            <ul>
                                <li><strong>Access Level:</strong> ALL sites in system</li>
                                <li><strong>Data Source:</strong> Entire mxapisite endpoint (10,000 records)</li>
                                <li><strong>Cache Duration:</strong> 30 minutes (aggressive)</li>
                                <li><strong>Performance:</strong> Lightning-fast after first load</li>
                                <li><strong>Example Users:</strong> Admin users with AUTHALLSITES=1</li>
                            </ul>
                        </div>
                        <div class="col-md-6">
                            <h5><span class="badge bg-secondary">AUTHALLSITES=0</span> Users</h5>
                            <ul>
                                <li><strong>Access Level:</strong> Specific authorized sites only</li>
                                <li><strong>Data Source:</strong> User's group site authorizations</li>
                                <li><strong>Cache Duration:</strong> 5 minutes (standard)</li>
                                <li><strong>Performance:</strong> Fast with intelligent caching</li>
                                <li><strong>Example Users:</strong> Standard users with AUTHALLSITES=0</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Usage Examples -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-code me-2"></i>Usage Examples</h3>
                </div>
                <div class="card-body">

                    <h5>JavaScript/Fetch</h5>
                    <div class="code-block">
                        <code>// Get person data
fetch('/api/site-access/{personid}/person')
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log('Person:', data.data.Displayname);
    }
  });

// Get sites with AUTHALLSITES logic
fetch('/api/site-access/{personid}/sites')
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log(`Found ${data.data.length} sites`);
      data.data.forEach(site => {
        console.log(`${site['Site ID']} (${site['Organization']})`);
      });
    }
  });</code>
                    </div>

                    <h5>cURL</h5>
                    <div class="code-block">
                        <code># Get group memberships
curl -X GET "http://127.0.0.1:5008/api/site-access/{personid}/groups" \\
  -H "Accept: application/json" \\
  --cookie-jar cookies.txt

# Clear cache
curl -X POST "http://127.0.0.1:5008/api/site-access/cache/clear" \\
  -H "Accept: application/json" \\
  --cookie-jar cookies.txt</code>
                    </div>
                </div>
            </div>

            <!-- Integration -->
            <div class="card endpoint-card">
                <div class="card-header">
                    <h3><i class="fas fa-puzzle-piece me-2"></i>Integration</h3>
                </div>
                <div class="card-body">
                    <h5>Enhanced Profile Page</h5>
                    <p>The Site Access API is integrated into the Enhanced Profile page with:</p>
                    <ul>
                        <li><strong>4-tab interface:</strong> Person | User Account | Group Memberships | Site Authorizations</li>
                        <li><strong>Dynamic loading:</strong> Data loads on-demand when tabs are clicked</li>
                        <li><strong>Mobile-responsive:</strong> Optimized for all devices</li>
                        <li><strong>Visual indicators:</strong> Green "YES (All Sites)" for AUTHALLSITES=1 users</li>
                    </ul>

                    <div class="code-block">
                        <strong>Access URL:</strong> <code>http://127.0.0.1:5008/enhanced-profile</code>
                    </div>
                </div>
            </div>

            <!-- Navigation -->
            <div class="text-center mt-4 mb-4">
                <a href="/welcome" class="btn btn-primary btn-lg me-3">
                    <i class="fas fa-home me-2"></i>Back to Welcome
                </a>
                <a href="/enhanced-profile" class="btn btn-success btn-lg me-3">
                    <i class="fas fa-user me-2"></i>Enhanced Profile
                </a>
                <a href="/api-docs" class="btn btn-outline-secondary btn-lg">
                    <i class="fas fa-code me-2"></i>Work Order API
                </a>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return html

@app.route('/api/mxapiperuser', methods=['GET'])
def get_sites():
    """Get sites for the current user using the mxapisite endpoint."""
    if not token_manager.is_logged_in():
        return jsonify({"error": "Not authenticated"}), 401

    url = f"{DEFAULT_MAXIMO_URL}/api/os/mxapisite"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "apikey": "dj9sia0tu2s0sktv3oq815amtv06ior0ahlsn70o"
    }

    # SQL query to get sites for current user
    sql_query = """
    SELECT s.*, m.description as group_description
    FROM SITEAUTH s
    JOIN maxgroup m ON s.groupname = m.groupname
    WHERE s.groupname IN (
        SELECT groupname
        FROM maxgroup
        WHERE EXISTS (
            SELECT 1
            FROM groupuser
            WHERE userid = '{current_user}'
            AND groupuser.groupname = maxgroup.groupname
        )
    )
    """

    try:
        response = requests.get(url, headers=headers, params={"_sql": sql_query})
        response.raise_for_status()

        # Parse the RDF response
        data = response.json()
        sites = []

        # Extract site information from the RDF response
        if "rdf:resource" in data:
            for resource in data["rdf:resource"]:
                site_url = resource.get("rdf:resource", "")
                if site_url:
                    # Extract site ID from URL
                    site_id = site_url.split("/")[-1]
                    sites.append({
                        "site_id": site_id,
                        "url": site_url
                    })

        return jsonify({
            "status": "success",
            "sites": sites,
            "count": len(sites)
        })
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching sites: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/mxapisite', methods=['GET'])
def get_sites_for_user():
    """Get sites for the current user using the mxapisite endpoint."""
    if not token_manager.is_logged_in():
        return jsonify({"error": "Not authenticated"}), 401

    url = f"{DEFAULT_MAXIMO_URL}/api/os/mxapisite"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "apikey": "dj9sia0tu2s0sktv3oq815amtv06ior0ahlsn70o"
    }

    # SQL query to get sites for current user
    sql_query = """
    SELECT s.*, m.description as group_description
    FROM SITEAUTH s
    JOIN maxgroup m ON s.groupname = m.groupname
    WHERE s.groupname IN (
        SELECT groupname
        FROM maxgroup
        WHERE EXISTS (
            SELECT 1
            FROM groupuser
            WHERE userid = '{current_user}'
            AND groupuser.groupname = maxgroup.groupname
        )
    )
    """

    try:
        response = requests.get(url, headers=headers, params={"_sql": sql_query})
        response.raise_for_status()

        # Parse the RDF response
        data = response.json()
        sites = []

        # Extract site information from the RDF response
        if "rdf:resource" in data:
            for resource in data["rdf:resource"]:
                site_url = resource.get("rdf:resource", "")
                if site_url:
                    # Extract site ID from URL
                    site_id = site_url.split("/")[-1]
                    sites.append({
                        "site_id": site_id,
                        "url": site_url
                    })

        return jsonify({
            "status": "success",
            "sites": sites,
            "count": len(sites)
        })
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching sites: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# Site Access API Routes
@app.route('/api/site-access/<person_id>/person', methods=['GET'])
def get_person_data(person_id):
    """Get person table data for the specified person ID."""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        data = SiteAccessService.get_person_data(person_id)
        if data:
            return jsonify({'success': True, 'data': data})
        else:
            return jsonify({'success': False, 'error': 'No person data found'})
    except Exception as e:
        logger.error(f"Error getting person data for {person_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/site-access/<person_id>/maxuser', methods=['GET'])
def get_maxuser_data(person_id):
    """Get maxuser table data for the specified person ID."""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        data = SiteAccessService.get_maxuser_data(person_id)
        if data:
            return jsonify({'success': True, 'data': data})
        else:
            return jsonify({'success': False, 'error': 'No maxuser data found'})
    except Exception as e:
        logger.error(f"Error getting maxuser data for {person_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/site-access/<person_id>/groups', methods=['GET'])
def get_groups_data(person_id):
    """Get group memberships data for the specified person ID."""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        data = SiteAccessService.get_groups_data(person_id)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"Error getting groups data for {person_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/site-access/<person_id>/sites', methods=['GET'])
def get_sites_data(person_id):
    """Get site authorizations data for the specified person ID."""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        data = SiteAccessService.get_sites_data(person_id)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"Error getting sites data for {person_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/site-access/cache/clear', methods=['POST'])
def clear_site_access_cache():
    """Clear the site access cache."""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        SiteAccessService.clear_cache()
        return jsonify({'success': True, 'message': 'Cache cleared successfully'})
    except Exception as e:
        logger.error(f"Error clearing site access cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/site-access/cache/stats', methods=['GET'])
def get_site_access_cache_stats():
    """Get site access cache statistics."""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        stats = SiteAccessService.get_cache_stats()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        logger.error(f"Error getting site access cache stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Task Planned Materials API Endpoints
@app.route('/api/task/<task_wonum>/planned-materials', methods=['GET'])
def get_task_planned_materials(task_wonum):
    """Get planned materials for a specific task."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        # Get task status for logging purposes (materials now available for all statuses)
        task_status = request.args.get('status', '')
        logger.info(f"📦 MATERIALS API: Loading materials for task {task_wonum} with status {task_status}")

        # Get user's site ID
        user_site_id = getattr(token_manager, 'user_site_id', 'UNKNOWN')
        if user_site_id == 'UNKNOWN':
            # Try to get from profile service
            try:
                profile_data = profile_service.get_user_profile()
                user_site_id = profile_data.get('defaultSite', 'UNKNOWN')
            except:
                user_site_id = 'UNKNOWN'

        logger.info(f"📦 MATERIALS API: Fetching materials for task {task_wonum}, site {user_site_id}")

        # Fetch planned materials
        materials, metadata = task_materials_service.get_task_planned_materials(task_wonum, user_site_id)

        return jsonify({
            'success': True,
            'materials': materials,
            'metadata': metadata,
            'show_materials': True,
            'task_wonum': task_wonum,
            'site_id': user_site_id
        })

    except Exception as e:
        logger.error(f"Error fetching planned materials for task {task_wonum}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'show_materials': False
        })

@app.route('/api/task/planned-materials/cache/clear', methods=['POST'])
def clear_materials_cache():
    """Clear the planned materials cache."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        task_materials_service.clear_cache()
        return jsonify({'success': True, 'message': 'Materials cache cleared'})

    except Exception as e:
        logger.error(f"Error clearing materials cache: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/task/planned-materials/cache/stats', methods=['GET'])
def get_materials_cache_stats():
    """Get planned materials cache statistics."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        stats = task_materials_service.get_cache_stats()
        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# Task Labor API Endpoints (following exact same pattern as materials)
@app.route('/api/task/<task_wonum>/labor-records', methods=['GET'])
def get_task_labor_records(task_wonum):
    """Get labor records for a specific task using mxapiwodetail/labtrans."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        # Get task status for access control
        task_status = request.args.get('status', '')
        logger.info(f"👷 LABOR API: Loading labor records for task {task_wonum} with status {task_status}")

        # Get user's site ID
        user_site_id = getattr(token_manager, 'user_site_id', 'UNKNOWN')

        # Fallback to session if not available in token manager
        if not user_site_id or user_site_id == 'UNKNOWN':
            try:
                user_site_id = session.get('user_site_id', 'UNKNOWN')
            except:
                user_site_id = 'UNKNOWN'

        logger.info(f"👷 LABOR API: Fetching labor records for task {task_wonum}, site {user_site_id}")

        # Fetch labor records
        result = task_labor_service.get_task_labor(task_wonum, user_site_id, task_status)

        return jsonify(result)

    except Exception as e:
        logger.error(f"👷 LABOR API: Error getting labor records for task {task_wonum}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'show_labor': False
        })

@app.route('/api/task/labor-records/cache/clear', methods=['POST'])
def clear_labor_records_cache():
    """Clear the labor records cache."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        result = task_labor_service.clear_cache()
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error clearing labor cache: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/task/labor-records/cache/stats', methods=['GET'])
def get_labor_records_cache_stats():
    """Get labor records cache statistics."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        stats = task_labor_service.get_cache_stats()
        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        logger.error(f"Error getting labor cache stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


# Inventory Search API Endpoints
@app.route('/api/test-inventory-fields', methods=['GET'])
def test_inventory_fields():
    """Test endpoint to investigate available fields in MXAPIINVENTORY."""
    try:
        logger.info("🔧 TESTING: Investigating MXAPIINVENTORY fields")

        # Test with minimal fields first
        base_url = token_manager.base_url
        inventory_url = f"{base_url}/oslc/os/mxapiinventory"

        # Test 1: Test the fields from the user's original requirements
        # Based on user requirements: ITEMNUM, DESCRIPTION, ISSUEUNIT, ORDERUNIT, CURBALTOTAL, AVBLBALANCE, etc.
        test_fields = [
            "itemnum", "siteid", "location",
            "issueunit", "orderunit", "curbaltotal", "avblbalance",
            "status", "abc", "vendor", "manufacturer", "modelnum",
            "itemtype", "rotating", "conditioncode", "itemsetid"
        ]

        params = {
            "oslc.select": ",".join(test_fields),
            "oslc.where": 'siteid="LCVKWT"',
            "oslc.pageSize": "1",
            "lean": "1"
        }

        response = token_manager.session.get(
            inventory_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"}
        )

        result = {
            'test': 'user_required_fields',
            'fields_tested': test_fields,
            'status_code': response.status_code,
            'success': response.status_code == 200
        }

        if response.status_code == 200:
            try:
                data = response.json()
                result['response_keys'] = list(data.keys())
                items = data.get('member', [])
                result['items_found'] = len(items)
                if items:
                    result['available_fields'] = list(items[0].keys())
                    result['sample_item'] = items[0]
            except Exception as e:
                result['json_error'] = str(e)
                result['raw_response'] = response.text[:200]
        else:
            result['error_response'] = response.text[:200]

        return jsonify(result)

    except Exception as e:
        logger.error(f"🔧 TESTING: Error investigating fields: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Field investigation failed: {str(e)}'
        }), 500

@app.route('/api/test-item-fields', methods=['GET'])
def test_item_fields():
    """Test endpoint to investigate available fields in MXAPIITEM."""
    try:
        logger.info("🔧 TESTING: Investigating MXAPIITEM fields")

        # Test with item fields for description
        base_url = token_manager.base_url
        item_url = f"{base_url}/oslc/os/mxapiitem"

        # Test fields that might be in MXAPIITEM
        test_fields = [
            "itemnum", "description", "status", "itemtype",
            "issueunit", "orderunit", "manufacturer", "vendor",
            "modelnum", "itemsetid"
        ]

        params = {
            "oslc.select": ",".join(test_fields),
            "oslc.where": 'status="ACTIVE"',
            "oslc.pageSize": "1",
            "lean": "1"
        }

        response = token_manager.session.get(
            item_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"}
        )

        result = {
            'test': 'mxapiitem_fields',
            'fields_tested': test_fields,
            'status_code': response.status_code,
            'success': response.status_code == 200
        }

        if response.status_code == 200:
            try:
                data = response.json()
                result['response_keys'] = list(data.keys())
                items = data.get('member', [])
                result['items_found'] = len(items)
                if items:
                    result['available_fields'] = list(items[0].keys())
                    result['sample_item'] = items[0]
            except Exception as e:
                result['json_error'] = str(e)
                result['raw_response'] = response.text[:200]
        else:
            result['error_response'] = response.text[:200]

        return jsonify(result)

    except Exception as e:
        logger.error(f"🔧 TESTING: Error investigating MXAPIITEM fields: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'MXAPIITEM field investigation failed: {str(e)}'
        }), 500

@app.route('/api/test-specific-item', methods=['GET'])
def test_specific_item():
    """Test endpoint to check if a specific item exists in MXAPIITEM with any status."""
    try:
        item_num = request.args.get('itemnum', '6210-60-V00-0181')
        logger.info(f"🔧 TESTING: Checking if item {item_num} exists in MXAPIITEM")

        base_url = token_manager.base_url
        item_url = f"{base_url}/oslc/os/mxapiitem"

        # Test without status filter to see if item exists at all
        test_fields = ["itemnum", "description", "status", "itemtype", "issueunit", "orderunit"]

        params = {
            "oslc.select": ",".join(test_fields),
            "oslc.where": f'itemnum="{item_num}"',  # No status filter
            "oslc.pageSize": "5",
            "lean": "1"
        }

        response = token_manager.session.get(
            item_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"}
        )

        result = {
            'test': 'specific_item_check',
            'item_searched': item_num,
            'status_code': response.status_code,
            'success': response.status_code == 200
        }

        if response.status_code == 200:
            try:
                data = response.json()
                items = data.get('member', [])
                result['items_found'] = len(items)
                result['items'] = items

                if items:
                    result['message'] = f'Item {item_num} EXISTS in MXAPIITEM'
                    for item in items:
                        logger.info(f"🔧 TESTING: Found item {item.get('itemnum')} with status {item.get('status')}")
                else:
                    result['message'] = f'Item {item_num} does NOT exist in MXAPIITEM'

            except Exception as e:
                result['json_error'] = str(e)
                result['raw_response'] = response.text[:200]
        else:
            result['error_response'] = response.text[:200]

        return jsonify(result)

    except Exception as e:
        logger.error(f"🔧 TESTING: Error checking specific item: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Specific item check failed: {str(e)}'
        }), 500

@app.route('/api/inventory/search', methods=['GET'])
def search_inventory_items():
    """Search inventory items by item number or description."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        # Get search parameters
        search_term = request.args.get('q', '').strip()
        site_id = request.args.get('siteid', '').strip()
        limit = int(request.args.get('limit', 20))

        if not search_term:
            return jsonify({
                'success': False,
                'error': 'Search term is required'
            })

        if not site_id:
            return jsonify({
                'success': False,
                'error': 'Site ID is required'
            })

        logger.info(f"🔍 INVENTORY API: Searching for '{search_term}' in site {site_id}")

        # Perform inventory search
        items, metadata = inventory_search_service.search_inventory_items(search_term, site_id, limit)

        return jsonify({
            'success': True,
            'items': items,
            'metadata': metadata,
            'search_term': search_term,
            'site_id': site_id,
            'count': len(items)
        })

    except Exception as e:
        logger.error(f"Error searching inventory: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/inventory/item-details/<itemnum>', methods=['GET'])
def get_item_details(itemnum):
    """Get detailed item information from MXAPIITEM."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        if not itemnum:
            return jsonify({
                'success': False,
                'error': 'Item number is required'
            })

        logger.info(f"🔍 INVENTORY API: Getting details for item {itemnum}")

        # Get item details
        item_details = inventory_search_service._get_item_details(itemnum)

        if not item_details:
            return jsonify({
                'success': False,
                'error': f'Item {itemnum} not found'
            })

        return jsonify({
            'success': True,
            'item': item_details,
            'itemnum': itemnum
        })

    except Exception as e:
        logger.error(f"Error getting item details for {itemnum}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/inventory/cache/clear', methods=['POST'])
def clear_inventory_cache():
    """Clear the inventory search cache."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        inventory_search_service.clear_cache()
        return jsonify({'success': True, 'message': 'Inventory search cache cleared'})

    except Exception as e:
        logger.error(f"Error clearing inventory cache: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/inventory/cache/stats', methods=['GET'])
def get_inventory_cache_stats():
    """Get inventory search cache statistics."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        stats = inventory_search_service.get_cache_stats()
        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        logger.error(f"Error getting inventory cache stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


# Labor Search API Endpoints
@app.route('/api/labor/search', methods=['GET'])
def search_labor_codes():
    """Search labor codes by labor code or description."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        # Get search parameters
        search_term = request.args.get('search_term', '').strip()
        site_id = request.args.get('site_id', '').strip()
        limit = int(request.args.get('limit', 20))
        craft = request.args.get('craft', '').strip() or None
        skill_level = request.args.get('skill_level', '').strip() or None

        # Validate required parameters
        if not search_term:
            return jsonify({
                'success': False,
                'error': 'Search term is required'
            })

        if not site_id:
            return jsonify({
                'success': False,
                'error': 'Site ID is required'
            })

        logger.info(f"🔍 LABOR API: Searching for '{search_term}' in site {site_id}")

        # Perform labor search
        labor_codes, metadata = labor_search_service.search_labor(
            search_term, site_id, limit, craft, skill_level
        )

        return jsonify({
            'success': True,
            'labor_codes': labor_codes,
            'metadata': metadata,
            'search_term': search_term,
            'site_id': site_id
        })

    except Exception as e:
        logger.error(f"Error in labor search: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/labor/cache/clear', methods=['POST'])
def clear_labor_cache():
    """Clear the labor search cache."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        result = labor_search_service.clear_cache()
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error clearing labor cache: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/labor/cache/stats', methods=['GET'])
def get_labor_cache_stats():
    """Get labor search cache statistics."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        stats = labor_search_service.get_cache_stats()
        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        logger.error(f"Error getting labor cache stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# Labor Request API Endpoints
@app.route('/api/task/<task_wonum>/add-labor', methods=['POST'])
def add_labor_to_task(task_wonum):
    """Add labor to a specific task."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})

        # Extract required parameters with proper null checks
        laborcode = (data.get('laborcode') or '').strip()
        regularhrs = data.get('regularhrs')  # Changed from laborhrs to regularhrs
        siteid = (data.get('siteid') or '').strip()
        taskid = data.get('taskid')
        parent_wonum = (data.get('parent_wonum') or '').strip()

        # Extract optional parameters with proper null checks
        craft = (data.get('craft') or '').strip() or None
        startdate = (data.get('startdate') or '').strip() or None
        starttime = (data.get('starttime') or '').strip() or None
        finishdate = (data.get('finishdate') or '').strip() or None
        finishtime = (data.get('finishtime') or '').strip() or None
        payrate = data.get('payrate') or None
        notes = (data.get('notes') or '').strip() or None
        transtype = (data.get('transtype') or '').strip() or None

        # Validate required parameters
        if not all([laborcode, regularhrs, siteid, taskid, parent_wonum]):
            missing = [param for param, value in [
                ('laborcode', laborcode), ('regularhrs', regularhrs), ('siteid', siteid),
                ('taskid', taskid), ('parent_wonum', parent_wonum)
            ] if not value]
            return jsonify({
                'success': False,
                'error': f'Missing required parameters: {missing}'
            })

        logger.info(f"🔧 LABOR API: Adding labor {laborcode} ({regularhrs}h) to task {task_wonum}")

        # Add labor to task
        result = labor_request_service.add_labor_request(
            wonum=parent_wonum,
            siteid=siteid,
            laborcode=laborcode,
            regularhrs=regularhrs,  # Changed from laborhrs to regularhrs
            taskid=taskid,
            craft=craft,
            startdate=startdate,
            starttime=starttime,
            finishdate=finishdate,
            finishtime=finishtime,
            payrate=payrate,
            notes=notes,
            task_wonum=task_wonum,
            transtype=transtype
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error adding labor to task {task_wonum}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/labor/performance-stats', methods=['GET'])
def get_labor_performance_stats():
    """Get labor request performance statistics."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        stats = labor_request_service.get_performance_stats()
        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        logger.error(f"Error getting labor performance stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

def extract_labor_records_from_data(raw_labor_data, source_type):
    """Extract labor records from various data structures"""
    logger.info(f"👷 LABOR EXTRACT: Processing {source_type} data type: {type(raw_labor_data)}")

    if isinstance(raw_labor_data, list):
        # Multiple labor records returned as list
        logger.info(f"👷 LABOR EXTRACT: Found {len(raw_labor_data)} labor records (list)")
        return raw_labor_data
    elif isinstance(raw_labor_data, dict):
        # Check if this is a collection structure or single record
        if 'member' in raw_labor_data:
            # This is a collection structure with member array
            member_data = raw_labor_data['member']
            if isinstance(member_data, list):
                logger.info(f"👷 LABOR EXTRACT: Found {len(member_data)} labor records (dict with member list)")
                return member_data
            else:
                logger.info(f"👷 LABOR EXTRACT: Found 1 labor record (dict with member single)")
                return [member_data]
        elif 'rdfs:member' in raw_labor_data:
            # This is a collection structure with rdfs:member array
            member_data = raw_labor_data['rdfs:member']
            if isinstance(member_data, list):
                logger.info(f"👷 LABOR EXTRACT: Found {len(member_data)} labor records (dict with rdfs:member list)")
                return member_data
            else:
                logger.info(f"👷 LABOR EXTRACT: Found 1 labor record (dict with rdfs:member single)")
                return [member_data]
        else:
            # Single labor record returned as dict
            logger.info(f"👷 LABOR EXTRACT: Found 1 labor record (single dict)")
            return [raw_labor_data]
    else:
        logger.error(f"❌ LABOR EXTRACT: Unexpected data type: {type(raw_labor_data)}")
        return []

def fetch_labor_from_collection_ref(collection_ref_url):
    """
    Fetch labor records from a collection reference URL (same pattern as materials).

    Args:
        collection_ref_url: The collection reference URL to fetch from

    Returns:
        List of labor dictionaries
    """
    try:
        logger.info(f"👷 LABOR API: Fetching from collection ref: {collection_ref_url}")

        response = token_manager.session.get(
            collection_ref_url,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"},
            allow_redirects=True
        )

        logger.info(f"👷 LABOR API: Collection ref response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            logger.info(f"👷 LABOR API: Collection ref data type: {type(data)}")
            logger.info(f"👷 LABOR API: Collection ref data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

            # Extract labor records from the collection response
            if isinstance(data, dict):
                labor_records = data.get('member', data.get('rdfs:member', []))
                logger.info(f"👷 LABOR API: Found {len(labor_records)} labor records in collection ref")

                # Process each labor record to handle localref if needed
                processed_records = []
                for i, labor_data in enumerate(labor_records):
                    logger.info(f"👷 LABOR API: Raw labor {i+1} data: {labor_data}")
                    if isinstance(labor_data, dict):
                        logger.info(f"👷 LABOR API: Labor {i+1} keys: {list(labor_data.keys())}")

                        # Check if this is just a localref - if so, fetch the actual labor data
                        if 'localref' in labor_data and len(labor_data.keys()) == 1:
                            localref = labor_data['localref']
                            logger.info(f"👷 LABOR API: Labor {i+1} is a localref, fetching actual data from: {localref}")

                            # Fix hostname in localref if needed
                            base_url = getattr(token_manager, 'base_url', '')
                            if base_url and 'vectrus-mea.manage.v2x.maximotest.gov2x.com' in localref:
                                import re
                                hostname_match = re.search(r'https://([^/]+)', base_url)
                                if hostname_match:
                                    correct_hostname = hostname_match.group(1)
                                    localref = re.sub(r'https://[^/]+', f'https://{correct_hostname}', localref)
                                    logger.info(f"👷 LABOR API: Fixed localref URL: {localref}")

                            # Fetch the actual labor data
                            try:
                                localref_response = token_manager.session.get(
                                    localref,
                                    timeout=(5.0, 30),
                                    headers={"Accept": "application/json"},
                                    allow_redirects=True
                                )

                                if localref_response.status_code == 200:
                                    actual_labor_data = localref_response.json()
                                    logger.info(f"👷 LABOR API: Fetched actual labor data: {actual_labor_data}")
                                    labor_data = actual_labor_data
                                else:
                                    logger.warning(f"👷 LABOR API: Failed to fetch localref data, status: {localref_response.status_code}")
                                    continue
                            except Exception as e:
                                logger.warning(f"👷 LABOR API: Error fetching localref data: {str(e)}")
                                continue

                        processed_records.append(labor_data)

                return processed_records
            else:
                logger.warning(f"👷 LABOR API: Collection ref response is not a dict")
                return []
        else:
            logger.error(f"👷 LABOR API: Collection ref failed with status {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"👷 LABOR API: Error fetching from collection ref: {str(e)}")
        return []

# Debug endpoint to investigate labtrans methods
@app.route('/api/debug/labtrans-methods/<task_wonum>')
def debug_labtrans_methods(task_wonum):
    """Debug endpoint to list all available labtrans methods and collections"""
    try:
        logger.info(f"🔍 DEBUG: Investigating labtrans methods for task {task_wonum}")

        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'error': 'Authentication required'})

        # Build API URL
        base_url = getattr(token_manager, 'base_url', '')
        api_url = f"{base_url}/oslc/os/mxapiwodetail"

        # Query for the specific task work order to see ALL available fields and collections
        params = {
            "oslc.select": "*",
            "oslc.where": f'wonum="{task_wonum}"',
            "oslc.pageSize": "1",
            "lean": "1"
        }

        logger.info(f"🔍 DEBUG: Querying {api_url} for task {task_wonum}")
        logger.info(f"🔍 DEBUG: Params: {params}")

        response = token_manager.session.get(
            api_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"},
            allow_redirects=True
        )

        logger.info(f"🔍 DEBUG: Response status: {response.status_code}")

        if response.status_code == 200:
            try:
                data = response.json()
                logger.info(f"🔍 DEBUG: Response data keys: {list(data.keys()) if data else 'None'}")
            except Exception as e:
                logger.error(f"🔍 DEBUG: Failed to parse JSON response: {e}")
                logger.error(f"🔍 DEBUG: Raw response text: {response.text[:1000]}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to parse JSON: {e}',
                    'raw_response': response.text[:1000],
                    'response_headers': dict(response.headers)
                })

            if 'member' in data and data['member']:
                wo_record = data['member'][0]
                all_keys = list(wo_record.keys())

                # Find all labtrans-related keys
                labtrans_keys = [key for key in all_keys if 'labtrans' in key.lower()]
                collection_keys = [key for key in all_keys if 'collectionref' in key.lower()]

                logger.info(f"🔍 DEBUG: ALL KEYS ({len(all_keys)}): {all_keys}")
                logger.info(f"🔍 DEBUG: LABTRANS KEYS ({len(labtrans_keys)}): {labtrans_keys}")
                logger.info(f"🔍 DEBUG: COLLECTION KEYS ({len(collection_keys)}): {collection_keys}")

                # Check if labtrans field exists and what it contains
                if 'labtrans' in wo_record:
                    labtrans_data = wo_record['labtrans']
                    logger.info(f"🔍 DEBUG: labtrans field type: {type(labtrans_data)}")
                    logger.info(f"🔍 DEBUG: labtrans field content: {labtrans_data}")

                # Check labtrans collection reference
                if 'labtrans_collectionref' in wo_record:
                    collection_url = wo_record['labtrans_collectionref']
                    logger.info(f"🔍 DEBUG: labtrans_collectionref: {collection_url}")

                return jsonify({
                    'success': True,
                    'task_wonum': task_wonum,
                    'all_keys_count': len(all_keys),
                    'all_keys': all_keys,
                    'labtrans_keys': labtrans_keys,
                    'collection_keys': collection_keys,
                    'has_labtrans_field': 'labtrans' in wo_record,
                    'has_labtrans_collection': 'labtrans_collectionref' in wo_record,
                    'labtrans_collection_url': wo_record.get('labtrans_collectionref', 'Not found'),
                    'labtrans_data_type': str(type(wo_record.get('labtrans', 'Not found'))),
                    'labtrans_data': wo_record.get('labtrans', 'Not found')
                })
            else:
                return jsonify({'success': False, 'error': 'No work order data found'})
        else:
            return jsonify({'success': False, 'error': f'API request failed: {response.status_code}'})

    except Exception as e:
        logger.error(f"❌ DEBUG: Error investigating labtrans methods: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# Task Labor Loading API Endpoint (Reverted to working original approach)
@app.route('/api/task/<task_wonum>/labor', methods=['GET'])
def get_task_labor(task_wonum):
    """Get labor assignments for a specific task."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        # Get task status for logging purposes
        task_status = request.args.get('status', '')
        logger.info(f"👷 LABOR API: Loading labor for task {task_wonum} with status {task_status}")

        # Get user's site ID
        user_site_id = getattr(token_manager, 'user_site_id', 'UNKNOWN')
        if user_site_id == 'UNKNOWN':
            # Try to get from profile service
            try:
                user_profile = enhanced_profile_service.get_user_profile()
                if user_profile and user_profile.get('defaultSite'):
                    user_site_id = user_profile['defaultSite']
            except:
                pass

        # Use MXAPIWODETAIL to get labor data using collection reference approach (same as materials)
        base_url = getattr(token_manager, 'base_url', '')
        api_url = f"{base_url}/oslc/os/mxapiwodetail"

        # First, get the work order to find the labtrans_collectionref
        oslc_filter = f'wonum="{task_wonum}"'
        if user_site_id and user_site_id != "UNKNOWN":
            oslc_filter += f' and siteid="{user_site_id}"'

        params = {
            "oslc.select": "wonum,siteid,labtrans_collectionref",  # Get the collection reference
            "oslc.where": oslc_filter,
            "oslc.pageSize": "1",
            "lean": "1"
        }

        logger.info(f"👷 LABOR API: Querying {api_url} for task {task_wonum}")
        logger.info(f"👷 LABOR API: Params: {params}")

        response = token_manager.session.get(
            api_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"},
            allow_redirects=True
        )

        logger.info(f"👷 LABOR API: Response status: {response.status_code}")

        if response.status_code == 200:
            try:
                data = response.json()
                logger.info(f"👷 LABOR API: Response data keys: {list(data.keys()) if data else 'None'}")

                # Extract the labtrans_collectionref from the work order (same pattern as materials)
                labor_records = []

                if isinstance(data, dict):
                    work_orders = data.get('member', data.get('rdfs:member', []))
                    logger.info(f"👷 LABOR API: Found {len(work_orders)} work orders in response")

                    if work_orders and len(work_orders) > 0:
                        work_order = work_orders[0]
                        logger.info(f"👷 LABOR API: Work order wonum: {work_order.get('wonum', 'UNKNOWN')}")

                        # Get the labtrans collection reference
                        collection_ref = work_order.get('labtrans_collectionref')
                        if collection_ref:
                            logger.info(f"👷 LABOR API: Found labtrans_collectionref: {collection_ref}")

                            # Fix the hostname in the collection reference URL if needed
                            # Sometimes Maximo returns collection refs with different hostnames
                            base_url = getattr(token_manager, 'base_url', '')
                            if base_url and 'vectrus-mea.manage.v2x.maximotest.gov2x.com' in collection_ref:
                                # Extract the correct hostname from our base_url
                                import re
                                hostname_match = re.search(r'https://([^/]+)', base_url)
                                if hostname_match:
                                    correct_hostname = hostname_match.group(1)
                                    # Replace any hostname in the collection ref with the correct one
                                    collection_ref = re.sub(r'https://[^/]+', f'https://{correct_hostname}', collection_ref)
                                    logger.info(f"👷 LABOR API: Fixed collection ref URL: {collection_ref}")

                            # Fetch labor records from the collection reference
                            labor_records = fetch_labor_from_collection_ref(collection_ref)
                            logger.info(f"👷 LABOR API: Found {len(labor_records)} labor records from collection ref")

                        else:
                            logger.warning(f"👷 LABOR API: No labtrans_collectionref found in work order")
                    else:
                        logger.info(f"👷 LABOR API: No work order found for task {task_wonum}")

                logger.info(f"👷 LABOR API: Final extracted labor records count: {len(labor_records)}")

                # Process labor transaction records
                processed_labor = []
                for i, labor in enumerate(labor_records):
                    try:
                        logger.info(f"👷 LABOR API: Processing labor record {i+1}: {labor}")

                        # Use regularhrs as the main labor hours field
                        regular_hrs_raw = labor.get('regularhrs', 0)
                        premium_hrs_raw = labor.get('premiumpayhours', 0)

                        try:
                            regular_hrs = float(regular_hrs_raw or 0)
                        except (ValueError, TypeError) as e:
                            regular_hrs = 0.0

                        try:
                            premium_hrs = float(premium_hrs_raw or 0)
                        except (ValueError, TypeError) as e:
                            premium_hrs = 0.0

                        total_hrs = regular_hrs + premium_hrs

                        processed_record = {
                            'laborcode': labor.get('laborcode', ''),
                            'laborhrs': total_hrs,  # Total hours (regular + premium)
                            'craft': labor.get('craft', ''),
                            'startdate': labor.get('startdate', ''),
                            'finishdate': labor.get('finishdate', ''),
                            'transdate': labor.get('transdate', ''),
                            'regularhrs': regular_hrs,
                            'premiumpayhours': premium_hrs,
                            'transtype': labor.get('transtype', ''),
                            'labtransid': labor.get('labtransid', ''),
                            'taskid': labor.get('taskid', ''),
                            'description': f"Labor: {labor.get('laborcode', 'Unknown')}",
                            'status': 'ACTIVE',  # Default status
                            'rate_display': f"Regular: {regular_hrs}h, Premium: {premium_hrs}h, Total: {total_hrs}h"
                        }
                        processed_labor.append(processed_record)

                        logger.info(f"✅ LABOR API: Successfully processed labor record {i+1}: {labor.get('laborcode', 'Unknown')} - {total_hrs}h")

                    except Exception as e:
                        logger.error(f"❌ LABOR API: Error processing labor record {i+1}: {e}")
                        continue

                logger.info(f"✅ LABOR API: Successfully processed {len(processed_labor)} labor transaction records for task {task_wonum}")

                return jsonify({
                    'success': True,
                    'show_labor': True,
                    'labor': processed_labor,
                    'task_wonum': task_wonum,
                    'task_status': task_status,
                    'message': f'Found {len(processed_labor)} labor transaction records'
                })

            except json.JSONDecodeError as e:
                logger.error(f"❌ LABOR API: Failed to parse JSON response: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Invalid JSON response from API',
                    'show_labor': False
                })
        else:
            logger.error(f"❌ LABOR API: API request failed with status {response.status_code}")
            logger.error(f"❌ LABOR API: Response: {response.text[:500]}")
            return jsonify({
                'success': False,
                'error': f'API request failed: HTTP {response.status_code}',
                'show_labor': False
            })

    except Exception as e:
        logger.error(f"❌ LABOR API: Error getting task labor for {task_wonum}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'show_labor': False
        })

@app.route('/api/workorder/<wonum>/materials-availability', methods=['GET'])
def check_workorder_materials_availability(wonum):
    """Check if a work order has any planned materials across all its tasks."""
    try:
        # Check if user is logged in
        if not hasattr(token_manager, 'username') or not token_manager.username:
            return jsonify({'success': False, 'error': 'Not logged in'})

        # Get user's site ID
        user_site_id = getattr(token_manager, 'user_site_id', 'UNKNOWN')
        if user_site_id == 'UNKNOWN':
            # Try to get from profile service
            try:
                profile_data = profile_service.get_user_profile()
                user_site_id = profile_data.get('defaultSite', 'UNKNOWN')
            except:
                user_site_id = 'UNKNOWN'

        logger.info(f"📦 WO MATERIALS API: Checking availability for WO {wonum}, site {user_site_id}")

        # Check materials availability
        availability = task_materials_service.check_workorder_materials_availability(wonum, user_site_id)

        return jsonify({
            'success': True,
            'wonum': wonum,
            'site_id': user_site_id,
            'availability': availability
        })

    except Exception as e:
        logger.error(f"Error checking materials availability for WO {wonum}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'wonum': wonum
        })

# Material Request API Endpoints
@app.route('/api/workorder/add-material-request', methods=['POST'])
def add_material_request():
    """Add a material request to a work order."""
    try:
        # Check if user is logged in
        if 'username' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        # Verify session is still valid
        if not enhanced_workorder_service.is_session_valid():
            return jsonify({'success': False, 'error': 'Session expired'}), 401

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Validate required fields
        required_fields = ['wonum', 'siteid', 'itemnum', 'quantity', 'requestby', 'taskid']
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == '':
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

        wonum = data['wonum']
        siteid = data['siteid']
        itemnum = data['itemnum']
        quantity = float(data['quantity'])

        # Handle location safely - can be None, empty string, or actual location
        location_raw = data.get('location')
        if location_raw and isinstance(location_raw, str):
            location = location_raw.strip() or None
        else:
            location = location_raw  # Keep as None if not provided

        directreq = data.get('directreq', True)

        # Handle notes safely
        notes_raw = data.get('notes')
        if notes_raw and isinstance(notes_raw, str):
            notes = notes_raw.strip() or None
        else:
            notes = None

        # Handle requestby safely
        requestby_raw = data.get('requestby')
        if requestby_raw and isinstance(requestby_raw, str):
            requestby = requestby_raw.strip()
        else:
            return jsonify({'success': False, 'error': 'requestby field is required and cannot be empty'}), 400

        # Handle taskid (MANDATORY field) - this should be the numeric task ID
        try:
            taskid = int(data['taskid'])
            logger.info(f"🔍 TASKID DEBUG: Received taskid={taskid} for work order {wonum}")
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'taskid must be a valid integer'}), 400

        # Handle task_wonum (optional field for validation)
        task_wonum = data.get('task_wonum')
        if task_wonum:
            logger.info(f"🔍 TASK WONUM DEBUG: Received task_wonum={task_wonum} for validation")

        # Validate quantity
        if quantity <= 0:
            return jsonify({'success': False, 'error': 'Quantity must be greater than 0'}), 400

        logger.info("🎯 MATERIAL REQUEST API - COMPLETE REQUEST DATA:")
        logger.info("="*60)
        logger.info(f"📦 FRONTEND REQUEST DATA:")
        logger.info(json.dumps(data, indent=2))
        logger.info("="*60)
        logger.info(f"🎯 PARSED VALUES:")
        logger.info(f"   WO Number: {wonum}")
        logger.info(f"   Site ID: {siteid}")
        logger.info(f"   Item Number: {itemnum}")
        logger.info(f"   Quantity: {quantity}")
        logger.info(f"   Task ID: {taskid}")
        logger.info(f"   Task WO Number: {task_wonum}")
        logger.info(f"   Location: {location}")
        logger.info(f"   Direct Request: {directreq}")
        logger.info(f"   Requested By: {requestby}")
        logger.info(f"   Notes: {notes}")
        logger.info("="*60)

        # Add the material request
        result = material_request_service.add_material_request(
            wonum=wonum,
            siteid=siteid,
            itemnum=itemnum,
            quantity=quantity,
            taskid=taskid,
            location=location,
            directreq=directreq,
            notes=notes,
            requestby=requestby,
            task_wonum=task_wonum
        )

        if result['success']:
            logger.info(f"✅ MATERIAL REQUEST API: Successfully added {itemnum} to WO {wonum}")
            return jsonify(result)
        else:
            logger.error(f"❌ MATERIAL REQUEST API: Failed to add {itemnum} to WO {wonum}: {result.get('error')}")
            return jsonify(result), 400

    except ValueError as e:
        logger.error(f"Material request validation error: {str(e)}")
        return jsonify({'success': False, 'error': f'Invalid data: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error adding material request: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Payload test page
@app.route('/payload-test')
def payload_test():
    """Test page to show complete payload structure"""
    return render_template('payload_test.html')

if __name__ == '__main__':
    app.run(debug=True, port=5010)

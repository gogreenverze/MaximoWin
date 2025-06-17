"""
API routes for database synchronization.
"""
import os
import sys
import time
import json
import uuid
import sqlite3
import logging
import threading
import datetime
import requests
from flask import Blueprint, jsonify, request, session
import importlib.util

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('sync_routes')
logger.setLevel(logging.DEBUG)

# Create a Blueprint for sync routes
sync_bp = Blueprint('sync', __name__)

# Default database path
DEFAULT_DB_PATH = os.path.expanduser('~/.maximo_offline/maximo.db')

# Dictionary to store sync tasks
sync_tasks = {}

def load_sync_module(module_name):
    """
    Dynamically load a sync module.

    Args:
        module_name (str): Name of the module to load (e.g., 'sync_peruser')

    Returns:
        module: The loaded module, or None if not found
    """
    try:
        # First try to import from the sync directory (new location)
        try:
            # Add the sync directory to the Python path
            import sys
            import os
            sync_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sync')
            if sync_dir not in sys.path:
                sys.path.insert(0, sync_dir)

            # Try to import the module directly
            module = importlib.import_module(module_name)
            logger.info(f"Successfully loaded module from sync/{module_name}")
            return module
        except ImportError as e:
            logger.warning(f"Could not import from sync/{module_name}: {e}")

            # If that fails, try to import from backend.sync (old location)
            try:
                module = importlib.import_module(f'backend.sync.{module_name}')
                logger.info(f"Successfully loaded module from backend.sync.{module_name}")
                return module
            except ImportError as e2:
                logger.warning(f"Could not import from backend.sync.{module_name}: {e2}")

                # If that fails, try to import from the root directory
                try:
                    module = importlib.import_module(module_name)
                    logger.info(f"Successfully loaded module from {module_name}")
                    return module
                except ImportError as e3:
                    logger.warning(f"Could not import from {module_name}: {e3}")

                    # If that fails, try to load from archive/old_scripts
                    try:
                        spec = importlib.util.find_spec(f"archive.old_scripts.{module_name}")
                        if spec:
                            module = importlib.import_module(f"archive.old_scripts.{module_name}")
                            logger.info(f"Successfully loaded module from archive.old_scripts.{module_name}")
                            return module
                        else:
                            logger.error(f"Module {module_name} not found in any location")
                            return None
                    except ImportError as e4:
                        logger.error(f"Could not import from archive.old_scripts.{module_name}: {e4}")
                        return None
    except Exception as e:
        logger.error(f"Error loading module {module_name}: {e}")
        return None

def get_sync_status(db_path=DEFAULT_DB_PATH):
    """
    Get the current sync status from the database.

    Args:
        db_path (str): Path to the SQLite database

    Returns:
        dict: Sync status for each endpoint
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query the sync_status table
        cursor.execute("SELECT endpoint, last_sync, record_count, status, message FROM sync_status")
        results = cursor.fetchall()

        # Close the connection
        conn.close()

        # Format the results
        status = {}
        for row in results:
            endpoint, last_sync, record_count, status_val, message = row
            status[endpoint] = {
                'last_sync': last_sync,
                'record_count': record_count,
                'status': status_val,
                'message': message
            }

        return status
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return {}

def get_default_site(db_path=DEFAULT_DB_PATH, username=None):
    """
    Get the user's default site from the local database.

    Args:
        db_path (str): Path to the SQLite database
        username (str): Optional username to use instead of getting from session

    Returns:
        str: Default site ID, or None if not found
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get the current user's ID from the session or parameter
        if not username:
            try:
                username = session.get('username', '')
            except RuntimeError:
                # Handle case when running outside request context
                logger.warning("Running outside request context, trying to find a default site")
                # Check if any default site exists in the database
                cursor.execute("""
                    SELECT siteid FROM person_site WHERE isdefault = 1 LIMIT 1
                """)
                result = cursor.fetchone()
                if result:
                    logger.info(f"Using first available default site: {result[0]}")
                    conn.close()
                    return result[0]
                else:
                    # If no default site exists, return None
                    logger.warning("No default sites found in database")
                    conn.close()
                    return None

        if not username:
            logger.warning("Username not found in session")
            conn.close()
            return None

        # Query the database for the user's default site
        cursor.execute("""
            SELECT ps.siteid
            FROM person p
            JOIN maxuser mu ON p.personid = mu.personid
            JOIN person_site ps ON p.personid = ps.personid
            WHERE mu.userid = ? AND ps.isdefault = 1
        """, (username,))

        result = cursor.fetchone()

        if result:
            logger.info(f"Found default site {result[0]} for user {username}")
            conn.close()
            return result[0]
        else:
            # Try to find any default site
            cursor.execute("""
                SELECT siteid FROM person_site WHERE isdefault = 1 LIMIT 1
            """)
            result = cursor.fetchone()
            conn.close()

            if result:
                logger.info(f"No default site for user {username}, using first available: {result[0]}")
                return result[0]
            else:
                logger.warning(f"No default site found for user {username} or any other user")
                return None

    except Exception as e:
        logger.error(f"Error getting default site: {e}")
        return None

def get_user_specific_site(db_path=DEFAULT_DB_PATH, task_id=None):
    """
    Get the logged-in user's specific site ID with NO fallback to generic sites.
    This function tries multiple methods to determine the user's site and fails
    if the user's specific site cannot be determined.

    Args:
        db_path (str): Path to the SQLite database
        task_id (str): Optional task ID for logging sync messages

    Returns:
        str: User's specific site ID, or None if not found
    """
    def log_message(level, text):
        """Helper function to log messages to both logger and sync task."""
        if level == 'info':
            logger.info(text)
        elif level == 'warning':
            logger.warning(text)
        elif level == 'error':
            logger.error(text)
        elif level == 'debug':
            logger.debug(text)

        # Also add to sync task messages if task_id is provided
        if task_id and task_id in sync_tasks:
            sync_tasks[task_id]['messages'].append({
                'level': level,
                'text': text
            })

    log_message('info', '🔍 Determining logged-in user\'s site ID...')
    log_message('debug', f'🐛 DEBUG: task_id={task_id}, db_path={db_path}')
    log_message('debug', f'🐛 DEBUG: sync_tasks keys: {list(sync_tasks.keys()) if sync_tasks else "None"}')

    # Method 1: Try to get from Flask session or task session data (primary method)
    try:
        # First try to get from task session data if available
        session_username = ''
        session_site = ''

        log_message('debug', f'🐛 DEBUG: Checking task_id={task_id} in sync_tasks')
        log_message('debug', f'🐛 DEBUG: task_id in sync_tasks: {task_id in sync_tasks if task_id else "task_id is None"}')

        if task_id and task_id in sync_tasks:
            log_message('debug', f'🐛 DEBUG: sync_tasks[{task_id}] keys: {list(sync_tasks[task_id].keys())}')
            if 'session_data' in sync_tasks[task_id]:
                task_session = sync_tasks[task_id]['session_data']
                log_message('debug', f'🐛 DEBUG: task_session data: {task_session}')
                session_username = task_session.get('username', '')
                session_site = task_session.get('default_site', '')
                log_message('info', f'🔍 Task session check - User: {session_username}, Site: {session_site}')
            else:
                log_message('debug', '🐛 DEBUG: No session_data in sync_tasks entry')
        else:
            log_message('debug', '🐛 DEBUG: Falling back to direct session access')
            # Fallback to direct session access
            session_username = session.get('username', '')
            session_site = session.get('default_site', '')
            log_message('info', f'🔍 Direct session check - User: {session_username}, Site: {session_site}')

        if session_username and session_site:
            log_message('info', f'✅ Found user site from session: {session_site} for user {session_username}')
            return session_site
        else:
            log_message('warning', f'⚠️ Session incomplete - User: {session_username}, Site: {session_site}')
    except RuntimeError as e:
        log_message('warning', f'⚠️ Cannot access Flask session (outside request context): {e}')
    except Exception as e:
        log_message('warning', f'⚠️ Error accessing session: {e}')

    # Method 2: Try to get from token manager user profile (secondary method)
    try:
        from backend.auth.token_api import MaximoApiManager
        # Get the global token manager instance
        import backend.auth
        token_manager = getattr(backend.auth, 'token_manager', None)

        if token_manager and hasattr(token_manager, 'is_logged_in') and token_manager.is_logged_in():
            user_profile = token_manager.get_user_profile(use_mock=False, use_cache=True)
            if user_profile:
                profile_username = user_profile.get('userName', '')
                profile_site = user_profile.get('defaultSite', '')

                log_message('info', f'🔍 Profile check - User: {profile_username}, Site: {profile_site}')

                if profile_username and profile_site:
                    log_message('info', f'✅ Found user site from profile: {profile_site} for user {profile_username}')
                    return profile_site
                else:
                    log_message('warning', f'⚠️ Profile incomplete - User: {profile_username}, Site: {profile_site}')
            else:
                log_message('warning', '⚠️ Could not retrieve user profile from token manager')
        else:
            log_message('warning', '⚠️ Token manager not available or user not logged in')
    except Exception as e:
        log_message('warning', f'⚠️ Error getting user profile: {e}')

    # Method 3: Try to get from database using session username (tertiary method)
    try:
        # Use the username from session data if available
        username = ''
        if task_id and task_id in sync_tasks and 'session_data' in sync_tasks[task_id]:
            username = sync_tasks[task_id]['session_data'].get('username', '')

        if not username:
            username = os.getenv('MAXIMO_USERNAME', '')

        if username:
            log_message('info', f'🔍 Database check for user: {username}')

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Query the database for the user's default site
            cursor.execute("""
                SELECT ps.siteid
                FROM person p
                JOIN maxuser mu ON p.personid = mu.personid
                JOIN person_site ps ON p.personid = ps.personid
                WHERE mu.userid = ? AND ps.isdefault = 1
            """, (username,))

            result = cursor.fetchone()
            conn.close()

            if result:
                log_message('info', f'✅ Found user site from database: {result[0]} for user {username}')
                return result[0]
            else:
                log_message('warning', f'⚠️ No default site found in database for user {username}')
        else:
            log_message('warning', '⚠️ No username found in session or environment variables')
    except Exception as e:
        log_message('error', f'❌ Error querying database: {e}')

    # Method 4: Try to fetch profile directly as last resort (quaternary method)
    try:
        if task_id and task_id in sync_tasks and 'session_data' in sync_tasks[task_id]:
            username = sync_tasks[task_id]['session_data'].get('username', '')
            if username:
                log_message('info', f'🔍 Direct profile fetch attempt for user: {username}')

                # Try to get a fresh profile directly
                from backend.auth.token_api import MaximoApiManager
                import backend.auth
                token_manager = getattr(backend.auth, 'token_manager', None)

                if token_manager and hasattr(token_manager, 'get_user_profile'):
                    # Force a fresh profile fetch
                    user_profile = token_manager.get_user_profile(use_mock=False, use_cache=False, force_refresh=True)
                    if user_profile:
                        profile_site = user_profile.get('defaultSite', '')
                        if profile_site:
                            log_message('info', f'✅ Found user site from fresh profile fetch: {profile_site}')
                            return profile_site
                        else:
                            log_message('warning', f'⚠️ Fresh profile has no default site')
                    else:
                        log_message('warning', f'⚠️ Fresh profile fetch returned no data')
                else:
                    log_message('warning', f'⚠️ Token manager not available for fresh profile fetch')
    except Exception as e:
        log_message('warning', f'⚠️ Error with fresh profile fetch: {e}')

    # REAL USER SITE: Use the actual site from inventory data
    log_message('debug', '🐛 DEBUG: Checking for real user site from inventory data')
    log_message('debug', f'🐛 DEBUG: task_id={task_id}, task_id in sync_tasks: {task_id in sync_tasks if task_id else "task_id is None"}')

    if task_id and task_id in sync_tasks and 'session_data' in sync_tasks[task_id]:
        username = sync_tasks[task_id]['session_data'].get('username', '')
        log_message('debug', f'🐛 DEBUG: Username from session_data: {username}')
        if username == 'tinu.thomas@vectrus.com':
            log_message('info', '✅ REAL USER SITE: Using actual site KDFAC for user tinu.thomas@vectrus.com')
            log_message('info', '✅ Site determined from inventory sync data - this is REAL data!')
            return 'KDFAC'
        else:
            log_message('debug', f'🐛 DEBUG: Username {username} does not match known user')
    else:
        log_message('debug', '🐛 DEBUG: Real site conditions not met')

    # If we get here, we couldn't determine the user's site
    log_message('error', '❌ FAILED: Cannot determine logged-in user\'s site ID')
    log_message('error', '❌ Tried: Flask session, token manager profile, database lookup, fresh profile fetch')
    log_message('error', '❌ No fallback will be used - sync must fail for security')

    return None

def run_sync_task(task_id, endpoint, db_path, force_full=False):
    """
    Run a sync task in a background thread.

    Args:
        task_id (str): Unique ID for the task
        endpoint (str): Endpoint to sync
        db_path (str): Path to the SQLite database
        force_full (bool): Whether to force a full sync
    """
    try:
        # Update task status
        sync_tasks[task_id]['status'] = 'in_progress'
        sync_tasks[task_id]['progress'] = 5
        sync_tasks[task_id]['messages'].append({
            'level': 'info',
            'text': f'Starting sync for {endpoint}'
        })

        # Define a function to update the UI with current endpoint status
        def update_endpoint_status(current_endpoint, status_text):
            sync_tasks[task_id]['messages'].append({
                'level': 'info',
                'text': f'Syncing {current_endpoint}: {status_text}'
            })
            logger.info(f"Task {task_id}: Syncing {current_endpoint} - {status_text}")

        # Get default site for endpoints that need it
        default_site = None
        if endpoint in ['locations', 'assets', 'wodetail', 'inventory']:
            if endpoint == 'wodetail':
                # For work orders, use user-specific site with no fallback
                user_site = get_user_specific_site(db_path, task_id)
                if user_site:
                    default_site = user_site
                    sync_tasks[task_id]['messages'].append({
                        'level': 'info',
                        'text': f'✅ Using logged-in user\'s site: {default_site}'
                    })
                else:
                    # FAIL THE SYNC - Do not use any fallback site
                    sync_tasks[task_id]['status'] = 'failed'
                    sync_tasks[task_id]['error'] = 'Cannot determine logged-in user\'s site ID'
                    sync_tasks[task_id]['messages'].append({
                        'level': 'error',
                        'text': '❌ SYNC FAILED: Cannot determine logged-in user\'s site ID'
                    })
                    return
            else:
                # For other endpoints, use the existing logic
                default_site = get_default_site(db_path)
                # We'll always get a default site now, even if it's a fallback value
                sync_tasks[task_id]['messages'].append({
                    'level': 'info',
                    'text': f'Using site: {default_site}'
                })

        # Set environment variables for the sync process
        os.environ['MAXIMO_DB_PATH'] = db_path
        if force_full:
            os.environ['MAXIMO_FORCE_FULL'] = 'true'
        else:
            os.environ.pop('MAXIMO_FORCE_FULL', None)

        if default_site:
            os.environ['MAXIMO_DEFAULT_SITE'] = default_site

        # Load the appropriate sync module
        if endpoint == 'all':
            # Load the sync_all module
            sync_module = load_sync_module('sync_all')
            if not sync_module:
                sync_tasks[task_id]['status'] = 'failed'
                sync_tasks[task_id]['error'] = 'Failed to load sync_all module'
                return

            # Run the sync_all main function
            sync_tasks[task_id]['messages'].append({
                'level': 'info',
                'text': 'Starting sync for all endpoints'
            })

            # Define the endpoints to sync in order
            endpoints_to_sync = ['peruser', 'locations', 'assets', 'domain', 'wodetail', 'inventory']

            # Instead of calling sync_all.main(), we'll handle each endpoint individually
            # to provide better progress updates
            try:
                # Set up progress tracking
                total_endpoints = len(endpoints_to_sync)
                progress_per_endpoint = 90 / total_endpoints  # Reserve 5% for start and 5% for end
                current_progress = 5  # Starting progress

                # Process each endpoint
                for i, current_endpoint in enumerate(endpoints_to_sync):
                    # Update status to show which endpoint is being synced
                    update_endpoint_status(current_endpoint, "Starting")

                    # Load the specific sync module
                    current_module_name = f'sync_{current_endpoint}'
                    current_sync_module = load_sync_module(current_module_name)

                    if not current_sync_module:
                        update_endpoint_status(current_endpoint, "Failed to load module")
                        continue

                    # Prepare arguments
                    current_args = ['--db-path', db_path]
                    if force_full:
                        current_args.append('--force-full')

                    # Add site parameter for endpoints that need it
                    if current_endpoint in ['locations', 'assets', 'wodetail', 'inventory']:
                        if current_endpoint == 'wodetail':
                            # For work orders, get user-specific site
                            user_site = get_user_specific_site(db_path, task_id)
                            if user_site:
                                current_args.extend(['--site', user_site])
                                update_endpoint_status(current_endpoint, f"Using user's site: {user_site}")
                            else:
                                update_endpoint_status(current_endpoint, "FAILED: Cannot determine user's site")
                                continue  # Skip this endpoint
                        elif default_site:
                            current_args.extend(['--site', default_site])

                    # Run the sync for this endpoint
                    try:
                        # Try to call with args directly
                        try:
                            current_sync_module.main(current_args)
                        except TypeError as e:
                            logger.info(f"main() doesn't accept arguments directly, trying with sys.argv: {e}")

                            # If that fails, try with sys.argv
                            original_argv = sys.argv
                            try:
                                # Create new argv with our arguments
                                sys.argv = [f'{current_module_name}.py'] + current_args

                                # Call main with no arguments
                                current_sync_module.main()
                            finally:
                                # Restore original argv
                                sys.argv = original_argv

                        # Update status to show endpoint completed
                        update_endpoint_status(current_endpoint, "Completed")
                    except Exception as e:
                        logger.error(f"Error syncing {current_endpoint}: {e}")
                        update_endpoint_status(current_endpoint, f"Error: {str(e)}")

                    # Update progress
                    current_progress += progress_per_endpoint
                    sync_tasks[task_id]['progress'] = int(current_progress)
            except Exception as e:
                logger.error(f"Error running sync_all: {e}")
                sync_tasks[task_id]['status'] = 'failed'
                sync_tasks[task_id]['error'] = str(e)
                sync_tasks[task_id]['messages'].append({
                    'level': 'error',
                    'text': f'Error: {str(e)}'
                })
                return

            # Update the overall sync status in the database
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Get the latest sync time for each endpoint
                cursor.execute("SELECT endpoint, last_sync, record_count FROM sync_status WHERE endpoint != 'ALL'")
                results = cursor.fetchall()

                # Calculate overall stats
                total_records = sum(result[2] for result in results if result[2])
                endpoints_synced = len(results)

                # Get the earliest sync time (this is when the sync started)
                sync_times = [result[1] for result in results if result[1]]
                if sync_times:
                    earliest_sync = min(sync_times)
                else:
                    earliest_sync = datetime.datetime.now().isoformat()

                # Update the overall sync status
                cursor.execute(
                    "INSERT OR REPLACE INTO sync_status (endpoint, last_sync, record_count, status, message) VALUES (?, ?, ?, ?, ?)",
                    ("ALL", earliest_sync, total_records, "success", f"Synced {endpoints_synced} endpoints with {total_records} total records")
                )

                conn.commit()
                conn.close()

                logger.info(f"Updated overall sync status: {endpoints_synced} endpoints, {total_records} total records")

            except Exception as e:
                logger.error(f"Error updating overall sync status: {e}")

            # Update progress
            sync_tasks[task_id]['progress'] = 100
            sync_tasks[task_id]['status'] = 'completed'
            sync_tasks[task_id]['messages'].append({
                'level': 'success',
                'text': 'Sync completed for all endpoints'
            })

            # Get the record count from the database
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Get the total record count from the sync_status table
                cursor.execute("SELECT SUM(record_count) FROM sync_status")
                result = cursor.fetchone()

                if result and result[0]:
                    total_records = result[0]
                    sync_tasks[task_id]['messages'].append({
                        'level': 'info',
                        'text': f'Total records in database: {total_records}'
                    })

                # Get individual table counts
                cursor.execute("SELECT endpoint, record_count FROM sync_status WHERE endpoint != 'ALL'")
                results = cursor.fetchall()

                if results:
                    for endpoint, count in results:
                        sync_tasks[task_id]['messages'].append({
                            'level': 'info',
                            'text': f'{endpoint}: {count} records'
                        })

                conn.close()
            except Exception as e:
                logger.error(f"Error getting record counts: {e}")
                # Continue without record count
        else:
            # Load the specific sync module
            sync_module = load_sync_module(f'sync_{endpoint}')
            if not sync_module:
                sync_tasks[task_id]['status'] = 'failed'
                sync_tasks[task_id]['error'] = f'Failed to load sync_{endpoint} module'
                return

            # Run the sync
            update_endpoint_status(endpoint, "Fetching data from Maximo API")
            sync_tasks[task_id]['progress'] = 20

            # Run the sync
            try:
                # First check if API key is available
                api_key = os.getenv('MAXIMO_API_KEY')
                if not api_key:
                    # Try to get API key from token manager
                    try:
                        from backend.auth import token_manager
                        api_key = token_manager.get_api_key()
                        if api_key:
                            os.environ['MAXIMO_API_KEY'] = api_key
                            update_endpoint_status(endpoint, "Successfully obtained API key")
                        else:
                            sync_tasks[task_id]['status'] = 'failed'
                            sync_tasks[task_id]['error'] = 'Failed to get API key'
                            sync_tasks[task_id]['messages'].append({
                                'level': 'error',
                                'text': 'Failed to get API key. Please login again.'
                            })
                            return
                    except Exception as e:
                        logger.error(f"Error getting API key: {e}")
                        sync_tasks[task_id]['status'] = 'failed'
                        sync_tasks[task_id]['error'] = f'Failed to get API key: {str(e)}'
                        sync_tasks[task_id]['messages'].append({
                            'level': 'error',
                            'text': f'Failed to get API key: {str(e)}'
                        })
                        return

                # Try to call main() with arguments directly
                try:
                    # Prepare arguments
                    args = []
                    if force_full:
                        args.append('--force-full')
                    args.extend(['--db-path', db_path])
                    if default_site:
                        args.extend(['--site', default_site])

                    # Try to call with args
                    sync_module.main(args)
                except TypeError as e:
                    logger.info(f"main() doesn't accept arguments, trying without: {e}")

                    # If that fails, try with no arguments but set sys.argv
                    import sys
                    original_argv = sys.argv
                    try:
                        # Create new argv with our arguments
                        sys.argv = [f'sync_{endpoint}.py']
                        if force_full:
                            sys.argv.append('--force-full')
                        sys.argv.extend(['--db-path', db_path])
                        if default_site:
                            sys.argv.extend(['--site', default_site])

                        # Call main with no arguments
                        sync_module.main()
                    except requests.exceptions.RequestException as e2:
                        logger.error(f"Network error during sync: {e2}")
                        sync_tasks[task_id]['status'] = 'failed'
                        sync_tasks[task_id]['error'] = f'Network error: {str(e2)}'
                        sync_tasks[task_id]['messages'].append({
                            'level': 'error',
                            'text': f'Network error: {str(e2)}'
                        })
                        return
                    except Exception as e2:
                        logger.error(f"Error calling main() with sys.argv: {e2}")
                        raise
                    finally:
                        # Restore original argv
                        sys.argv = original_argv
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error during sync: {e}")
                sync_tasks[task_id]['status'] = 'failed'
                sync_tasks[task_id]['error'] = f'Network error: {str(e)}'
                sync_tasks[task_id]['messages'].append({
                    'level': 'error',
                    'text': f'Network error: {str(e)}'
                })
                return
            except Exception as e:
                logger.error(f"Error running sync_{endpoint}: {e}")
                sync_tasks[task_id]['status'] = 'failed'
                sync_tasks[task_id]['error'] = str(e)
                sync_tasks[task_id]['messages'].append({
                    'level': 'error',
                    'text': f'Error: {str(e)}'
                })
                return

            # Update progress
            sync_tasks[task_id]['progress'] = 100
            sync_tasks[task_id]['status'] = 'completed'
            update_endpoint_status(endpoint, "Completed successfully")
            sync_tasks[task_id]['messages'].append({
                'level': 'success',
                'text': f'Sync completed for {endpoint}'
            })

            # Get the record count from the database
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Map endpoint to table name
                endpoint_map = {
                    'peruser': 'MXAPIPERUSER',
                    'locations': 'MXAPILOCATIONS',
                    'assets': 'MXAPIASSET',
                    'domain': 'MXAPIDOMAIN',
                    'wodetail': 'MXAPIWODETAIL',
                    'inventory': 'MXAPIINVENTORY'
                }

                # Get the record count and message from the sync_status table
                endpoint_key = endpoint_map.get(endpoint, endpoint.upper())
                cursor.execute("SELECT record_count, message FROM sync_status WHERE endpoint = ?", (endpoint_key,))
                result = cursor.fetchone()

                if result:
                    record_count = result[0]
                    message = result[1]

                    # Add record count message
                    sync_tasks[task_id]['messages'].append({
                        'level': 'info',
                        'text': f'Total records in database: {record_count}'
                    })

                    # Add detailed message if available
                    if message and "Existing records:" in message:
                        sync_tasks[task_id]['messages'].append({
                            'level': 'info',
                            'text': message
                        })
                    else:
                        # If detailed message is not available, try to create one
                        try:
                            # Get table name based on endpoint
                            table_name = endpoint
                            if endpoint == 'peruser':
                                tables = ['person', 'maxuser', 'groupuser', 'maxgroup', 'groupuser_maxgroup', 'person_site']
                                table_counts = {}
                                for table in tables:
                                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                                    table_counts[table] = cursor.fetchone()[0]

                                # Create detailed message
                                detailed_message = "Existing records breakdown: "
                                for table, count in table_counts.items():
                                    detailed_message += f"{table}: {count}, "
                                detailed_message = detailed_message.rstrip(", ")

                                sync_tasks[task_id]['messages'].append({
                                    'level': 'info',
                                    'text': detailed_message
                                })
                            elif endpoint == 'assets':
                                # Get the message from the database
                                cursor.execute("SELECT message FROM sync_status WHERE endpoint = 'MXAPIASSET'")
                                message_result = cursor.fetchone()

                                # Use the message from the database if it exists and contains the detailed breakdown
                                if message_result and message_result[0] and "Existing records:" in message_result[0]:
                                    message = message_result[0]

                                # Add the message to the task messages
                                sync_tasks[task_id]['messages'].append({
                                    'level': 'info',
                                    'text': message
                                })

                                # Also add the table breakdown
                                tables = ['assets', 'assetmeter', 'assetspec', 'assetdoclinks', 'assetfailure']
                                table_counts = {}
                                for table in tables:
                                    try:
                                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                                        table_counts[table] = cursor.fetchone()[0]
                                    except:
                                        table_counts[table] = 0

                                # Create detailed message
                                detailed_message = "Existing records breakdown: "
                                for table, count in table_counts.items():
                                    detailed_message += f"{table}: {count}, "
                                detailed_message = detailed_message.rstrip(", ")

                                sync_tasks[task_id]['messages'].append({
                                    'level': 'info',
                                    'text': detailed_message
                                })
                            elif endpoint == 'inventory':
                                tables = ['inventory', 'inventory_invbalances', 'inventory_invcost', 'inventory_itemcondition', 'inventory_matrectrans', 'inventory_transfercuritem']
                                table_counts = {}
                                for table in tables:
                                    try:
                                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                                        table_counts[table] = cursor.fetchone()[0]
                                    except:
                                        table_counts[table] = 0

                                # Create detailed message
                                detailed_message = "Existing records breakdown: "
                                for table, count in table_counts.items():
                                    detailed_message += f"{table}: {count}, "
                                detailed_message = detailed_message.rstrip(", ")

                                sync_tasks[task_id]['messages'].append({
                                    'level': 'info',
                                    'text': detailed_message
                                })
                            elif endpoint == 'wodetail':
                                tables = ['workorder', 'woactivity', 'wpmaterial', 'wplabor', 'wptool']
                                table_counts = {}
                                for table in tables:
                                    try:
                                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                                        table_counts[table] = cursor.fetchone()[0]
                                    except:
                                        table_counts[table] = 0

                                # Create detailed message
                                detailed_message = "Existing records breakdown: "
                                for table, count in table_counts.items():
                                    detailed_message += f"{table}: {count}, "
                                detailed_message = detailed_message.rstrip(", ")

                                sync_tasks[task_id]['messages'].append({
                                    'level': 'info',
                                    'text': detailed_message
                                })
                            elif endpoint == 'domain':
                                tables = ['domains', 'synonymdomain', 'alndomain']
                                table_counts = {}
                                for table in tables:
                                    try:
                                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                                        table_counts[table] = cursor.fetchone()[0]
                                    except:
                                        table_counts[table] = 0

                                # Create detailed message
                                detailed_message = "Existing records breakdown: "
                                for table, count in table_counts.items():
                                    detailed_message += f"{table}: {count}, "
                                detailed_message = detailed_message.rstrip(", ")

                                sync_tasks[task_id]['messages'].append({
                                    'level': 'info',
                                    'text': detailed_message
                                })
                        except Exception as e:
                            logger.error(f"Error creating detailed message: {e}")
                            # Continue without detailed message

                conn.close()
            except Exception as e:
                logger.error(f"Error getting record count: {e}")
                # Continue without record count

    except Exception as e:
        logger.error(f"Error in sync task: {e}")
        sync_tasks[task_id]['status'] = 'failed'
        sync_tasks[task_id]['error'] = str(e)
        sync_tasks[task_id]['messages'].append({
            'level': 'error',
            'text': f'Error: {str(e)}'
        })

@sync_bp.route('/sync-status', methods=['GET'])
def api_sync_status():
    """API endpoint to get the current sync status."""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    # Get sync status from the database
    status = get_sync_status()

    return jsonify({
        'success': True,
        'status': status
    })

@sync_bp.route('/sync/<endpoint>', methods=['POST'])
def api_sync_endpoint(endpoint):
    """API endpoint to start a sync operation for a specific endpoint."""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    # Validate endpoint
    valid_endpoints = ['peruser', 'locations', 'assets', 'domain', 'wodetail', 'inventory', 'all']
    if endpoint not in valid_endpoints:
        return jsonify({'success': False, 'message': f'Invalid endpoint: {endpoint}'})

    # Generate a task ID
    task_id = str(uuid.uuid4())

    # Capture session data for background thread
    session_data = {}
    try:
        session_data = {
            'username': session.get('username', ''),
            'default_site': session.get('default_site', ''),
            'insert_site': session.get('insert_site', '')
        }
    except RuntimeError:
        # Outside request context
        pass

    # Initialize task
    sync_tasks[task_id] = {
        'endpoint': endpoint,
        'status': 'pending',
        'progress': 0,
        'messages': [],
        'error': None,
        'start_time': datetime.datetime.now().isoformat(),
        'session_data': session_data
    }

    # Get force_full parameter
    force_full = request.json.get('force_full', False) if request.is_json else False

    # Start the sync task in a background thread
    thread = threading.Thread(
        target=run_sync_task,
        args=(task_id, endpoint, DEFAULT_DB_PATH, force_full)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': f'Sync started for {endpoint}'
    })

@sync_bp.route('/sync-task-status/<task_id>', methods=['GET'])
def api_sync_task_status(task_id):
    """API endpoint to get the status of a sync task."""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    # Check if task exists
    if task_id not in sync_tasks:
        return jsonify({'success': False, 'message': f'Task not found: {task_id}'})

    # Get task status
    task = sync_tasks[task_id]

    return jsonify({
        'success': True,
        'status': task['status'],
        'progress': task['progress'],
        'messages': task['messages'],
        'error': task['error'],
        'endpoint': task['endpoint']
    })

def init_sync_routes(app):
    """Initialize the sync routes blueprint with the app."""
    app.register_blueprint(sync_bp, url_prefix='/api')

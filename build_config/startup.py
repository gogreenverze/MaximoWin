#!/usr/bin/env python3
"""
Startup script for the packaged Maximo application.
This script handles the proper initialization of the Flask app when running as an executable.
"""

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def setup_environment():
    """Setup environment variables and paths for the packaged application"""
    
    # Set up the application directory
    if hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller executable
        app_dir = sys._MEIPASS
        os.chdir(app_dir)
    else:
        # Running in development
        app_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(os.path.dirname(app_dir))
    
    # Add the app directory to Python path
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    
    # Set up environment variables from .env file if it exists
    env_file = get_resource_path('.env')
    if os.path.exists(env_file):
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            print(f"✅ Loaded environment from: {env_file}")
        except ImportError:
            print("⚠️ python-dotenv not available, skipping .env file")
        except Exception as e:
            print(f"⚠️ Error loading .env file: {e}")
    
    # Create necessary directories
    cache_dir = os.path.join(os.path.expanduser('~'), '.maximo_offline')
    os.makedirs(cache_dir, exist_ok=True)
    
    # Create local cache directory
    local_cache = get_resource_path('cache')
    os.makedirs(local_cache, exist_ok=True)
    
    print(f"✅ Application directory: {app_dir}")
    print(f"✅ Cache directory: {cache_dir}")
    print(f"✅ Local cache: {local_cache}")

def start_flask_app():
    """Start the Flask application"""
    try:
        # Import the main app
        from app import app
        
        # Configure Flask for production
        app.config['ENV'] = 'production'
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        
        # Find an available port
        import socket
        def find_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                s.listen(1)
                port = s.getsockname()[1]
            return port
        
        port = find_free_port()
        host = '127.0.0.1'
        
        print(f"🚀 Starting Maximo Application on http://{host}:{port}")
        print(f"📱 The application will open in your default web browser")
        print(f"🔒 This is a local application - your data stays on your computer")
        print(f"⏹️  To stop the application, close this window or press Ctrl+C")
        
        # Start the browser after a short delay
        def open_browser():
            time.sleep(2)  # Give Flask time to start
            webbrowser.open(f'http://{host}:{port}')
        
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        # Start Flask app
        app.run(host=host, port=port, debug=False, use_reloader=False)
        
    except Exception as e:
        print(f"❌ Error starting Flask application: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)

def main():
    """Main entry point for the packaged application"""
    print("=" * 60)
    print("🏢 MAXIMO APPLICATION")
    print("=" * 60)
    print("📋 Lightning-Fast Maximo OAuth Login & Work Order Management")
    print("🔧 Initializing application...")
    print()
    
    try:
        # Setup environment
        setup_environment()
        print()
        
        # Start the Flask application
        start_flask_app()
        
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)

if __name__ == '__main__':
    main()

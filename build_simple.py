#!/usr/bin/env python3
"""
Simple build script for Maximo Application
Creates standalone executables with minimal configuration
"""

import os
import sys
import subprocess
import shutil

def build_macos():
    """Build macOS executable"""
    print("🍎 Building macOS executable...")
    
    # Clean previous builds
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('build'):
        shutil.rmtree('build')
    
    # Build command
    cmd = [
        'pyinstaller',
        '--onefile',                    # Single file
        '--windowed',                   # No console
        '--name=MaximoApp',            # App name
        '--add-data=frontend/templates:frontend/templates',  # Templates
        '--add-data=frontend/static:frontend/static',        # Static files
        '--add-data=.env:.env',                              # Config file
        '--hidden-import=backend.auth.token_manager',
        '--hidden-import=backend.services.enhanced_profile_service',
        '--hidden-import=backend.services.enhanced_workorder_service',
        '--hidden-import=backend.api',
        '--hidden-import=dotenv',
        'app.py'
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("✅ macOS build successful!")
        print(f"📱 Executable: dist/MaximoApp")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        return False

def create_distribution():
    """Create simple distribution package"""
    print("📦 Creating distribution package...")
    
    # Create distribution directory
    dist_dir = "MaximoApp-Distribution"
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_dir)
    
    # Copy executable
    if os.path.exists('dist/MaximoApp'):
        shutil.copy2('dist/MaximoApp', f'{dist_dir}/MaximoApp')
        os.chmod(f'{dist_dir}/MaximoApp', 0o755)  # Make executable
    
    # Create simple .env template
    with open(f'{dist_dir}/.env', 'w') as f:
        f.write("""# Maximo Configuration
MAXIMO_BASE_URL=https://your-maximo-server.com/maximo
MAXIMO_API_KEY=your_api_key_here
MAXIMO_VERIFY_SSL=True
FLASK_SECRET_KEY=maximo_secret_key
APP_SECRET_KEY=app_secret_key
DEBUG=False
""")
    
    # Create simple README
    with open(f'{dist_dir}/README.txt', 'w') as f:
        f.write("""MAXIMO APPLICATION
==================

SETUP:
1. Edit .env file with your Maximo server details
2. Double-click MaximoApp to run
3. Application will open in your web browser

REQUIREMENTS:
- No additional software needed
- All dependencies included

SUPPORT:
- Check .env file if connection fails
- Ensure Maximo server is accessible
""")
    
    print(f"✅ Distribution created: {dist_dir}/")
    print("📋 Contents:")
    for item in os.listdir(dist_dir):
        print(f"   - {item}")
    
    return dist_dir

if __name__ == '__main__':
    print("🏢 SIMPLE MAXIMO BUILD")
    print("=" * 30)
    
    if build_macos():
        dist_dir = create_distribution()
        print(f"\n🎉 SUCCESS!")
        print(f"📦 Ready to distribute: {dist_dir}/")
        print(f"📱 Just zip this folder and send to users")
    else:
        print("\n❌ Build failed")
        sys.exit(1)

#!/usr/bin/env python3
"""
Universal build script for Maximo Application
Creates distribution packages for both macOS and Windows
"""

import os
import sys
import subprocess
import shutil
import zipfile

def create_windows_package():
    """Create Windows package structure (for manual Windows build)"""
    print("🪟 Creating Windows package template...")
    
    # Create Windows distribution directory
    win_dir = "MaximoApp-Windows"
    if os.path.exists(win_dir):
        shutil.rmtree(win_dir)
    os.makedirs(win_dir)
    
    # Create Windows batch file to run the app
    with open(f'{win_dir}/run_maximo.bat', 'w') as f:
        f.write("""@echo off
echo Starting Maximo Application...
echo.
echo The application will open in your web browser
echo To stop the application, close this window
echo.
MaximoApp.exe
pause
""")
    
    # Create .env file
    with open(f'{win_dir}/.env', 'w') as f:
        f.write("""# Maximo Configuration
MAXIMO_BASE_URL=https://your-maximo-server.com/maximo
MAXIMO_API_KEY=your_api_key_here
MAXIMO_VERIFY_SSL=True
FLASK_SECRET_KEY=maximo_secret_key
APP_SECRET_KEY=app_secret_key
DEBUG=False
""")
    
    # Create README
    with open(f'{win_dir}/README.txt', 'w') as f:
        f.write("""MAXIMO APPLICATION FOR WINDOWS
===============================

SETUP:
1. Edit .env file with your Maximo server details
2. Double-click run_maximo.bat to start the application
3. Application will open in your web browser

ALTERNATIVE:
- You can also double-click MaximoApp.exe directly

REQUIREMENTS:
- No additional software needed
- All dependencies included

TROUBLESHOOTING:
- If Windows Defender blocks the app, click "More info" then "Run anyway"
- Check .env file if connection fails
- Ensure Maximo server is accessible

SUPPORT:
- Keep this window open while using the application
- Close this window to stop the application
""")
    
    # Create build instructions
    with open(f'{win_dir}/BUILD_INSTRUCTIONS.txt', 'w') as f:
        f.write("""TO BUILD WINDOWS EXECUTABLE:
============================

On a Windows machine, run:

1. Install Python 3.9+
2. Install dependencies:
   pip install pyinstaller flask requests python-dotenv

3. Build executable:
   pyinstaller --onefile --windowed --name=MaximoApp ^
   --add-data="frontend/templates;frontend/templates" ^
   --add-data="frontend/static;frontend/static" ^
   --add-data=".env;." ^
   --hidden-import=backend.auth.token_manager ^
   --hidden-import=backend.services.enhanced_profile_service ^
   --hidden-import=backend.services.enhanced_workorder_service ^
   --hidden-import=backend.api ^
   --hidden-import=dotenv ^
   app.py

4. Copy dist/MaximoApp.exe to this folder
5. Distribute the entire folder to users
""")
    
    print(f"✅ Windows package template created: {win_dir}/")
    return win_dir

def create_final_packages():
    """Create final distribution packages"""
    print("📦 Creating final distribution packages...")
    
    # Create macOS zip
    if os.path.exists('MaximoApp-Distribution'):
        print("📱 Creating macOS package...")
        with zipfile.ZipFile('MaximoApp-macOS.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk('MaximoApp-Distribution'):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, 'MaximoApp-Distribution')
                    zipf.write(file_path, f'MaximoApp-macOS/{arcname}')
        print("✅ Created: MaximoApp-macOS.zip")
    
    # Create Windows zip (template)
    if os.path.exists('MaximoApp-Windows'):
        print("🪟 Creating Windows package template...")
        with zipfile.ZipFile('MaximoApp-Windows-Template.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk('MaximoApp-Windows'):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, 'MaximoApp-Windows')
                    zipf.write(file_path, f'MaximoApp-Windows/{arcname}')
        print("✅ Created: MaximoApp-Windows-Template.zip")

def main():
    print("🏢 MAXIMO APPLICATION - UNIVERSAL BUILD")
    print("=" * 45)
    
    # Check if macOS build exists
    if not os.path.exists('MaximoApp-Distribution'):
        print("❌ macOS build not found. Run 'python3 build_simple.py' first")
        return
    
    # Create Windows package template
    create_windows_package()
    
    # Create final packages
    create_final_packages()
    
    print("\n🎉 BUILD COMPLETE!")
    print("=" * 20)
    print("📦 Distribution files created:")
    print("   📱 MaximoApp-macOS.zip (Ready to use)")
    print("   🪟 MaximoApp-Windows-Template.zip (Needs Windows build)")
    print()
    print("📋 NEXT STEPS:")
    print("1. For macOS: Send MaximoApp-macOS.zip to users")
    print("2. For Windows: Use GitHub Actions or build on Windows machine")
    print("3. Users just need to unzip and run!")

if __name__ == '__main__':
    main()

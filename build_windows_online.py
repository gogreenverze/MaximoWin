#!/usr/bin/env python3
"""
Build Windows executable using online CI/CD services
This script will trigger a build and download the Windows executable
"""

import os
import sys
import subprocess
import json
import time

def check_git_repo():
    """Check if we're in a git repository"""
    try:
        result = subprocess.run(['git', 'status'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def init_git_repo():
    """Initialize git repository if needed"""
    if not check_git_repo():
        print("📁 Initializing git repository...")
        subprocess.run(['git', 'init'], check=True)
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit for Maximo app'], check=True)
        print("✅ Git repository initialized")
        return True
    return False

def create_github_workflow():
    """Create optimized GitHub workflow for Windows build"""
    workflow_content = '''name: Build Windows Executable

on:
  push:
    branches: [ main, master ]
  workflow_dispatch:

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pyinstaller flask requests python-dotenv
    
    - name: Build Windows executable
      run: |
        pyinstaller --onefile --windowed --name=MaximoApp --add-data="frontend/templates;frontend/templates" --add-data="frontend/static;frontend/static" --add-data=".env;." --hidden-import=backend.auth.token_manager --hidden-import=backend.services.enhanced_profile_service --hidden-import=backend.services.enhanced_workorder_service --hidden-import=backend.api --hidden-import=dotenv app.py
    
    - name: Create Windows distribution package
      run: |
        mkdir MaximoApp-Windows-Ready
        copy dist\\MaximoApp.exe MaximoApp-Windows-Ready\\
        echo # Maximo Configuration > MaximoApp-Windows-Ready\\.env
        echo MAXIMO_BASE_URL=https://your-maximo-server.com/maximo >> MaximoApp-Windows-Ready\\.env
        echo MAXIMO_API_KEY=your_api_key_here >> MaximoApp-Windows-Ready\\.env
        echo MAXIMO_VERIFY_SSL=True >> MaximoApp-Windows-Ready\\.env
        echo FLASK_SECRET_KEY=maximo_secret_key >> MaximoApp-Windows-Ready\\.env
        echo APP_SECRET_KEY=app_secret_key >> MaximoApp-Windows-Ready\\.env
        echo DEBUG=False >> MaximoApp-Windows-Ready\\.env
        echo @echo off > MaximoApp-Windows-Ready\\run_maximo.bat
        echo echo Starting Maximo Application... >> MaximoApp-Windows-Ready\\run_maximo.bat
        echo echo The application will open in your web browser >> MaximoApp-Windows-Ready\\run_maximo.bat
        echo echo To stop the application, close this window >> MaximoApp-Windows-Ready\\run_maximo.bat
        echo echo. >> MaximoApp-Windows-Ready\\run_maximo.bat
        echo MaximoApp.exe >> MaximoApp-Windows-Ready\\run_maximo.bat
        echo pause >> MaximoApp-Windows-Ready\\run_maximo.bat
        echo MAXIMO APPLICATION FOR WINDOWS > MaximoApp-Windows-Ready\\README.txt
        echo =============================== >> MaximoApp-Windows-Ready\\README.txt
        echo. >> MaximoApp-Windows-Ready\\README.txt
        echo SETUP: >> MaximoApp-Windows-Ready\\README.txt
        echo 1. Edit .env file with your Maximo server details >> MaximoApp-Windows-Ready\\README.txt
        echo 2. Double-click run_maximo.bat to start >> MaximoApp-Windows-Ready\\README.txt
        echo 3. Application will open in your web browser >> MaximoApp-Windows-Ready\\README.txt
    
    - name: Upload Windows executable
      uses: actions/upload-artifact@v4
      with:
        name: MaximoApp-Windows-Ready
        path: MaximoApp-Windows-Ready/
        retention-days: 30
'''
    
    os.makedirs('.github/workflows', exist_ok=True)
    with open('.github/workflows/build-windows.yml', 'w') as f:
        f.write(workflow_content)
    
    print("✅ GitHub workflow created: .github/workflows/build-windows.yml")

def main():
    print("🪟 WINDOWS EXECUTABLE BUILDER")
    print("=" * 35)
    
    # Check if git is available
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
    except:
        print("❌ Git is not installed. Please install Git first.")
        return
    
    # Initialize git repo if needed
    init_git_repo()
    
    # Create GitHub workflow
    create_github_workflow()
    
    # Add and commit the workflow
    subprocess.run(['git', 'add', '.github/workflows/build-windows.yml'], check=True)
    try:
        subprocess.run(['git', 'commit', '-m', 'Add Windows build workflow'], check=True)
        print("✅ Workflow committed to git")
    except:
        print("ℹ️  Workflow already committed")
    
    print("\n🚀 NEXT STEPS TO GET WINDOWS EXECUTABLE:")
    print("=" * 45)
    print("1. Create a GitHub repository:")
    print("   - Go to https://github.com/new")
    print("   - Create a new repository (can be private)")
    print("   - Don't initialize with README (we have files already)")
    print()
    print("2. Push your code to GitHub:")
    print("   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git")
    print("   git branch -M main")
    print("   git push -u origin main")
    print()
    print("3. Trigger the build:")
    print("   - Go to your GitHub repo → Actions tab")
    print("   - Click 'Build Windows Executable'")
    print("   - Click 'Run workflow'")
    print()
    print("4. Download the Windows executable:")
    print("   - Wait 3-5 minutes for build to complete")
    print("   - Download 'MaximoApp-Windows-Ready' artifact")
    print("   - This will be a zip with the .exe file!")
    print()
    print("🎯 ALTERNATIVE: I can help you set up the GitHub repo if you want!")

if __name__ == '__main__':
    main()

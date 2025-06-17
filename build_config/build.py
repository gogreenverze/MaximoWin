#!/usr/bin/env python3
"""
Build script for creating Maximo Application executables
Supports both macOS and Windows platforms
"""

import os
import sys
import shutil
import subprocess
import platform
import argparse
from pathlib import Path

def get_platform_info():
    """Get current platform information"""
    system = platform.system().lower()
    arch = platform.machine().lower()
    
    if system == 'darwin':
        return 'macos', arch
    elif system == 'windows':
        return 'windows', arch
    elif system == 'linux':
        return 'linux', arch
    else:
        return system, arch

def clean_build_directories():
    """Clean previous build artifacts"""
    print("🧹 Cleaning previous build artifacts...")
    
    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.pyc']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"   Removed: {dir_name}/")
    
    # Clean pyc files recursively
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pyc'):
                os.remove(os.path.join(root, file))
        # Remove __pycache__ directories
        if '__pycache__' in dirs:
            shutil.rmtree(os.path.join(root, '__pycache__'))

def check_dependencies():
    """Check if all required dependencies are installed"""
    print("🔍 Checking dependencies...")

    # Map package names to import names
    required_packages = {
        'flask': 'flask',
        'requests': 'requests',
        'python-dotenv': 'dotenv',
        'pyinstaller': 'PyInstaller'
    }
    missing_packages = []

    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"   ✅ {package_name}")
        except ImportError:
            missing_packages.append(package_name)
            print(f"   ❌ {package_name}")

    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Please install them with: pip install -r requirements.txt")
        return False

    return True

def build_executable(debug=False, onefile=True):
    """Build the executable using PyInstaller"""
    platform_name, arch = get_platform_info()

    print(f"🔨 Building executable for {platform_name} ({arch})...")

    # When using a spec file, we don't pass --onefile/--onedir options
    # These are configured in the spec file itself
    cmd = ['pyinstaller']

    cmd.extend([
        '--clean',  # Clean PyInstaller cache
        '--noconfirm',  # Replace output directory without confirmation
        'MaximoApp.spec'  # Use our custom spec file
    ])

    print(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("   ✅ Build completed successfully!")
        if result.stdout:
            print("   Build output:")
            print("   " + "\n   ".join(result.stdout.split('\n')[-10:]))  # Show last 10 lines
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Build failed!")
        print(f"   Error: {e.stderr}")
        if e.stdout:
            print(f"   Output: {e.stdout}")
        return False

def create_distribution_package():
    """Create a distribution package with documentation"""
    platform_name, arch = get_platform_info()
    
    print("📦 Creating distribution package...")
    
    # Create distribution directory
    dist_dir = f"dist/MaximoApp-{platform_name}-{arch}"
    os.makedirs(dist_dir, exist_ok=True)
    
    # Copy executable
    if platform_name == 'macos':
        if os.path.exists('dist/MaximoApp.app'):
            shutil.copytree('dist/MaximoApp.app', f'{dist_dir}/MaximoApp.app')
        elif os.path.exists('dist/MaximoApp'):
            shutil.copy2('dist/MaximoApp', f'{dist_dir}/MaximoApp')
    else:
        if os.path.exists('dist/MaximoApp.exe'):
            shutil.copy2('dist/MaximoApp.exe', f'{dist_dir}/MaximoApp.exe')
        elif os.path.exists('dist/MaximoApp'):
            shutil.copy2('dist/MaximoApp', f'{dist_dir}/MaximoApp')
    
    # Copy documentation
    docs_to_copy = ['README.md', '.env.example']
    for doc in docs_to_copy:
        if os.path.exists(doc):
            shutil.copy2(doc, dist_dir)
    
    # Create .env.example if it doesn't exist
    env_example_path = f'{dist_dir}/.env.example'
    if not os.path.exists(env_example_path):
        with open(env_example_path, 'w') as f:
            f.write("""# Maximo API Credentials
MAXIMO_BASE_URL=https://your-maximo-server.com/maximo
MAXIMO_API_KEY=your_api_key_here
MAXIMO_VERIFY_SSL=True

# Flask Configuration
FLASK_SECRET_KEY=your_secret_key_here

# Application Configuration
APP_SECRET_KEY=your_app_secret_key_here
DEBUG=False
""")
    
    # Create installation instructions
    install_instructions = f'{dist_dir}/INSTALLATION.md'
    with open(install_instructions, 'w') as f:
        f.write(f"""# Maximo Application Installation

## System Requirements
- {platform_name.title()} operating system
- No additional software required (all dependencies are bundled)

## Installation Steps

1. **Extract the application** (if downloaded as a zip file)

2. **Configure the application**:
   - Copy `.env.example` to `.env`
   - Edit `.env` file with your Maximo server details:
     - `MAXIMO_BASE_URL`: Your Maximo server URL
     - `MAXIMO_API_KEY`: Your API key (optional, for enhanced performance)

3. **Run the application**:
""")
        
        if platform_name == 'macos':
            f.write("""   - Double-click `MaximoApp.app` to start
   - Or run from terminal: `./MaximoApp.app/Contents/MacOS/MaximoApp`
""")
        elif platform_name == 'windows':
            f.write("""   - Double-click `MaximoApp.exe` to start
   - Or run from command prompt: `MaximoApp.exe`
""")
        else:
            f.write("""   - Double-click `MaximoApp` to start (if GUI is available)
   - Or run from terminal: `./MaximoApp`
""")
        
        f.write("""
4. **First time setup**:
   - The application will open in your default web browser
   - Login with your Maximo credentials
   - The application runs locally on your computer

## Features
- Lightning-fast Maximo OAuth authentication
- Work order management and task handling
- Inventory search and material requests
- Offline database synchronization
- Mobile-first responsive design

## Troubleshooting
- If the application doesn't start, check the `.env` file configuration
- Ensure your Maximo server is accessible
- Check firewall settings if connection issues occur

## Support
For support, please refer to the README.md file or contact your system administrator.
""")
    
    print(f"   ✅ Distribution package created: {dist_dir}")
    return dist_dir

def main():
    """Main build function"""
    parser = argparse.ArgumentParser(description='Build Maximo Application executable')
    parser.add_argument('--debug', action='store_true', help='Build with debug console')
    parser.add_argument('--onedir', action='store_true', help='Build as directory instead of single file')
    parser.add_argument('--no-clean', action='store_true', help='Skip cleaning build directories')
    
    args = parser.parse_args()
    
    print("🏢 MAXIMO APPLICATION BUILD SCRIPT")
    print("=" * 50)
    
    # Change to project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    
    print(f"📁 Project directory: {project_root}")
    
    # Clean build directories
    if not args.no_clean:
        clean_build_directories()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Build executable
    onefile = not args.onedir
    if not build_executable(debug=args.debug, onefile=onefile):
        sys.exit(1)
    
    # Create distribution package
    dist_dir = create_distribution_package()
    
    print("\n🎉 Build completed successfully!")
    print(f"📦 Distribution package: {dist_dir}")
    print("\n📋 Next steps:")
    print("1. Test the executable on a clean system")
    print("2. Configure the .env file with your Maximo server details")
    print("3. Distribute the package to end users")

if __name__ == '__main__':
    main()

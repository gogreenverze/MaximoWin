#!/bin/bash
# Build script for macOS
# Creates a standalone .app bundle that can be distributed

set -e  # Exit on any error

echo "🍎 Building Maximo Application for macOS"
echo "========================================"

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script must be run on macOS"
    exit 1
fi

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "📁 Project directory: $PROJECT_ROOT"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is required but not installed"
    exit 1
fi

# Install/update dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

# Run the build script
echo "🔨 Starting build process..."
python3 build_config/build.py

# Check if build was successful
if [ -d "dist/MaximoApp.app" ]; then
    echo "✅ macOS app bundle created successfully!"
    
    # Make the app executable
    chmod +x "dist/MaximoApp.app/Contents/MacOS/MaximoApp"
    
    # Create a DMG file for easy distribution (optional)
    if command -v hdiutil &> /dev/null; then
        echo "📀 Creating DMG file for distribution..."
        
        # Create temporary directory for DMG contents
        DMG_DIR="dist/dmg_temp"
        mkdir -p "$DMG_DIR"
        
        # Copy app to DMG directory
        cp -R "dist/MaximoApp.app" "$DMG_DIR/"
        
        # Create Applications symlink
        ln -s /Applications "$DMG_DIR/Applications"
        
        # Create DMG
        DMG_NAME="MaximoApp-macOS-$(uname -m).dmg"
        hdiutil create -volname "Maximo Application" -srcfolder "$DMG_DIR" -ov -format UDZO "dist/$DMG_NAME"
        
        # Clean up
        rm -rf "$DMG_DIR"
        
        echo "✅ DMG created: dist/$DMG_NAME"
    fi
    
    echo ""
    echo "🎉 Build completed successfully!"
    echo "📱 App bundle: dist/MaximoApp.app"
    echo ""
    echo "📋 To test the application:"
    echo "   1. Double-click dist/MaximoApp.app"
    echo "   2. Or run: open dist/MaximoApp.app"
    echo ""
    echo "📋 To distribute:"
    echo "   1. Copy the entire MaximoApp.app bundle"
    echo "   2. Or use the DMG file if created"
    echo "   3. Include installation instructions"
    
else
    echo "❌ Build failed - app bundle not found"
    exit 1
fi

@echo off
REM Build script for Windows
REM Creates a standalone .exe that can be distributed

echo 🪟 Building Maximo Application for Windows
echo ==========================================

REM Get script directory and project root
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
cd /d "%PROJECT_ROOT%"

echo 📁 Project directory: %PROJECT_ROOT%

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is required but not installed
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if pip is available
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ pip is required but not installed
    pause
    exit /b 1
)

REM Install/update dependencies
echo 📦 Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

REM Run the build script
echo 🔨 Starting build process...
python build_config/build.py
if errorlevel 1 (
    echo ❌ Build failed
    pause
    exit /b 1
)

REM Check if build was successful
if exist "dist\MaximoApp.exe" (
    echo ✅ Windows executable created successfully!
    
    REM Create installer using NSIS if available
    where nsis >nul 2>&1
    if not errorlevel 1 (
        echo 📦 NSIS found - creating installer...
        REM Note: This would require an NSIS script
        echo ℹ️  NSIS installer creation not implemented yet
    )
    
    echo.
    echo 🎉 Build completed successfully!
    echo 📱 Executable: dist\MaximoApp.exe
    echo.
    echo 📋 To test the application:
    echo    1. Double-click dist\MaximoApp.exe
    echo    2. Or run from command prompt: dist\MaximoApp.exe
    echo.
    echo 📋 To distribute:
    echo    1. Copy MaximoApp.exe to target system
    echo    2. Include .env configuration file
    echo    3. Include installation instructions
    
) else (
    echo ❌ Build failed - executable not found
    pause
    exit /b 1
)

pause

# Maximo Application - Simple Distribution Guide

## ✅ COMPLETED: macOS Executable

Your macOS executable is ready! Here's what you have:

### Files Created:
- `MaximoApp-macOS.zip` - **Ready to distribute to macOS users**
- `MaximoApp-Windows-Template.zip` - Template for Windows build

## 📱 For macOS Users (Ready Now)

### What to send:
Just send the file: **`MaximoApp-macOS.zip`**

### User instructions:
1. **Download** `MaximoApp-macOS.zip`
2. **Double-click** to unzip
3. **Edit** `.env` file with Maximo server details:
   ```
   MAXIMO_BASE_URL=https://your-maximo-server.com/maximo
   MAXIMO_API_KEY=your_api_key_here
   ```
4. **Double-click** `MaximoApp` to run
5. **Application opens** in web browser automatically

### If macOS blocks the app:
- Right-click `MaximoApp` → "Open" → "Open" (first time only)

## 🪟 For Windows Users (2 Options)

### Option 1: GitHub Actions (Recommended - No Windows Machine Needed)

1. **Push your code to GitHub**
2. **Go to Actions tab** in your GitHub repository
3. **Run the "Build Maximo App" workflow**
4. **Download** the Windows artifact when complete
5. **Send to Windows users**

### Option 2: Build on Windows Machine

1. **Copy your project** to a Windows machine
2. **Install Python 3.9+** on Windows
3. **Run these commands:**
   ```cmd
   pip install pyinstaller flask requests python-dotenv
   
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
   ```
4. **Copy** `dist/MaximoApp.exe` to the Windows template folder
5. **Zip and distribute**

## 🚀 Quick Commands Summary

### Build macOS (Already Done):
```bash
python3 build_simple.py
python3 build_all.py
```

### Build Windows via GitHub:
1. Push code to GitHub
2. Enable GitHub Actions
3. Download artifacts

### Test the macOS app:
```bash
cd MaximoApp-Distribution
./MaximoApp
```

## 📦 Final Distribution Structure

### macOS Package (`MaximoApp-macOS.zip`):
```
MaximoApp-macOS/
├── MaximoApp          # Executable (16MB)
├── .env              # Configuration file
└── README.txt        # User instructions
```

### Windows Package (after build):
```
MaximoApp-Windows/
├── MaximoApp.exe     # Executable
├── run_maximo.bat    # Easy launcher
├── .env              # Configuration file
└── README.txt        # User instructions
```

## 🎯 User Experience

### macOS:
1. Download zip file
2. Unzip
3. Edit .env file
4. Double-click MaximoApp
5. Browser opens automatically

### Windows:
1. Download zip file
2. Unzip
3. Edit .env file
4. Double-click run_maximo.bat (or MaximoApp.exe)
5. Browser opens automatically

## ✅ What's Included in Each Executable

- ✅ Python interpreter
- ✅ Flask web framework
- ✅ All your application code
- ✅ All templates and static files
- ✅ All Python dependencies
- ✅ SQLite database support
- ✅ Automatic browser opening
- ✅ Local-only web server (secure)

## 🔧 No Installation Required

Users need **ZERO** additional software:
- ❌ No Python installation
- ❌ No pip packages
- ❌ No command line usage
- ❌ No technical setup
- ✅ Just download, configure, and run!

## 📊 File Sizes

- **macOS executable**: ~16MB
- **Windows executable**: ~15-20MB (estimated)
- **Total download**: ~16-20MB per platform

## 🎉 You're Done!

Your Maximo application is now packaged as standalone executables. Users can run it with just 2-3 simple steps, and it works exactly like a native desktop application while providing the full web interface experience.

# Maximo Application Build System

This directory contains the build configuration and scripts for creating standalone executables of the Maximo Application.

## Overview

The build system uses PyInstaller to create self-contained executables that include:
- Python interpreter
- All Python dependencies (Flask, requests, etc.)
- Application code and templates
- Static files (CSS, JS, images)
- Configuration files

## Build Files

### Core Build Files
- `MaximoApp.spec` - PyInstaller specification file (customized for Flask)
- `startup.py` - Application startup script for packaged executables
- `build.py` - Cross-platform Python build script

### Platform-Specific Scripts
- `build_macos.sh` - macOS build script (creates .app bundle and optional DMG)
- `build_windows.bat` - Windows build script (creates .exe)

## Quick Start

### Prerequisites
1. Python 3.7+ installed
2. All dependencies installed: `pip install -r requirements.txt`

### Building on macOS
```bash
# Option 1: Use the macOS-specific script
./build_config/build_macos.sh

# Option 2: Use the cross-platform script
python3 build_config/build.py

# Option 3: Use PyInstaller directly
pyinstaller MaximoApp.spec
```

### Building on Windows
```batch
REM Option 1: Use the Windows-specific script
build_config\build_windows.bat

REM Option 2: Use the cross-platform script
python build_config\build.py

REM Option 3: Use PyInstaller directly
pyinstaller MaximoApp.spec
```

## Build Options

### Debug vs Production
- **Debug build**: `python build.py --debug` (shows console window)
- **Production build**: `python build.py` (no console window)

### Single File vs Directory
- **Single file**: Default (easier distribution)
- **Directory**: `python build.py --onedir` (faster startup)

## Output Structure

After building, you'll find:

```
dist/
├── MaximoApp                    # Standalone executable (Linux/macOS)
├── MaximoApp.exe               # Standalone executable (Windows)
├── MaximoApp.app/              # macOS app bundle
└── MaximoApp-{platform}-{arch}/ # Distribution package
    ├── MaximoApp.app/          # Application
    ├── .env.example            # Configuration template
    ├── INSTALLATION.md         # Installation instructions
    └── README.md               # Application documentation
```

## Configuration

### Environment Variables
The application requires a `.env` file with:
```
MAXIMO_BASE_URL=https://your-maximo-server.com/maximo
MAXIMO_API_KEY=your_api_key_here
MAXIMO_VERIFY_SSL=True
FLASK_SECRET_KEY=your_secret_key_here
APP_SECRET_KEY=your_app_secret_key_here
DEBUG=False
```

### Customizing the Build

#### Adding Files to the Bundle
Edit `MaximoApp.spec` and add to the `datas` list:
```python
datas = [
    ('path/to/source', 'destination/in/bundle'),
    # ... existing entries
]
```

#### Adding Hidden Imports
If PyInstaller misses some imports, add them to `hiddenimports`:
```python
hiddenimports = [
    'your.missing.module',
    # ... existing entries
]
```

#### Excluding Packages
To reduce bundle size, add unwanted packages to `excludes`:
```python
excludes = [
    'unwanted_package',
    # ... existing entries
]
```

## Troubleshooting

### Common Issues

#### 1. Missing Dependencies
**Error**: `ModuleNotFoundError` when running the executable
**Solution**: Add the missing module to `hiddenimports` in the spec file

#### 2. Large Executable Size
**Solutions**:
- Add unused packages to `excludes` in the spec file
- Use `--onedir` instead of `--onefile` for faster startup
- Enable UPX compression (already enabled in spec file)

#### 3. Template/Static Files Not Found
**Error**: Flask template or static file errors
**Solution**: Verify paths in the `datas` section of the spec file

#### 4. Permission Denied (macOS)
**Error**: "App can't be opened because it is from an unidentified developer"
**Solutions**:
- Right-click the app and select "Open"
- Or run: `xattr -cr dist/MaximoApp.app`
- For distribution: Code sign the application

#### 5. Windows Antivirus False Positives
**Issue**: Antivirus software flags the executable
**Solutions**:
- Submit the executable to antivirus vendors for whitelisting
- Code sign the executable
- Build with `--debug` to show console (less likely to be flagged)

### Debug Mode
For troubleshooting, build with debug mode:
```bash
python build_config/build.py --debug
```

This will:
- Show console output
- Display detailed error messages
- Allow you to see what's happening during startup

## Distribution

### macOS Distribution
1. **App Bundle**: Distribute the entire `MaximoApp.app` folder
2. **DMG**: Use the generated DMG file for easier installation
3. **Code Signing**: For wider distribution, code sign the app:
   ```bash
   codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" MaximoApp.app
   ```

### Windows Distribution
1. **Executable**: Distribute the `MaximoApp.exe` file
2. **Installer**: Create an NSIS installer for professional distribution
3. **Code Signing**: Sign the executable for trust:
   ```cmd
   signtool sign /f certificate.p12 /p password MaximoApp.exe
   ```

### Cross-Platform Notes
- Include platform-specific installation instructions
- Test on clean systems without Python installed
- Provide the `.env.example` file for configuration
- Include troubleshooting documentation

## Performance Optimization

### Startup Time
- Use `--onedir` for faster startup (but larger distribution)
- Minimize hidden imports
- Exclude unnecessary packages

### Bundle Size
- Use `excludes` to remove unused packages
- Enable UPX compression (already enabled)
- Consider using `--strip` for smaller binaries

### Runtime Performance
- The packaged application runs at near-native speed
- Flask development server is replaced with production settings
- Database operations are unaffected by packaging

## Security Considerations

### Code Protection
- PyInstaller provides basic obfuscation
- For sensitive applications, consider additional protection tools
- Environment variables are still readable in the bundle

### Distribution Security
- Code sign executables for trust
- Use HTTPS for download distribution
- Provide checksums for integrity verification

## Maintenance

### Updating the Application
1. Update the source code
2. Update version numbers in relevant files
3. Rebuild the executable
4. Test on target platforms
5. Distribute the new version

### Dependency Updates
1. Update `requirements.txt`
2. Test the application
3. Rebuild and test the executable
4. Update documentation if needed

## Support

For build-related issues:
1. Check this documentation
2. Review PyInstaller documentation
3. Check the application logs
4. Test with debug mode enabled

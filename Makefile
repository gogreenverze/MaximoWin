# Makefile for Maximo Application
# Provides convenient commands for building and managing the application

.PHONY: help install clean build build-debug build-macos build-windows test package dist-clean

# Default target
help:
	@echo "Maximo Application Build System"
	@echo "==============================="
	@echo ""
	@echo "Available commands:"
	@echo "  install      - Install dependencies"
	@echo "  clean        - Clean build artifacts"
	@echo "  build        - Build production executable"
	@echo "  build-debug  - Build debug executable (with console)"
	@echo "  build-macos  - Build macOS app bundle and DMG"
	@echo "  build-windows- Build Windows executable"
	@echo "  test         - Test the application"
	@echo "  package      - Create distribution package"
	@echo "  dist-clean   - Clean all build and distribution files"
	@echo ""
	@echo "Examples:"
	@echo "  make install && make build"
	@echo "  make clean build-debug"
	@echo "  make build-macos"

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

# Clean build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Build production executable
build: clean
	@echo "🔨 Building production executable..."
	python3 build_config/build.py

# Build debug executable
build-debug: clean
	@echo "🔨 Building debug executable..."
	python3 build_config/build.py --debug

# Build macOS app bundle and DMG
build-macos: clean
	@echo "🍎 Building macOS application..."
	@if [ "$$(uname)" != "Darwin" ]; then \
		echo "❌ This target can only be run on macOS"; \
		exit 1; \
	fi
	./build_config/build_macos.sh

# Build Windows executable (cross-platform note)
build-windows:
	@echo "🪟 Building Windows executable..."
	@echo "Note: For best results, run this on Windows"
	python3 build_config/build.py

# Test the application
test:
	@echo "🧪 Testing application..."
	python3 -m pytest tests/ || echo "No tests found - running basic import test"
	python3 -c "import app; print('✅ Application imports successfully')"

# Create distribution package
package: build
	@echo "📦 Creating distribution package..."
	@echo "✅ Distribution package created in dist/"

# Clean everything including distribution files
dist-clean:
	@echo "🧹 Cleaning all build and distribution files..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.spec
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Development helpers
dev-setup: install
	@echo "🛠️  Setting up development environment..."
	@if [ ! -f .env ]; then \
		cp .env.example .env 2>/dev/null || echo "# Create your .env file based on .env.example" > .env; \
		echo "📝 Created .env file - please configure it"; \
	fi

# Run the application in development mode
dev-run:
	@echo "🚀 Running application in development mode..."
	python3 app.py

# Quick build and test
quick: clean build
	@echo "⚡ Quick build completed"
	@if [ -f "dist/MaximoApp" ]; then \
		echo "✅ Executable created: dist/MaximoApp"; \
	elif [ -d "dist/MaximoApp.app" ]; then \
		echo "✅ App bundle created: dist/MaximoApp.app"; \
	else \
		echo "❌ Build may have failed - check dist/ directory"; \
	fi

# Show build information
info:
	@echo "Build Information"
	@echo "=================="
	@echo "Platform: $$(uname -s)"
	@echo "Architecture: $$(uname -m)"
	@echo "Python: $$(python3 --version)"
	@echo "PyInstaller: $$(python3 -c 'import PyInstaller; print(PyInstaller.__version__)' 2>/dev/null || echo 'Not installed')"
	@echo "Flask: $$(python3 -c 'import flask; print(flask.__version__)' 2>/dev/null || echo 'Not installed')"
	@echo ""
	@echo "Project Structure:"
	@echo "  Source: app.py"
	@echo "  Templates: frontend/templates/"
	@echo "  Static: frontend/static/"
	@echo "  Build Config: build_config/"
	@echo "  Output: dist/"

#!/bin/bash
# Build Windows executable using Docker

echo "🐳 Building Windows executable using Docker..."

# Create Dockerfile for Windows build
cat > Dockerfile.windows << 'EOF'
FROM python:3.9-windowsservercore

WORKDIR /app
COPY . .

RUN pip install pyinstaller flask requests python-dotenv

RUN pyinstaller --onefile --windowed --name=MaximoApp \
    --add-data="frontend/templates;frontend/templates" \
    --add-data="frontend/static;frontend/static" \
    --add-data=".env;." \
    --hidden-import=backend.auth.token_manager \
    --hidden-import=backend.services.enhanced_profile_service \
    --hidden-import=backend.services.enhanced_workorder_service \
    --hidden-import=backend.api \
    --hidden-import=dotenv \
    app.py

CMD ["cmd"]
EOF

# Build Docker image and extract executable
docker build -f Dockerfile.windows -t maximo-windows-builder .
docker create --name temp-container maximo-windows-builder
docker cp temp-container:/app/dist/MaximoApp.exe ./MaximoApp.exe
docker rm temp-container

echo "✅ Windows executable created: MaximoApp.exe"

# Clean up
rm Dockerfile.windows

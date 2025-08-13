#!/bin/bash
set -e

echo "🚀 FinKubeOps Production Startup"
echo "==============================="

cd /home/site/wwwroot

# Set port from Azure
export PORT=${HTTP_PLATFORM_PORT:-8000}

# Build React frontend for production
if [ -f "package.json" ]; then
    echo "📦 Building React frontend..."
    npm install --production
    npm run build
    npm start
    
    if [ -d "build" ]; then
        echo "✅ React build completed"
    else
        echo "⚠️ React build failed"
    fi
fi

# Setup Python environment
echo "🐍 Setting up Python environment..."
if [ -d "antenv" ]; then
    source antenv/bin/activate
elif [ -d "__oryx_prod_venv" ]; then
    source __oryx_prod_venv/bin/activate
fi

# Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo "📦 Installing Python dependencies..."
    pip install -r requirements.txt
fi

# Start your server exactly as you want
echo "🎯 Starting uvicorn mcp_server:app on port $PORT"
exec uvicorn mcp_server:app --host 0.0.0.0 --port $PORT --log-level info

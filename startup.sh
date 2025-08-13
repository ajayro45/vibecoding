#!/bin/bash
set -e

echo "�� Starting FinKubeOps from GitHub deployment..."

# Set environment variables for Azure App Service
export PYTHONPATH="/home/site/wwwroot"
export PORT=${HTTP_PLATFORM_PORT:-8000}

cd /home/site/wwwroot

# Use Azure's Python environment (Oryx creates this)
if [ -d "antenv" ]; then
    echo "📦 Activating Azure Python environment..."
    source antenv/bin/activate
elif [ -d "__oryx_prod_venv" ]; then
    echo "📦 Activating Oryx Python environment..."
    source __oryx_prod_venv/bin/activate
else
    echo "📦 Using system Python..."
fi

# Ensure dependencies are installed
python -m pip list | grep fastapi || pip install -r requirements.txt

# Start the application
echo "🎯 Starting FinKubeOps server on port $PORT..."

# Try to start your main application
if [ -f "paste-2.py" ]; then
    echo "✅ Found paste-2.py, starting main application..."
    exec python paste-2.py
elif [ -f "main.py" ]; then
    echo "✅ Found main.py, starting application..."
    exec python main.py
else
    echo "⚠️ No main application file found, starting fallback..."
    exec python app.py
fi

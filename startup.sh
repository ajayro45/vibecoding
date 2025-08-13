#!/bin/bash
set -e

echo "🚀 FinKubeOps Production Startup"
echo "==============================="
echo "📊 Backend: uvicorn main:app"
echo "⚛️ Frontend: React build served by FastAPI"
echo ""

# Find the correct working directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
APP_DIR="/home/site/wwwroot"

# Check if we're in an Oryx build environment
if [ ! -z "$APP_PATH" ]; then
    APP_DIR="$APP_PATH"
    echo "📁 Using Oryx APP_PATH: $APP_DIR"
elif [ -f "/tmp/8ddda*/main.py" ]; then
    APP_DIR=$(dirname $(find /tmp -name "main.py" 2>/dev/null | head -1))
    echo "📁 Found app in temp directory: $APP_DIR"
fi

cd "$APP_DIR"

# Set environment variables
export PYTHONPATH="$APP_DIR"
export PORT=${HTTP_PLATFORM_PORT:-8000}

echo "📁 Current directory: $(pwd)"
echo "📋 Available files:"
ls -la

# Function to build React frontend
build_react() {
    if [ -f "package.json" ]; then
        echo "📦 Building React frontend for production..."
        
        # Check Node.js version
        if command -v node &> /dev/null; then
            echo "📦 Node.js version: $(node --version)"
            echo "📦 NPM version: $(npm --version)"
        else
            echo "❌ Node.js not found, skipping React build"
            return 0
        fi
        
        # Install dependencies if needed
        if [ ! -d "node_modules" ]; then
            echo "📦 Installing Node.js dependencies..."
            npm install --production --silent
        fi
        
        # Build React app
        echo "🔨 Building React app..."
        export GENERATE_SOURCEMAP=false
        export CI=false
        
        if npm run build; then
            echo "✅ React build completed successfully"
            if [ -d "build" ]; then
                echo "📊 Build size: $(du -sh build/ | cut -f1)"
            fi
        else
            echo "⚠️ React build failed, continuing with Python backend only"
        fi
    else
        echo "⚠️ No package.json found, skipping React build"
    fi
}

# Function to setup and start Python backend
start_python_backend() {
    echo "🐍 Setting up Python backend..."
    
    # Find and activate the virtual environment
    VENV_ACTIVATED=false
    
    # Try different venv locations
    for venv_path in "$APP_DIR/antenv" "$APP_DIR/__oryx_prod_venv" "/tmp/8ddda*/antenv"; do
        if [ -d "$venv_path" ] && [ -f "$venv_path/bin/activate" ]; then
            echo "📦 Activating virtual environment: $venv_path"
            source "$venv_path/bin/activate"
            VENV_ACTIVATED=true
            break
        fi
    done
    
    if [ "$VENV_ACTIVATED" = false ]; then
        echo "📦 No virtual environment found, using system Python"
    fi
    
    # Show Python info
    echo "🐍 Python version: $(python3 --version 2>/dev/null || python --version)"
    echo "📦 Pip version: $(pip --version)"
    echo "🔍 Python path: $(which python3 2>/dev/null || which python)"
    
    # Install dependencies if requirements.txt exists
    if [ -f "requirements.txt" ]; then
        echo "📦 Installing Python dependencies..."
        pip install -r requirements.txt --quiet
        echo "✅ Python dependencies installed"
    else
        echo "⚠️ No requirements.txt found"
    fi
    
    # Verify main.py exists
    if [ -f "main.py" ]; then
        echo "✅ Found main.py"
        echo "📋 main.py preview:"
        head -5 main.py
        
        # Start the backend server
        echo "🎯 Starting uvicorn on port $PORT"
        echo "🌐 Command: python -m uvicorn main:app --host 0.0.0.0 --port $PORT --log-level info"
        
        # Use exec to replace the shell process
        exec python -m uvicorn main:app --host 0.0.0.0 --port $PORT --log-level info
        
    else
        echo "❌ main.py not found!"
        echo "📋 Available Python files:"
        find . -name "*.py" -type f 2>/dev/null || echo "No Python files found"
        echo "📁 Directory contents:"
        ls -la
        exit 1
    fi
}

# Main execution flow
echo "🚀 Starting build and deployment process..."

# Step 1: Build React frontend (non-blocking)
build_react

# Step 2: Start Python backend (this will run indefinitely)
start_python_backend

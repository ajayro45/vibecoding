#!/bin/bash
set -e

echo "🚀 FinKubeOps Production Startup"
echo "==============================="
echo "📊 Backend: uvicorn main:app"
echo "⚛️ Frontend: React build served by FastAPI"
echo ""

cd /home/site/wwwroot

# Set environment variables
export PYTHONPATH="/home/site/wwwroot"
export PORT=${HTTP_PLATFORM_PORT:-8000}

echo "📁 Current directory: $(pwd)"
echo "📋 Available files:"
ls -la

# Build React frontend for production
build_react() {
    if [ -f "package.json" ]; then
        echo "📦 Building React frontend for production..."
        
        # Install Node.js dependencies
        if [ ! -d "node_modules" ]; then
            echo "📦 Installing Node.js dependencies..."
            npm install --production
        fi
        
        # Build React app
        echo "🔨 Building React app..."
        export GENERATE_SOURCEMAP=false
        export CI=false
        npm run build
        
        if [ -d "build" ]; then
            echo "✅ React build completed successfully"
            echo "📊 Build size: $(du -sh build/ | cut -f1)"
            echo "📋 Build contents:"
            ls -la build/
        else
            echo "❌ React build failed"
            return 1
        fi
    else
        echo "⚠️ No package.json found, skipping React build"
    fi
}

# Setup Python environment and start backend
start_python_backend() {
    echo "🐍 Setting up Python backend..."
    
    # Activate Python environment
    if [ -d "antenv" ]; then
        echo "📦 Activating antenv..."
        source antenv/bin/activate
    elif [ -d "__oryx_prod_venv" ]; then
        echo "📦 Activating Oryx virtual environment..."
        source __oryx_prod_venv/bin/activate
    else
        echo "📦 Using system Python..."
    fi
    
    # Show Python info
    echo "🐍 Python version: $(python3 --version)"
    echo "📦 Pip version: $(pip --version)"
    
    # Install Python dependencies
    if [ -f "requirements.txt" ]; then
        echo "📦 Installing Python dependencies..."
        pip install -r requirements.txt
        echo "✅ Python dependencies installed"
    else
        echo "⚠️ No requirements.txt found"
    fi
    
    # Verify main.py exists
    if [ -f "main.py" ]; then
        echo "✅ Found main.py"
        
        # Check if main.py has FastAPI app
        if grep -q "app.*FastAPI" main.py; then
            echo "✅ Found FastAPI app in main.py"
        else
            echo "⚠️ Warning: No FastAPI app found in main.py"
        fi
        
        # Start the backend server
        echo "🎯 Starting uvicorn main:app on port $PORT"
        echo "🌐 Command: uvicorn main:app --host 0.0.0.0 --port $PORT --log-level info"
        
        exec uvicorn main:app --host 0.0.0.0 --port $PORT --log-level info
        
    else
        echo "❌ main.py not found!"
        echo "📋 Available Python files:"
        ls -la *.py 2>/dev/null || echo "No Python files found"
        ls -lrt ../
        ls -lrt ../../
        ls -lrt ../../../
        exit 1
    fi
}

# Main execution
echo "🚀 Starting build and deployment process..."

# Step 1: Build React frontend
build_react

# Step 2: Start Python backend (this will serve both API and React)
start_python_backend

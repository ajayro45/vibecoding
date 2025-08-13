#!/bin/bash

echo "🧪 Testing FinKubeOps setup locally..."

# Check if files exist
echo "📁 Checking required files..."
files=("requirements.txt" "package.json" "startup.sh" "app.py" "src/App.js" "public/index.html")
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file (missing)"
    fi
done

# Check Python dependencies
echo ""
echo "🐍 Testing Python dependencies..."
if python3 -c "import fastapi, uvicorn; print('✅ Core dependencies OK')"; then
    echo "✅ Python environment ready"
else
    echo "❌ Python dependencies missing. Run: pip install -r requirements.txt"
fi

# Check Node.js dependencies
echo ""
echo "📦 Testing Node.js setup..."
if [ -d "node_modules" ]; then
    echo "✅ Node modules installed"
else
    echo "⚠️ Node modules not installed. Run: npm install"
fi

echo ""
echo "🎯 To test locally:"
echo "1. pip install -r requirements.txt"
echo "2. npm install"
echo "3. npm run build"
echo "4. python app.py"
echo "5. Open http://localhost:8000"

#!/bin/bash

# Fixed GitHub Repository Setup Script for FinKubeOps Azure App Service
# This creates all necessary files for GitHub → Azure App Service deployment

set -e

echo "🚀 Setting up GitHub repository for Azure App Service deployment..."
echo "=================================================================="

# Create directory structure
echo "📁 Creating directory structure..."
mkdir -p public src .github/workflows

# 1. requirements.txt
echo "📝 Creating requirements.txt..."
cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
websockets==12.0
python-multipart==0.0.6
azure-identity==1.15.0
azure-mgmt-costmanagement==4.0.1
azure-mgmt-resource==23.1.0
kubernetes==28.1.0
openai==1.3.9
aiohttp==3.9.1
aiofiles==23.2.1
requests==2.31.0
pydantic==2.5.1
pydantic-settings==2.1.0
python-dotenv==1.0.0
PyYAML==6.0.1
python-json-logger==2.0.7
python-dateutil==2.8.2
pytz==2023.3
tenacity==8.2.3
gunicorn==21.2.0
EOF

# 2. package.json
echo "📝 Creating package.json..."
cat > package.json << 'EOF'
{
  "name": "finkubeops",
  "version": "2.0.0",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-scripts": "5.0.1",
    "lucide-react": "^0.263.1",
    "recharts": "^2.8.0"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "GENERATE_SOURCEMAP=false react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  },
  "engines": {
    "node": "18.x",
    "npm": "9.x"
  },
  "browserslist": {
    "production": [">0.2%", "not dead", "not op_mini all"],
    "development": ["last 1 chrome version", "last 1 firefox version", "last 1 safari version"]
  }
}
EOF

# 3. startup.sh
echo "📝 Creating startup.sh..."
cat > startup.sh << 'EOF'
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
EOF

chmod +x startup.sh

# 4. app.py (fallback application)
echo "📝 Creating app.py..."
cat > app.py << 'PYEOF'
#!/usr/bin/env python3
"""
FinKubeOps Fallback Application for Azure App Service
"""

import os
import sys
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Azure App Service configuration
PORT = int(os.environ.get('HTTP_PLATFORM_PORT', os.environ.get('PORT', 8000)))
HOST = os.environ.get('HOST', '0.0.0.0')

logger.info(f"🚀 FinKubeOps fallback starting on {HOST}:{PORT}")

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    
    app = FastAPI(
        title="FinKubeOps",
        description="AI-Powered Kubernetes FinOps Platform",
        version="2.0.0"
    )
    
    # Add CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Serve React build if it exists
    if os.path.exists("build"):
        app.mount("/static", StaticFiles(directory="build/static"), name="static")
        logger.info("✅ Serving React static files")
    
    @app.get("/api/health")
    async def health():
        return {
            "status": "healthy",
            "message": "FinKubeOps running on Azure App Service",
            "version": "2.0.0",
            "port": PORT,
            "timestamp": datetime.now().isoformat(),
            "environment": "Azure App Service",
            "deployment": "GitHub Auto-Deploy"
        }
    
    @app.get("/api/status")
    async def get_status():
        return {
            "application": "FinKubeOps",
            "status": "running",
            "deployment_method": "GitHub → Azure App Service",
            "python_version": sys.version,
            "files_present": {
                "paste-2.py": os.path.exists("paste-2.py"),
                "main.py": os.path.exists("main.py"),
                "react_build": os.path.exists("build"),
                "requirements.txt": os.path.exists("requirements.txt")
            },
            "environment_vars": {
                "AZURE_SUBSCRIPTION_ID": bool(os.getenv('AZURE_SUBSCRIPTION_ID')),
                "AZURE_OPENAI_ENDPOINT": bool(os.getenv('AZURE_OPENAI_ENDPOINT')),
                "PORT": PORT
            }
        }
    
    @app.get("/")
    async def root():
        # Serve React app if available
        if os.path.exists("build/index.html"):
            with open("build/index.html", "r") as f:
                content = f.read()
                return HTMLResponse(content=content)
        
        # Otherwise show status page
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FinKubeOps - Azure App Service</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh; color: white;
                }
                .container { max-width: 800px; margin: 0 auto; }
                .card { background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; margin: 20px 0; }
                .success { background: rgba(34, 197, 94, 0.2); }
                .warning { background: rgba(251, 191, 36, 0.2); }
                .info { background: rgba(59, 130, 246, 0.2); }
                a { color: #60a5fa; text-decoration: none; }
                ul { text-align: left; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 FinKubeOps</h1>
                <h2>AI-Powered Kubernetes FinOps Platform</h2>
                
                <div class="card success">
                    <h3>✅ Deployment Successful</h3>
                    <p>Your application is running on Azure App Service!</p>
                </div>
                
                <div class="card warning">
                    <h3>⚠️ Setup Required</h3>
                    <p>To enable full functionality:</p>
                    <ul>
                        <li>Add your paste-2.txt as paste-2.py to the repo</li>
                        <li>Add your paste.txt as src/App.js to the repo</li>
                        <li>Configure environment variables in Azure Portal</li>
                    </ul>
                </div>
                
                <div class="card info">
                    <h3>🔗 Available Endpoints</h3>
                    <p><a href="/api/health">Health Check</a> | <a href="/docs">API Docs</a></p>
                </div>
            </div>
        </body>
        </html>
        """)
    
    if __name__ == "__main__":
        logger.info(f"🎯 Starting server on {HOST}:{PORT}")
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
        
except Exception as e:
    logger.error(f"❌ Application failed to start: {e}")
    print(f"Error: {e}")
    sys.exit(1)
PYEOF

# 5. web.config
echo "📝 Creating web.config..."
cat > web.config << 'XMLEOF'
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="httpPlatformHandler" path="*" verb="*" modules="httpPlatformHandler" resourceType="Unspecified"/>
    </handlers>
    <httpPlatform processPath="%HOME%\site\wwwroot\startup.sh"
                  arguments=""
                  stdoutLogEnabled="true"
                  stdoutLogFile="%HOME%\LogFiles\stdout"
                  startupTimeLimit="60"
                  startupRetryCount="3">
      <environmentVariables>
        <environmentVariable name="PORT" value="%HTTP_PLATFORM_PORT%" />
        <environmentVariable name="PYTHONPATH" value="%HOME%\site\wwwroot" />
      </environmentVariables>
    </httpPlatform>
    <rewrite>
      <rules>
        <rule name="API Routes" stopProcessing="true">
          <match url="^api/(.*)" />
          <action type="None" />
        </rule>
        <rule name="React Router" stopProcessing="true">
          <match url=".*" />
          <conditions logicalGrouping="MatchAll">
            <add input="{REQUEST_FILENAME}" matchType="IsFile" negate="true" />
            <add input="{REQUEST_URI}" pattern="^/api/" negate="true" />
          </conditions>
          <action type="Rewrite" url="build/index.html" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
XMLEOF

# 6. .deployment
echo "📝 Creating .deployment..."
cat > .deployment << 'DEPEOF'
[config]
SCM_DO_BUILD_DURING_DEPLOYMENT=true
ENABLE_ORYX_BUILD=true
DEPEOF

# 7. React files
echo "📝 Creating React files..."

# public/index.html
cat > public/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta name="description" content="AI-Powered Kubernetes FinOps Platform" />
    <title>FinKubeOps</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
HTMLEOF

# src/index.js
cat > src/index.js << 'JSEOF'
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
JSEOF

# src/index.css
cat > src/index.css << 'CSSEOF'
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
CSSEOF

# src/App.js (placeholder)
cat > src/App.js << 'REACTEOF'
import React, { useState, useEffect } from 'react';

function App() {
  const [status, setStatus] = useState('loading');
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch('/api/health')
      .then(res => res.json())
      .then(data => {
        setStatus('connected');
        setData(data);
      })
      .catch(err => {
        setStatus('error');
        console.error('Backend connection failed:', err);
      });
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-5xl font-bold mb-4">🚀 FinKubeOps</h1>
          <p className="text-xl text-slate-300">AI-Powered Kubernetes FinOps Platform</p>
          <p className="text-sm text-yellow-300 mt-2">
            ⚠️ Replace this file with your paste.txt content
          </p>
        </div>

        <div className="bg-slate-800/50 rounded-2xl p-8 mb-8">
          <h2 className="text-2xl font-semibold mb-4">System Status</h2>
          
          <div className="flex items-center mb-4">
            <div className={`w-3 h-3 rounded-full mr-3 ${
              status === 'connected' ? 'bg-green-400' : 
              status === 'error' ? 'bg-red-400' : 'bg-yellow-400'
            }`}></div>
            <span className="text-lg">
              Backend: {status === 'connected' ? 'Connected' : 
                       status === 'error' ? 'Disconnected' : 'Connecting...'}
            </span>
          </div>

          {data && (
            <div className="bg-slate-900/50 rounded-xl p-4 mb-4">
              <pre className="text-sm text-slate-300">
                {JSON.stringify(data, null, 2)}
              </pre>
            </div>
          )}

          <div className="text-center">
            <a href="/docs" className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg mr-4 inline-block">
              📚 API Documentation
            </a>
            <a href="/api/status" className="bg-green-600 hover:bg-green-700 px-6 py-3 rounded-lg inline-block">
              📊 Status
            </a>
          </div>
        </div>

        <div className="bg-yellow-900/20 border border-yellow-600/30 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-yellow-300 mb-2">🔧 Setup Instructions</h3>
          <ol className="text-sm text-yellow-100 space-y-1">
            <li>1. Replace src/App.js with your paste.txt content</li>
            <li>2. Add paste-2.txt as paste-2.py to the repository</li>
            <li>3. Configure environment variables in Azure Portal</li>
            <li>4. Push changes to GitHub for automatic deployment</li>
          </ol>
        </div>
      </div>
    </div>
  );
}

export default App;
REACTEOF

# 8. .gitignore
echo "📝 Creating .gitignore..."
cat > .gitignore << 'GITEOF'
# Dependencies
node_modules/
__pycache__/
*.pyc

# Build outputs  
/build
/dist

# Environment variables
.env*

# Logs
*.log

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
GITEOF

# 9. README.md
echo "📝 Creating README.md..."
cat > README.md << 'READMEEOF'
# FinKubeOps - Azure App Service

�� AI-Powered Kubernetes FinOps Platform with GitHub auto-deployment.

## Quick Setup

### 1. Add Your Files
```bash
# Replace placeholder with your actual React component
cp paste.txt src/App.js

# Add your Python backend
cp paste-2.txt paste-2.py
```

### 2. Push to GitHub
```bash
git add .
git commit -m "Add FinKubeOps application"
git push origin main
```

### 3. Configure Azure App Service

1. **Create App Service** (Python 3.11, Linux)
2. **Connect to GitHub** (Deployment Center)
3. **Set startup command**: `startup.sh`
4. **Add environment variables**:
   - `AZURE_SUBSCRIPTION_ID`
   - `AZURE_TENANT_ID`
   - `AZURE_CLIENT_ID`
   - `AZURE_CLIENT_SECRET`
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_API_KEY`

## How It Works

- **Push to GitHub** → Automatic deployment
- **Oryx builds** both Python and React
- **React serves** as static files
- **FastAPI backend** handles API requests

## Endpoints

- Frontend: `https://your-app.azurewebsites.net`
- Health: `https://your-app.azurewebsites.net/api/health`
- Docs: `https://your-app.azurewebsites.net/docs`

Your app automatically updates when you push to GitHub! 🎉
READMEEOF

# 10. GitHub Actions (optional)
echo "📝 Creating GitHub Actions workflow..."
cat > .github/workflows/azure.yml << 'YMLEOF'
name: Deploy to Azure

on:
  push:
    branches: [ main ]

env:
  AZURE_WEBAPP_NAME: 'your-app-name'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
        cache: 'npm'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        npm ci
        npm run build
    
    - name: Deploy to Azure
      uses: azure/webapps-deploy@v2
      with:
        app-name: ${{ env.AZURE_WEBAPP_NAME }}
        publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
        package: .
YMLEOF

# Final summary
echo ""
echo "✅ GitHub repository setup completed successfully!"
echo "================================================="
echo ""
echo "📁 Created files:"
echo "✅ requirements.txt (Python dependencies)"
echo "✅ package.json (Node.js dependencies)"
echo "✅ startup.sh (Azure startup script)"
echo "✅ app.py (Fallback application)"
echo "✅ web.config (Azure configuration)"
echo "✅ .deployment (Build configuration)"
echo "✅ src/App.js (React app - replace with paste.txt)"
echo "✅ public/index.html (React template)"
echo "✅ .gitignore (Git ignore rules)"
echo "✅ README.md (Instructions)"
echo "✅ .github/workflows/azure.yml (GitHub Actions)"
echo ""
echo "🎯 Next Steps:"
echo ""
echo "1. 📝 Replace placeholder files:"
echo "   cp paste.txt src/App.js"
echo "   cp paste-2.txt paste-2.py"
echo ""
echo "2. 🚀 Push to GitHub:"
echo "   git init"
echo "   git add ."
echo "   git commit -m 'Initial FinKubeOps setup'"
echo "   git remote add origin https://github.com/username/repo.git"
echo "   git push -u origin main"
echo ""
echo "3. ⚙️ Configure Azure App Service:"
echo "   - Connect to GitHub repository"
echo "   - Set startup command: startup.sh"
echo "   - Add environment variables"
echo ""
echo "🌐 Your app will auto-deploy from GitHub to Azure! 🎉"

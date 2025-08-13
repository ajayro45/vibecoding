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

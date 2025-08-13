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

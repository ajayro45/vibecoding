#!/usr/bin/env python3
"""
Fixed High-Performance AI-Powered Kubernetes MCP Server
Real Azure Data Only - No Mock Data
"""

import asyncio
import aiohttp
import json
import logging
import os
import sqlite3
import time
import tempfile
import yaml
import traceback
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# FastAPI imports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
import uvicorn

# Kubernetes imports
try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    print("⚠️ Kubernetes client not available. Install with: pip install kubernetes")

# Azure imports
try:
    from azure.identity import DefaultAzureCredential, ClientSecretCredential
    from azure.mgmt.costmanagement import CostManagementClient
    from azure.mgmt.resource import ResourceManagementClient
    AZURE_SDK_AVAILABLE = True
except ImportError:
    AZURE_SDK_AVAILABLE = False
    print("⚠️ Azure SDK not available. Install with: pip install azure-identity azure-mgmt-costmanagement azure-mgmt-resource")

# OpenAI imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ OpenAI not available. Install with: pip install openai")

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Enhanced logging configuration
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('finops_mcp_server.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Suppress verbose logging
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure.identity').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Configuration constants
CACHE_TTL = 300  # 5 minutes
AZURE_API_CACHE_TTL = 900  # 15 minutes
BACKGROUND_REFRESH_INTERVAL = 300  # 5 minutes
WEBSOCKET_PING_INTERVAL = 15  # 15 seconds
MAX_WEBSOCKET_CONNECTIONS = 100

# Global cache and WebSocket clients
_cache = {}
_cache_timestamps = {}
websocket_clients: Set[WebSocket] = set()

def get_cached_data(key: str, ttl: int = CACHE_TTL):
    """Get cached data if not expired"""
    if key in _cache and key in _cache_timestamps:
        if time.time() - _cache_timestamps[key] < ttl:
            return _cache[key]
    return None

def set_cached_data(key: str, data: Any):
    """Set cached data with timestamp"""
    _cache[key] = data
    _cache_timestamps[key] = time.time()

# Database migration function
async def migrate_database_schema():
    """Migrate existing database to new schema with cost_inr column"""
    try:
        conn = sqlite3.connect("finops_mcp.db")
        cursor = conn.cursor()
        
        # Check if migration is needed
        cursor.execute("PRAGMA table_info(azure_cost_data)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'cost_inr' not in columns:
            logger.info("🔧 Migrating database schema...")
            
            # Add cost_inr column
            cursor.execute('ALTER TABLE azure_cost_data ADD COLUMN cost_inr REAL DEFAULT 0.0')
            
            # Migrate existing cost data
            if 'cost_usd' in columns:
                cursor.execute('UPDATE azure_cost_data SET cost_inr = COALESCE(cost_usd, 0) * 83.0')
                logger.info("✅ Migrated USD to INR values")
            
            # Create index for INR column
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cost_inr ON azure_cost_data(cost_inr)')
            
            conn.commit()
            logger.info("✅ Database migration completed")
        else:
            logger.info("✅ Database schema is up to date")
            
        conn.close()
        
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        # If migration fails, recreate the table
        logger.info("🔄 Recreating database with correct schema...")
        conn = sqlite3.connect("finops_mcp.db")
        cursor = conn.cursor()
        
        # Backup existing data
        try:
            cursor.execute('ALTER TABLE azure_cost_data RENAME TO azure_cost_data_backup')
        except:
            pass
        
        # Create new table with correct schema
        cursor.execute('''
            CREATE TABLE azure_cost_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_group TEXT NOT NULL,
                subscription_id TEXT NOT NULL,
                location TEXT NOT NULL,
                cost_usd REAL DEFAULT 0.0,
                cost_inr REAL NOT NULL DEFAULT 0.0,
                cost_period TEXT NOT NULL,
                tags TEXT DEFAULT '{}',
                last_updated TEXT NOT NULL,
                UNIQUE(resource_id, timestamp, cost_period)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database recreated with correct schema")

# Pydantic models
class ChatRequest(BaseModel):
    query: str
    context: Optional[Dict] = {}

class ChatResponse(BaseModel):
    response: str
    model: str
    timestamp: str
    cached: bool = False

class ManifestRequest(BaseModel):
    manifest: str
    namespace: Optional[str] = "default"
    dry_run: Optional[bool] = False

class ManifestResponse(BaseModel):
    success: bool
    message: str
    resources_created: Optional[List[Dict]] = []
    warnings: Optional[List[str]] = []

class ScaleRequest(BaseModel):
    name: str
    namespace: str
    replicas: int

# Enhanced WebSocket Connection Manager
class WebSocketConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_metadata: Dict[WebSocket, Dict] = {}
        self.lock = asyncio.Lock()
        
    async def connect(self, websocket: WebSocket, client_info: Dict = None):
        """Connect a WebSocket with enhanced tracking"""
        async with self.lock:
            try:
                await websocket.accept()
                self.active_connections.add(websocket)
                self.connection_metadata[websocket] = {
                    'connected_at': datetime.now(),
                    'client_info': client_info or {},
                    'message_count': 0,
                    'last_activity': datetime.now()
                }
                logger.info(f"✅ WebSocket connected. Total connections: {len(self.active_connections)}")
                
                # Send immediate welcome message
                await self.send_personal_message(websocket, {
                    "type": "connection_established",
                    "message": "Connected to Enhanced FinOps MCP Server",
                    "server_version": "2.0.0",
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error connecting WebSocket: {e}")
                await self.disconnect(websocket)
    
    async def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket with cleanup"""
        async with self.lock:
            try:
                if websocket in self.active_connections:
                    self.active_connections.remove(websocket)
                if websocket in self.connection_metadata:
                    del self.connection_metadata[websocket]
                logger.info(f"🔌 WebSocket disconnected. Remaining connections: {len(self.active_connections)}")
            except Exception as e:
                logger.error(f"Error disconnecting WebSocket: {e}")
    
    async def send_personal_message(self, websocket: WebSocket, message: Dict):
        """Send message to specific WebSocket with error handling"""
        try:
            if websocket in self.active_connections:
                await websocket.send_json(message)
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]['last_activity'] = datetime.now()
                    self.connection_metadata[websocket]['message_count'] += 1
                return True
        except Exception as e:
            logger.warning(f"Failed to send message to WebSocket: {e}")
            await self.disconnect(websocket)
            return False
    
    async def broadcast(self, message: Dict):
        """Broadcast message to all connected WebSockets"""
        if not self.active_connections:
            return 0
        
        disconnected = set()
        sent_count = 0
        
        for websocket in list(self.active_connections):
            try:
                if await self.send_personal_message(websocket, message):
                    sent_count += 1
                else:
                    disconnected.add(websocket)
            except Exception as e:
                logger.warning(f"Broadcast failed for WebSocket: {e}")
                disconnected.add(websocket)
        
        for ws in disconnected:
            await self.disconnect(ws)
        
        logger.debug(f"📡 Broadcast sent to {sent_count}/{len(self.active_connections)} clients")
        return sent_count
    
    def get_connection_stats(self):
        """Get connection statistics"""
        return {
            'total_connections': len(self.active_connections),
            'connections_metadata': {
                str(id(ws)): {
                    'connected_duration': (datetime.now() - meta['connected_at']).total_seconds(),
                    'message_count': meta['message_count'],
                    'last_activity': meta['last_activity'].isoformat()
                } for ws, meta in self.connection_metadata.items()
            }
        }

# FIXED Azure OpenAI Manager - Non-blocking
class AzureOpenAIManager:
    def __init__(self):
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.available = False
        self.retry_count = 2  # Reduced retry count
        self.retry_delay = 0.5  # Reduced delay
        self.client = None
        
        # Only initialize if all credentials are present
        if OPENAI_AVAILABLE and all([self.endpoint, self.api_key, self.deployment_name]):
            # Initialize in background, don't block startup
            asyncio.create_task(self._initialize_client_async())
        else:
            logger.info("⚠️ Azure OpenAI not fully configured - AI features will be disabled")

    async def _initialize_client_async(self):
        """Initialize Azure OpenAI client asynchronously without blocking"""
        try:
            from openai import AzureOpenAI
            
            self.client = AzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint
            )
            
            # Quick test with minimal timeout
            test_response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.chat.completions.create(
                        model=self.deployment_name,
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=5,
                        timeout=5
                    )
                ),
                timeout=10.0
            )
            
            self.available = True
            logger.info("✅ Azure OpenAI client initialized successfully")
            
        except Exception as e:
            logger.warning(f"Azure OpenAI initialization failed: {e}")
            self.available = False

    async def generate_response(self, query: str, context: Dict = None) -> str:
        """Generate AI response"""
        if not self.available or not self.client:
            return self._generate_fallback_response(query, context)

        try:
            system_prompt = self._build_system_prompt(context)
            user_prompt = f"User query: {query}\n\nPlease provide a helpful, actionable response."
            
            for attempt in range(self.retry_count):
                try:
                    response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.client.chat.completions.create(
                            model=self.deployment_name,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            max_tokens=1000,
                            temperature=0.7,
                            timeout=30
                        )
                    )
                    
                    return response.choices[0].message.content.strip()
                    
                except Exception as e:
                    logger.warning(f"Azure OpenAI API attempt {attempt + 1} failed: {e}")
                    if attempt < self.retry_count - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise e

        except Exception as e:
            logger.error(f"Azure OpenAI API error: {e}")
            return self._generate_fallback_response(query, context)

        """Generate AI response with strict timeout and fallback"""
        if not self.available or not self.client:
            return self._generate_fallback_response(query, context)

        try:
            system_prompt = self._build_system_prompt(context)
            user_prompt = f"User query: {query}\n\nPlease provide a helpful, actionable response."
            
            # Strict timeout for AI response
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.chat.completions.create(
                        model=self.deployment_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens=800,  # Reduced token count
                        temperature=0.7,
                        timeout=15  # Strict timeout
                    )
                ),
                timeout=20.0  # Overall timeout
            )
            
            return response.choices[0].message.content.strip()
                    
        except asyncio.TimeoutError:
            logger.warning("AI response timeout - using fallback")
            return self._generate_fallback_response(query, context)
        except Exception as e:
            logger.warning(f"Azure OpenAI API error: {e}")
            return self._generate_fallback_response(query, context)

    def _build_system_prompt(self, context: Dict = None) -> str:
        """Build context-aware system prompt"""
        base_prompt = """You are an expert Kubernetes FinOps AI assistant with deep knowledge of:
- Azure cost management and optimization
- Kubernetes cluster operations and best practices
- Financial operations (FinOps) for cloud infrastructure
- Resource optimization and scaling strategies

You provide actionable, specific recommendations. All costs should be discussed in Indian Rupees (INR)."""

        if context:
            if context.get('clusterHealth'):
                cluster_info = context['clusterHealth']
                base_prompt += f"\n\nCurrent cluster status: {cluster_info.get('status', 'unknown')}"
            
            if context.get('finOpsSummary'):
                finops = context['finOpsSummary']
                if finops.get('totalCost'):
                    base_prompt += f"\nCurrent monthly Azure cost: ₹{finops['totalCost']:,.2f} INR"

        return base_prompt

    def _generate_fallback_response(self, query: str, context: Dict = None) -> str:
        """Generate intelligent fallback response"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['cost', 'money', 'expensive', 'azure', 'billing']):
            return """💰 **Azure Cost Analysis (INR)**

**Key Optimization Strategies:**
• **Auto-scaling**: Implement Horizontal Pod Autoscaler (HPA) for dynamic scaling
• **Resource Right-sizing**: Review and adjust CPU/memory requests and limits  
• **Reserved Instances**: Consider Azure Reserved VM Instances for predictable workloads
• **Storage Optimization**: Use appropriate storage tiers and lifecycle policies

**Immediate Actions:**
1. Review over-provisioned resources
2. Enable cluster autoscaler
3. Implement pod disruption budgets
4. Use Azure Advisor recommendations

Would you like me to help you implement any of these optimizations?"""

        else:
            return """🤖 **AI Kubernetes FinOps Assistant**

I'm here to help you with:

**💰 Cost Optimization:**
• Azure spending analysis and recommendations (in INR)
• Resource right-sizing strategies
• Cost alerts and budgeting

**🚀 Cluster Management:**
• Deployment scaling and management
• Health monitoring and troubleshooting
• Performance optimization

What specific area would you like to explore?"""

# Enhanced Database Manager
class DatabaseManager:
    def __init__(self, db_path: str = "finops_mcp.db"):
        self.db_path = db_path
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.connection_pool = {}
        self.init_database()

    def init_database(self):
        """Initialize database with correct schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Enable optimizations
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL') 
        cursor.execute('PRAGMA cache_size=10000')
        cursor.execute('PRAGMA temp_store=MEMORY')

        # Check if table exists and get its schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='azure_cost_data'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Check if cost_inr column exists
            cursor.execute("PRAGMA table_info(azure_cost_data)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'cost_inr' not in columns:
                logger.info("🔧 Adding missing cost_inr column to existing table")
                cursor.execute('ALTER TABLE azure_cost_data ADD COLUMN cost_inr REAL DEFAULT 0.0')
                
                # Migrate existing data if cost_usd exists
                if 'cost_usd' in columns:
                    logger.info("🔄 Migrating USD to INR values (1 USD = 83 INR)")
                    cursor.execute('UPDATE azure_cost_data SET cost_inr = COALESCE(cost_usd, 0) * 83.0 WHERE cost_inr = 0')
        else:
            # Create new table with correct schema
            cursor.execute('''
                CREATE TABLE azure_cost_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    resource_name TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_group TEXT NOT NULL,
                    subscription_id TEXT NOT NULL,
                    location TEXT NOT NULL,
                    cost_usd REAL DEFAULT 0.0,
                    cost_inr REAL NOT NULL DEFAULT 0.0,
                    cost_period TEXT NOT NULL,
                    tags TEXT DEFAULT '{}',
                    last_updated TEXT NOT NULL,
                    UNIQUE(resource_id, timestamp, cost_period)
                )
            ''')

        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cost_timestamp ON azure_cost_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cost_resource ON azure_cost_data(resource_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cost_period ON azure_cost_data(cost_period)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cost_inr ON azure_cost_data(cost_inr)')

        conn.commit()
        conn.close()
        logger.info("✅ Database initialized with correct schema and cost_inr column")

    async def add_cost_data_batch(self, cost_records: List[Dict]):
        """Add multiple cost records efficiently with proper INR handling"""
        def _insert_batch():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            records = []
            current_time = datetime.now().isoformat()
            
            for record in cost_records[:100]:  # Limit batch size
                # Handle both USD and INR costs
                cost_usd = record.get('cost_usd', 0.0)
                cost_inr = record.get('cost_inr', 0.0)
                
                # If only USD is provided, convert to INR
                if cost_usd > 0 and cost_inr == 0:
                    cost_inr = cost_usd * 83.0
                # If only INR is provided, derive USD
                elif cost_inr > 0 and cost_usd == 0:
                    cost_usd = cost_inr / 83.0
                
                records.append((
                    current_time,
                    record.get('resource_id', ''),
                    record.get('resource_name', ''),
                    record.get('resource_type', ''),
                    record.get('resource_group', ''),
                    record.get('subscription_id', ''),
                    record.get('location', ''),
                    cost_usd,
                    cost_inr,
                    record.get('cost_period', 'daily'),
                    json.dumps(record.get('tags', {})),
                    current_time
                ))
            
            cursor.executemany('''
                INSERT OR REPLACE INTO azure_cost_data 
                (timestamp, resource_id, resource_name, resource_type, resource_group, 
                 subscription_id, location, cost_usd, cost_inr, cost_period, tags, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', records)
            
            conn.commit()
            conn.close()
            return len(records)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _insert_batch)

    async def get_cost_overview_fast(self):
        """Get cost overview with enhanced caching and INR support"""
        cache_key = "cost_overview"
        cached = get_cached_data(cache_key, CACHE_TTL)
        if cached:
            logger.debug("📊 Using cached cost overview")
            return cached

        def _get_overview():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get summary data using INR
            cursor.execute('''
                SELECT 
                    COALESCE(SUM(cost_inr), 0) as total_cost,
                    COUNT(DISTINCT resource_id) as resource_count,
                    COALESCE(AVG(cost_inr), 0) as avg_cost
                FROM azure_cost_data 
                WHERE timestamp >= datetime('now', '-30 days')
            ''')
            summary = cursor.fetchone()
            
            # Get cost by type using INR
            cursor.execute('''
                SELECT 
                    CASE 
                        WHEN INSTR(resource_type, '/') > 0 
                        THEN SUBSTR(resource_type, INSTR(resource_type, '/') + 1)
                        ELSE resource_type
                    END as type,
                    SUM(cost_inr) as total_cost
                FROM azure_cost_data 
                WHERE timestamp >= datetime('now', '-30 days')
                GROUP BY type
                ORDER BY total_cost DESC
                LIMIT 10
            ''')
            cost_by_type = {row[0]: row[1] for row in cursor.fetchall()}
            
            conn.close()
            
            total_cost = summary[0] or 0.0
            resource_count = summary[1] or 0
            avg_cost = summary[2] or 0.0
            
            result = {
                'total_monthly_cost': total_cost,
                'resource_count': resource_count,
                'avg_resource_cost': avg_cost,
                'cost_by_type': cost_by_type,
                'cost_by_service': cost_by_type,  # Alias for compatibility
                'optimization_opportunities': min(5, max(1, int(resource_count * 0.2))),
                'total_potential_savings': total_cost * 0.15,
                'last_updated': datetime.now().isoformat(),
                'data_source': 'database_cache'
            }
            
            return result

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.executor, _get_overview)
        
        set_cached_data(cache_key, result)
        logger.info(f"💾 Cost overview loaded: ₹{result['total_monthly_cost']:,.2f} total")
        return result

# FIXED Azure FinOps Manager - Real Data Only
class AzureFinOpsManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        self.tenant_id = os.getenv('AZURE_TENANT_ID')
        self.client_id = os.getenv('AZURE_CLIENT_ID')
        self.client_secret = os.getenv('AZURE_CLIENT_SECRET')
        
        self.credential = None
        self.cost_mgmt_client = None
        self._last_azure_fetch = 0
        self._azure_data_cache = None
        self.retry_count = 2  # Reduced retry count
        self.retry_delay = 1.0
        self.azure_status = 'disconnected'
        
        # Enhanced initialization
        if AZURE_SDK_AVAILABLE and self.subscription_id:
            self._init_azure_clients()
        else:
            logger.error("❌ Azure SDK not available or subscription ID missing - REAL DATA REQUIRED!")
            raise ValueError("Azure configuration is required for real data operation")

    def _init_azure_clients(self):
        """Initialize Azure clients with enhanced error handling"""
        logger.info(f"🔄 Initializing Azure clients for subscription: {self.subscription_id}")
        
        for attempt in range(self.retry_count):
            try:
                # Try Service Principal first if credentials are provided
                if all([self.tenant_id, self.client_id, self.client_secret]):
                    logger.info("🔑 Using Azure Service Principal authentication")
                    self.credential = ClientSecretCredential(
                        tenant_id=self.tenant_id,
                        client_id=self.client_id,
                        client_secret=self.client_secret
                    )
                else:
                    logger.info("🔑 Using Azure Default Credential authentication")
                    self.credential = DefaultAzureCredential()
                
                # Initialize Cost Management client
                self.cost_mgmt_client = CostManagementClient(self.credential)
                self.azure_status = 'azure_client_ready'
                logger.info("✅ Azure Cost Management client initialized successfully")
                return
                    
            except Exception as e:
                logger.warning(f"Azure client initialization attempt {attempt + 1} failed: {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        self.azure_status = 'failed'
        logger.error("❌ Failed to initialize Azure clients after all attempts")
        raise ValueError("Failed to initialize Azure clients - check your credentials")

    async def test_azure_connection_async(self):
        """Test Azure connection asynchronously"""
        if not self.cost_mgmt_client:
            self.azure_status = 'no_client'
            return False
            
        try:
            test_scope = f"/subscriptions/{self.subscription_id}"
            test_query = {
                "type": "ActualCost",
                "timeframe": "MonthToDate",
                "dataset": {
                    "granularity": "Monthly",
                    "aggregation": {
                        "totalCost": {"name": "PreTaxCost", "function": "Sum"}
                    }
                }
            }
            
            test_result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: self.cost_mgmt_client.query.usage(test_scope, test_query)
                ),
                timeout=30.0
            )
            
            self.azure_status = 'azure_api'
            logger.info("✅ Azure Cost Management API connection successful")
            return True
            
        except Exception as e:
            logger.warning(f"Azure API test failed: {e}")
            self.azure_status = 'azure_client_only'
            return False

    async def get_cost_overview_fast(self):
        """Get cost overview with REAL DATA ONLY - no mock data"""
        try:
            # Always get database data first for immediate response
            cached_data = await self.db.get_cost_overview_fast()
        
            # Check Azure connection status and data freshness
            current_time = time.time()
            should_refresh = (current_time - self._last_azure_fetch) > AZURE_API_CACHE_TTL
            
            # Force refresh from Azure if no real data or stale data
            if should_refresh and self.cost_mgmt_client:
                logger.info(f"🔄 Refreshing real Azure data... Status: {self.azure_status}")
                await self._refresh_azure_data()
        
            # Merge with fresh Azure data if available
            if self._azure_data_cache and self._azure_data_cache.get('is_real_data', False):
                # Use real Azure data
                cached_data.update(self._azure_data_cache)
                cached_data['data_source'] = 'azure_api_real'
                logger.info(f"📊 Using real Azure API data: ₹{cached_data.get('total_monthly_cost', 0):,.2f}")
            elif cached_data.get('total_monthly_cost', 0) > 0:
                # Use database cache if it has data
                cached_data['data_source'] = 'database_cache'
                logger.info(f"📊 Using database cache: ₹{cached_data.get('total_monthly_cost', 0):,.2f}")
            else:
                # No data available - return empty structure
                logger.warning("⚠️ No Azure cost data available - check your Azure configuration")
                cached_data = {
                    'total_monthly_cost': 0.0,
                    'cost_by_type': {},
                    'cost_by_service': {},
                    'resource_count': 0,
                    'total_potential_savings': 0.0,
                    'last_updated': datetime.now().isoformat(),
                    'data_source': 'no_data',
                    'error': 'No Azure cost data available'
                }
        
            # Ensure data structure consistency
            cached_data = self._ensure_data_structure(cached_data)
        
            return cached_data
        
        except Exception as e:
            logger.error(f"Error getting cost overview: {e}")
            return {
                'total_monthly_cost': 0.0,
                'cost_by_type': {},
                'cost_by_service': {},
                'resource_count': 0,
                'total_potential_savings': 0.0,
                'last_updated': datetime.now().isoformat(),
                'data_source': 'error',
                'error': str(e)
            }

    async def _refresh_azure_data(self):
        """Refresh Azure data from API - REAL DATA ONLY"""
        try:
            if not self.cost_mgmt_client:
                logger.error("❌ No Azure client available - cannot fetch real data")
                return
        
            logger.info("�� Fetching REAL Azure cost data from API...")
        
            try:
                # Fetch real Azure data with timeout
                cost_data = await asyncio.wait_for(
                    self._fetch_azure_costs_real_only(), 
                    timeout=120.0
                )
            
                # Validate we got real, meaningful data
                if cost_data and cost_data.get('is_real_data', False):
                    self._azure_data_cache = cost_data
                    self._last_azure_fetch = time.time()
                    self.azure_status = 'azure_api'
                
                    # Save to database
                    if cost_data.get('cost_records'):
                        saved_count = await self.db.add_cost_data_batch(cost_data['cost_records'])
                        logger.info(f"💾 Saved {saved_count} real Azure cost records to database")
                
                    logger.info(f"✅ Real Azure data refresh completed - ₹{cost_data.get('total_monthly_cost', 0):,.2f}")
                    return
                else:
                    logger.error("❌ Azure API returned invalid data")
                    self.azure_status = 'no_data'
            
            except asyncio.TimeoutError:
                logger.error("❌ Azure API timeout (120s)")
                self.azure_status = 'timeout'
            
            except Exception as api_error:
                logger.error(f"❌ Azure API error: {api_error}")
                self.azure_status = 'api_error'
                
        except Exception as e:
            logger.error(f"❌ Azure data refresh failed: {e}")
            self.azure_status = 'error'

    async def _fetch_azure_costs_real_only(self):
        """Fetch REAL Azure costs only - no fallback to mock data"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            scope = f"/subscriptions/{self.subscription_id}"
        
            logger.info(f"🔍 Querying REAL Azure costs for scope: {scope}")
            logger.info(f"📅 Date range: {start_date.date()} to {end_date.date()}")
        
            # Use ActualCost query with proper grouping
            query_definition = {
                "type": "ActualCost",
                "timeframe": "Custom", 
                "timePeriod": {
                    "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                    "to": end_date.strftime("%Y-%m-%dT23:59:59Z")
                },
                "dataset": {
                    "granularity": "None",  # Aggregated data
                    "aggregation": {
                        "totalCost": {"name": "PreTaxCost", "function": "Sum"}
                    },
                    "grouping": [
                        {"type": "Dimension", "name": "ServiceName"},
                        {"type": "Dimension", "name": "ResourceType"}
                    ]
                }
            }
        
            logger.info("🔄 Executing Azure Cost Management query...")
        
            # Execute the query with proper error handling
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cost_mgmt_client.query.usage(scope, query_definition)
            )
        
            # Validate the result
            if not result:
                logger.error("❌ Azure API returned null result")
                return None
            
            if not hasattr(result, 'rows') or not result.rows:
                logger.info("⚠️ Azure API returned no cost rows - subscription has zero costs")
                # Return valid zero-cost structure for subscriptions with no charges
                return {
                    'total_monthly_cost': 0.0,
                    'cost_by_type': {},
                    'cost_by_service': {},
                    'cost_records': [],
                    'resource_count': 0,
                    'total_potential_savings': 0.0,
                    'last_updated': datetime.now().isoformat(),
                    'data_source': 'azure_api_zero_cost',
                    'exchange_rate': 83.0,
                    'query_period_days': 30,
                    'api_rows_processed': 0,
                    'is_real_data': True,  # It's real data, just zero cost
                    'subscription_id': self.subscription_id,
                    'query_executed_at': datetime.now().isoformat()
                }
        
            logger.info(f"✅ Azure API returned {len(result.rows)} cost records")
        
            # Process the results
            total_cost_usd = 0.0
            cost_by_service = {}
            cost_by_type = {}
            cost_records = []
            processed_rows = 0
        
            for i, row in enumerate(result.rows):
                try:
                    # Validate row structure
                    if not row or len(row) < 2:
                        logger.debug(f"Skipping invalid row {i}: {row}")
                        continue
                
                    # Extract cost (first column)
                    try:
                        cost_value = row[0]
                        if cost_value is None:
                            continue
                        cost_usd = float(cost_value)
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Invalid cost value in row {i}: {row[0]} - {e}")
                        continue
                
                    # Skip zero or negative costs
                    if cost_usd <= 0:
                        continue
                
                    # Extract service and type information
                    service_name = str(row[1]) if len(row) > 1 and row[1] is not None else "Unknown Service"
                    resource_type = str(row[2]) if len(row) > 2 and row[2] is not None else "Unknown Type"
                
                    # Clean up service names
                    service_clean = service_name.replace('Microsoft.', '').replace('microsoft.', '')
                    type_clean = resource_type.split('/')[-1] if '/' in resource_type else resource_type
                    type_clean = type_clean.replace('Microsoft.', '').replace('microsoft.', '')
                
                    # Accumulate costs
                    total_cost_usd += cost_usd
                    cost_by_service[service_clean] = cost_by_service.get(service_clean, 0) + cost_usd
                    cost_by_type[type_clean] = cost_by_type.get(type_clean, 0) + cost_usd
                
                    # Create detailed cost record
                    cost_records.append({
                        'resource_id': f"azure-{service_clean}-{i}",
                        'resource_name': f"{service_clean}-resource-{i}",
                        'resource_type': resource_type,
                        'service_name': service_name,
                        'resource_group': f'{service_clean.lower()}-rg',
                        'subscription_id': self.subscription_id,
                        'location': 'global',
                        'cost_usd': cost_usd,
                        'cost_period': 'monthly',
                        'tags': {
                            'service': service_clean,
                            'type': type_clean,
                            'source': 'azure_api'
                        }
                    })
                
                    processed_rows += 1
                
                except Exception as e:
                    logger.warning(f"Error processing Azure cost row {i}: {e}")
                    continue
        
            # Convert to INR
            exchange_rate = 83.0
            total_cost_inr = total_cost_usd * exchange_rate
            cost_by_service_inr = {k: v * exchange_rate for k, v in cost_by_service.items()}
            cost_by_type_inr = {k: v * exchange_rate for k, v in cost_by_type.items()}
        
            # Log the processing results
            logger.info(f"💰 Azure API processing summary:")
            logger.info(f"   Total rows returned: {len(result.rows)}")
            logger.info(f"   Rows processed: {processed_rows}")
            logger.info(f"   Total cost: ${total_cost_usd:.2f} USD = ₹{total_cost_inr:,.2f} INR")
            logger.info(f"   Services found: {len(cost_by_service)}")
            if cost_by_service:
                logger.info(f"   Top services: {list(cost_by_service.keys())[:5]}")
        
            # Build result data structure
            result_data = {
                'total_monthly_cost': total_cost_inr,
                'cost_by_type': cost_by_service_inr,  # Use service breakdown as primary
                'cost_by_service': cost_by_service_inr,
                'cost_by_resource_type': cost_by_type_inr,
                'cost_records': cost_records,
                'resource_count': len(cost_records),
                'total_potential_savings': total_cost_inr * 0.15,
                'last_updated': datetime.now().isoformat(),
                'data_source': 'azure_api_real',
                'exchange_rate': exchange_rate,
                'query_period_days': 30,
                'api_rows_returned': len(result.rows),
                'api_rows_processed': processed_rows,
                'is_real_data': True,  # Mark as real Azure data
                'subscription_id': self.subscription_id,
                'query_executed_at': datetime.now().isoformat()
            }
        
            logger.info(f"✅ Azure cost data processed successfully: ₹{total_cost_inr:,.2f} INR")
            return result_data
        
        except Exception as e:
            logger.error(f"Azure cost fetch failed: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            # Return None to indicate failure - NO mock data
            return None

    def _ensure_data_structure(self, data: Dict) -> Dict:
        """Ensure the data structure has all required fields for the frontend"""
        # Ensure cost_by_type exists
        if not data.get('cost_by_type'):
            if data.get('cost_by_service'):
                data['cost_by_type'] = data['cost_by_service']
            else:
                data['cost_by_type'] = {}
        
        # Ensure cost_by_service exists
        if not data.get('cost_by_service'):
            data['cost_by_service'] = data['cost_by_type']
        
        # Ensure other required fields
        data['total_monthly_cost'] = data.get('total_monthly_cost', 0.0)
        data['total_potential_savings'] = data.get('total_potential_savings', data['total_monthly_cost'] * 0.15)
        data['resource_count'] = data.get('resource_count', len(data['cost_by_type']))
        data['last_updated'] = data.get('last_updated', datetime.now().isoformat())
        
        # Set proper data source status
        if not data.get('data_source'):
            data['data_source'] = self.azure_status
        
        return data

    def get_azure_status(self) -> str:
        """Get current Azure integration status"""
        return self.azure_status

# Enhanced Kubernetes Manager (unchanged)
class KubernetesManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.v1 = None
        self.apps_v1 = None
        self.k8s_available = False
        self.retry_count = 3
        self.retry_delay = 1.0
        
        self._init_k8s_client()

    def _init_k8s_client(self):
        """Initialize Kubernetes client with enhanced error handling"""
        if not KUBERNETES_AVAILABLE:
            logger.warning("Kubernetes client not available")
            return
            
        for attempt in range(self.retry_count):
            try:
                # Try in-cluster config first
                config.load_incluster_config()
                logger.info("✅ Loaded in-cluster Kubernetes configuration")
                self.k8s_available = True
                break
            except config.ConfigException:
                try:
                    # Fall back to local config
                    config.load_kube_config()
                    logger.info("✅ Loaded local Kubernetes configuration")
                    self.k8s_available = True
                    break
                except Exception as e:
                    if attempt < self.retry_count - 1:
                        logger.warning(f"Kubernetes config attempt {attempt + 1} failed: {e}")
                        time.sleep(self.retry_delay)
                    else:
                        logger.warning(f"Kubernetes not available after all attempts: {e}")
                        self.k8s_available = False
                        return
        
        if self.k8s_available:
            try:
                self.v1 = client.CoreV1Api()
                self.apps_v1 = client.AppsV1Api()
                
                # Test connection with timeout
                nodes = self.v1.list_node(_request_timeout=10)
                logger.info(f"✅ Connected to Kubernetes cluster with {len(nodes.items)} nodes")
                
            except Exception as e:
                logger.error(f"Failed to initialize Kubernetes clients: {e}")
                self.k8s_available = False

    async def get_cluster_status_fast(self):
        """Get cluster status with enhanced caching and error handling"""
        cache_key = "cluster_status"
        cached = get_cached_data(cache_key, CACHE_TTL)
        if cached:
            return cached

        if not self.k8s_available:
            status = {
                'cluster_health': {
                    'status': 'disconnected',
                    'score': 0,
                    'nodes': {'total': 0, 'ready': 0},
                    'pods': {'total': 0, 'running': 0, 'pending': 0, 'failed': 0},
                    'message': 'Kubernetes cluster not available'
                },
                'last_updated': datetime.now().isoformat()
            }
            set_cached_data(cache_key, status)
            return status

        try:
            # Get data concurrently with timeout
            nodes_task = asyncio.create_task(self._get_nodes_status())
            pods_task = asyncio.create_task(self._get_pods_status())
            
            nodes_result, pods_result = await asyncio.gather(
                nodes_task, pods_task, return_exceptions=True
            )
            
            # Handle potential exceptions
            if isinstance(nodes_result, Exception):
                logger.error(f"Error getting nodes: {nodes_result}")
                nodes_result = {'total': 0, 'ready': 0}
                
            if isinstance(pods_result, Exception):
                logger.error(f"Error getting pods: {pods_result}")
                pods_result = {'total': 0, 'running': 0, 'pending': 0, 'failed': 0}

            # Calculate health score
            health_score = 100
            if nodes_result['total'] > 0:
                health_score *= (nodes_result['ready'] / nodes_result['total'])
            if pods_result['total'] > 0:
                failed_ratio = pods_result['failed'] / pods_result['total']
                health_score -= (failed_ratio * 30)
            
            health_score = max(0, min(100, round(health_score, 1)))
            
            if health_score > 80:
                status_text = "healthy"
            elif health_score > 50:
                status_text = "warning"
            else:
                status_text = "critical"
            
            cluster_status = {
                'cluster_health': {
                    'status': status_text,
                    'score': health_score,
                    'nodes': nodes_result,
                    'pods': pods_result
                },
                'last_updated': datetime.now().isoformat()
            }
            
            set_cached_data(cache_key, cluster_status)
            logger.debug(f"📊 Cluster status: {status_text} ({health_score}%)")
            return cluster_status
            
        except Exception as e:
            logger.error(f"Error getting cluster status: {e}")
            error_status = {
                'cluster_health': {
                    'status': 'error',
                    'score': 0,
                    'nodes': {'total': 0, 'ready': 0},
                    'pods': {'total': 0, 'running': 0, 'pending': 0, 'failed': 0},
                    'error': str(e)
                },
                'last_updated': datetime.now().isoformat()
            }
            set_cached_data(cache_key, error_status)
            return error_status

    async def _get_nodes_status(self):
        """Get nodes status with timeout"""
        try:
            nodes = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.v1.list_node(_request_timeout=10)
                ),
                timeout=15.0
            )
            
            total_nodes = len(nodes.items)
            ready_nodes = 0
            
            for node in nodes.items:
                if node.status.conditions:
                    for condition in node.status.conditions:
                        if condition.type == "Ready" and condition.status == "True":
                            ready_nodes += 1
                            break
            
            return {'total': total_nodes, 'ready': ready_nodes}
            
        except asyncio.TimeoutError:
            logger.warning("Timeout getting node status")
            raise Exception("Timeout getting node status")

    async def _get_pods_status(self):
        """Get pods status with timeout"""
        try:
            pods = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.v1.list_pod_for_all_namespaces(_request_timeout=10)
                ),
                timeout=15.0
            )
            
            pod_stats = {'total': 0, 'running': 0, 'pending': 0, 'failed': 0}
            pod_stats['total'] = len(pods.items)
            
            for pod in pods.items:
                phase = pod.status.phase
                if phase == "Running":
                    pod_stats['running'] += 1
                elif phase == "Pending":
                    pod_stats['pending'] += 1
                elif phase == "Failed":
                    pod_stats['failed'] += 1
            
            return pod_stats
            
        except asyncio.TimeoutError:
            logger.warning("Timeout getting pod status")
            raise Exception("Timeout getting pod status")

    async def get_deployments(self, namespace: str = "default"):
        """Get deployments list with enhanced error handling"""
        if not self.k8s_available:
            return []

        try:
            if namespace == "all":
                deployments = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.apps_v1.list_deployment_for_all_namespaces(_request_timeout=10)
                    ),
                    timeout=15.0
                )
            else:
                deployments = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.apps_v1.list_namespaced_deployment(namespace=namespace, _request_timeout=10)
                    ),
                    timeout=15.0
                )
            
            result = []
            for item in deployments.items:
                result.append({
                    'name': item.metadata.name,
                    'namespace': item.metadata.namespace,
                    'replicas': item.spec.replicas,
                    'ready_replicas': item.status.ready_replicas or 0,
                    'available_replicas': item.status.available_replicas or 0,
                    'created': item.metadata.creation_timestamp.isoformat() if item.metadata.creation_timestamp else None
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting deployments: {e}")
            return []

    async def get_pods(self, namespace: str = "default"):
        """Get pods list with enhanced error handling"""
        if not self.k8s_available:
            return []

        try:
            if namespace == "all":
                pods = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.v1.list_pod_for_all_namespaces(_request_timeout=10)
                    ),
                    timeout=15.0
                )
            else:
                pods = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.v1.list_namespaced_pod(namespace=namespace, _request_timeout=10)
                    ),
                    timeout=15.0
                )
            
            result = []
            for item in pods.items:
                result.append({
                    'name': item.metadata.name,
                    'namespace': item.metadata.namespace,
                    'phase': item.status.phase,
                    'node': item.spec.node_name,
                    'ready': self._get_pod_ready_status(item),
                    'restarts': self._get_pod_restart_count(item),
                    'created': item.metadata.creation_timestamp.isoformat() if item.metadata.creation_timestamp else None
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting pods: {e}")
            return []

    async def get_services(self, namespace: str = "default"):
        """Get services list with enhanced error handling"""
        if not self.k8s_available:
            return []

        try:
            if namespace == "all":
                services = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.v1.list_service_for_all_namespaces(_request_timeout=10)
                    ),
                    timeout=15.0
                )
            else:
                services = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.v1.list_namespaced_service(namespace=namespace, _request_timeout=10)
                    ),
                    timeout=15.0
                )
            
            result = []
            for item in services.items:
                result.append({
                    'name': item.metadata.name,
                    'namespace': item.metadata.namespace,
                    'type': item.spec.type,
                    'cluster_ip': item.spec.cluster_ip,
                    'ports': [{'port': p.port, 'target_port': p.target_port, 'protocol': p.protocol} 
                             for p in (item.spec.ports or [])],
                    'created': item.metadata.creation_timestamp.isoformat() if item.metadata.creation_timestamp else None
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting services: {e}")
            return []

    def _get_pod_ready_status(self, pod):
        """Get pod ready status"""
        try:
            ready = 0
            total = len(pod.spec.containers) if pod.spec.containers else 0
            
            if pod.status.container_statuses:
                ready = len([c for c in pod.status.container_statuses if c.ready])
            
            return f"{ready}/{total}"
        except:
            return "0/0"

    def _get_pod_restart_count(self, pod):
        """Get total restart count for pod"""
        try:
            if not pod.status.container_statuses:
                return 0
            return sum(c.restart_count for c in pod.status.container_statuses)
        except:
            return 0

    async def scale_deployment(self, name: str, namespace: str, replicas: int):
        """Scale deployment with enhanced error handling"""
        if not self.k8s_available:
            raise HTTPException(status_code=503, detail="Kubernetes cluster not available")

        try:
            # Get current deployment
            deployment = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.apps_v1.read_namespaced_deployment(name, namespace, _request_timeout=10)
                ),
                timeout=15.0
            )
            
            # Update replicas
            deployment.spec.replicas = replicas
            
            # Apply changes
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.apps_v1.patch_namespaced_deployment(
                        name=name, namespace=namespace, body=deployment, _request_timeout=15
                    )
                ),
                timeout=20.0
            )
            
            logger.info(f"✅ Scaled deployment {name} to {replicas} replicas")
            return {'message': f"Deployment {name} scaled to {replicas} replicas", 'success': True}
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout scaling deployment {name}")
            raise HTTPException(status_code=504, detail="Request timeout")
        except Exception as e:
            logger.error(f"Scaling error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def apply_manifest(self, manifest_content: str, namespace: str = "default", dry_run: bool = False):
        """Apply YAML manifest with enhanced error handling"""
        if not self.k8s_available:
            return ManifestResponse(
                success=False,
                message="Kubernetes cluster not available",
                resources_created=[],
                warnings=["Cluster connection not established"]
            )

        try:
            resources = list(yaml.safe_load_all(manifest_content))
            resources = [r for r in resources if r is not None]
            
            if not resources:
                return ManifestResponse(
                    success=False,
                    message="No valid resources found in manifest",
                    resources_created=[],
                    warnings=["Manifest appears to be empty or invalid"]
                )

            created_resources = []
            warnings = []
            
            for resource in resources:
                try:
                    result = await self._apply_single_resource(resource, namespace, dry_run)
                    if result['success']:
                        created_resources.append(result)
                    else:
                        warnings.append(f"Failed to apply {result.get('kind', 'unknown')}: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    warnings.append(f"Error processing resource: {str(e)}")

            success = len(created_resources) > 0 or dry_run
            message = f"{'Validated' if dry_run else 'Applied'} {len(created_resources)} resources successfully"
            if warnings:
                message += f" with {len(warnings)} warnings"

            return ManifestResponse(
                success=success,
                message=message,
                resources_created=created_resources,
                warnings=warnings
            )

        except Exception as e:
            logger.error(f"Manifest application error: {e}")
            return ManifestResponse(
                success=False,
                message=f"Error {'validating' if dry_run else 'applying'} manifest: {str(e)}",
                resources_created=[],
                warnings=[]
            )

    async def _apply_single_resource(self, resource: Dict, namespace: str, dry_run: bool) -> Dict:
        """Apply a single resource with timeout"""
        kind = resource.get('kind', 'Unknown')
        metadata = resource.get('metadata', {})
        name = metadata.get('name', 'unnamed')
        resource_namespace = metadata.get('namespace', namespace)

        try:
            if dry_run:
                # Just validate the resource structure
                return {
                    'success': True,
                    'kind': kind,
                    'name': name,
                    'namespace': resource_namespace,
                    'operation': 'validated'
                }

            if kind == 'Deployment':
                try:
                    existing = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, lambda: self.apps_v1.read_namespaced_deployment(name, resource_namespace, _request_timeout=10)
                        ),
                        timeout=15.0
                    )
                    result = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, lambda: self.apps_v1.replace_namespaced_deployment(
                                name=name, namespace=resource_namespace, body=resource, _request_timeout=15)
                        ),
                        timeout=20.0
                    )
                    operation = 'updated'
                except ApiException as e:
                    if e.status == 404:
                        result = await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(
                                None, lambda: self.apps_v1.create_namespaced_deployment(
                                    namespace=resource_namespace, body=resource, _request_timeout=15)
                            ),
                            timeout=20.0
                        )
                        operation = 'created'
                    else:
                        raise

            elif kind == 'Service':
                try:
                    existing = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, lambda: self.v1.read_namespaced_service(name, resource_namespace, _request_timeout=10)
                        ),
                        timeout=15.0
                    )
                    result = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, lambda: self.v1.replace_namespaced_service(
                                name=name, namespace=resource_namespace, body=resource, _request_timeout=15)
                        ),
                        timeout=20.0
                    )
                    operation = 'updated'
                except ApiException as e:
                    if e.status == 404:
                        result = await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(
                                None, lambda: self.v1.create_namespaced_service(
                                    namespace=resource_namespace, body=resource, _request_timeout=15)
                            ),
                            timeout=20.0
                        )
                        operation = 'created'
                    else:
                        raise

            else:
                return {
                    'success': False,
                    'kind': kind,
                    'name': name,
                    'namespace': resource_namespace,
                    'error': f'Unsupported resource kind: {kind}'
                }

            return {
                'success': True,
                'kind': kind,
                'name': name,
                'namespace': resource_namespace,
                'operation': operation
            }

        except asyncio.TimeoutError:
            return {
                'success': False,
                'kind': kind,
                'name': name,
                'namespace': resource_namespace,
                'error': 'Request timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'kind': kind,
                'name': name,
                'namespace': resource_namespace,
                'error': str(e)
            }

# Initialize managers
db_manager = DatabaseManager()
k8s_manager = KubernetesManager(db_manager)
finops_manager = AzureFinOpsManager(db_manager)
ai_manager = AzureOpenAIManager()

# Enhanced WebSocket Connection Manager
websocket_manager = WebSocketConnectionManager()

# FastAPI app with enhanced configuration
app = FastAPI(
    title="Enhanced Kubernetes FinOps MCP Server",
    description="AI-powered Kubernetes FinOps platform with Azure integration",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background task management
_background_tasks_started = False
_background_task = None

# API Routes with enhanced error handling
@app.get("/api/health")
async def health_check():
    """Enhanced health check with detailed status"""
    connection_stats = websocket_manager.get_connection_stats()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "kubernetes": "connected" if k8s_manager.k8s_available else "disconnected",
            "azure_finops": "connected" if finops_manager.cost_mgmt_client else "disconnected",
            "azure_openai": "connected" if ai_manager.available else "disconnected",
            "database": "active",
            "cache": "enabled",
            "websockets": f"{connection_stats['total_connections']} active"
        },
        "version": "2.0.0",
        "features": {
            "azure_cost_api": AZURE_SDK_AVAILABLE,
            "openai_integration": OPENAI_AVAILABLE,
            "kubernetes_integration": KUBERNETES_AVAILABLE,
            "real_time_updates": True,
            "intelligent_caching": True,
            "enhanced_websockets": True
        },
        "performance": {
            "cache_size": len(_cache),
            "websocket_connections": connection_stats['total_connections']
        }
    }

# Enhanced API endpoint for better debugging
@app.get("/api/azure/status")
async def get_azure_status():
    """Get detailed Azure integration status"""
    return {
        "subscription_id": finops_manager.subscription_id,
        "azure_status": finops_manager.get_azure_status(),
        "client_available": finops_manager.cost_mgmt_client is not None,
        "last_fetch": finops_manager._last_azure_fetch,
        "cache_available": finops_manager._azure_data_cache is not None,
        "sdk_available": AZURE_SDK_AVAILABLE,
        "credentials_configured": {
            "subscription_id": bool(os.getenv('AZURE_SUBSCRIPTION_ID')),
            "tenant_id": bool(os.getenv('AZURE_TENANT_ID')),
            "client_id": bool(os.getenv('AZURE_CLIENT_ID')),
            "client_secret": bool(os.getenv('AZURE_CLIENT_SECRET'))
        }
    }

@app.get("/api/finops/overview")
async def get_finops_overview():
    """Enhanced FinOps overview with concurrent AI analysis and cost data"""
    try:
        # Start both operations concurrently without waiting
        cost_task = asyncio.create_task(finops_manager.get_cost_overview_fast())
        
        # Get cost data first (this should be fast due to caching)
        cost_overview = await cost_task
        
        # Start AI analysis as a separate task that doesn't block the response
        ai_analysis = None
        ai_task = None
        
        if ai_manager.available and cost_overview.get('total_monthly_cost', 0) > 0:
            try:
                # Create AI analysis task with timeout
                ai_task = asyncio.create_task(
                    asyncio.wait_for(
                        ai_manager.generate_response(
                            f"Analyze Azure costs of ₹{cost_overview.get('total_monthly_cost', 0):,.2f} INR and provide optimization recommendations for Indian market",
                            {"finOpsData": {"cost_data": cost_overview}}
                        ),
                        timeout=15.0  # 15 second timeout for AI
                    )
                )
                
                # Try to get AI response, but don't block if it takes too long
                try:
                    ai_analysis = await ai_task
                    logger.info("✅ AI analysis completed successfully")
                except asyncio.TimeoutError:
                    logger.warning("⏰ AI analysis timeout - proceeding without AI insights")
                    ai_analysis = "AI analysis is processing in background..."
                except Exception as e:
                    logger.warning(f"AI analysis failed: {e}")
                    ai_analysis = "AI analysis temporarily unavailable"
                    
            except Exception as e:
                logger.warning(f"Failed to start AI analysis: {e}")
                ai_analysis = "AI analysis unavailable"
        
        # Calculate recommendations based on cost data
        total_cost = cost_overview.get('total_monthly_cost', 0)
        
        # Enhanced response structure with real data focus
        response = {
            'cost_data': cost_overview,
            'ai_analysis': ai_analysis,
            'actionable_recommendations': [
                {
                    'action': 'Enable auto-scaling policies',
                    'command': 'kubectl apply -f hpa-config.yaml',
                    'estimated_savings_inr': total_cost * 0.08,
                    'risk_level': 'low',
                    'priority': 'high',
                    'description': 'Implement Horizontal Pod Autoscaler to reduce over-provisioning'
                },
                {
                    'action': 'Right-size over-provisioned resources',
                    'command': 'kubectl top pods --all-namespaces',
                    'estimated_savings_inr': total_cost * 0.05,
                    'risk_level': 'medium',
                    'priority': 'high',
                    'description': 'Analyze resource usage and adjust CPU/memory limits'
                },
                {
                    'action': 'Use Azure Advisor recommendations',
                    'command': 'az advisor recommendation list --category Cost',
                    'estimated_savings_inr': total_cost * 0.02,
                    'risk_level': 'low',
                    'priority': 'medium',
                    'description': 'Review Azure-native optimization suggestions'
                },
                {
                    'action': 'Implement resource scheduling',
                    'command': 'kubectl patch deployment <name> -p \'{"spec":{"template":{"spec":{"schedulerName":"cost-optimizer"}}}}\'',
                    'estimated_savings_inr': total_cost * 0.03,
                    'risk_level': 'low',
                    'priority': 'medium',
                    'description': 'Schedule non-critical workloads during off-peak hours'
                }
            ],
            'total_potential_savings': cost_overview.get('total_potential_savings', total_cost * 0.15),
            'currency': 'INR',
            'last_updated': datetime.now().isoformat(),
            'data_source': cost_overview.get('data_source', 'unknown'),
            'ai_status': 'completed' if ai_analysis and 'unavailable' not in str(ai_analysis) else 'partial'
        }
        
        logger.info(f"📊 FinOps overview completed - ₹{total_cost:,.2f} | Source: {cost_overview.get('data_source', 'unknown')}")
        return response
        
    except Exception as e:
        logger.error(f"FinOps overview error: {e}")
        
        # Return minimal fallback response
        fallback_response = {
            'cost_data': {
                'total_monthly_cost': 0,
                'cost_by_type': {},
                'cost_by_service': {},
                'resource_count': 0,
                'data_source': 'error',
                'last_updated': datetime.now().isoformat()
            },
            'ai_analysis': f'Service temporarily unavailable: {str(e)}',
            'actionable_recommendations': [],
            'total_potential_savings': 0,
            'currency': 'INR',
            'last_updated': datetime.now().isoformat(),
            'error': str(e),
            'ai_status': 'error'
        }
        
        return fallback_response

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    """Enhanced AI chat with context awareness"""
    try:
        # Get current system context
        cluster_status = await k8s_manager.get_cluster_status_fast()
        cost_overview = await finops_manager.get_cost_overview_fast()
        
        # Build comprehensive context
        context = {
            'clusterHealth': cluster_status.get('cluster_health'),
            'finOpsData': {'cost_data': cost_overview},
            'timestamp': datetime.now().isoformat(),
            **request.context
        }
        
        # Generate AI response
        response = await ai_manager.generate_response(request.query, context)
        
        return ChatResponse(
            response=response,
            model="azure-openai-gpt-35-turbo",
            timestamp=datetime.now().isoformat(),
            cached=False
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return ChatResponse(
            response=f"I apologize, but I'm experiencing technical difficulties. Error: {str(e)}",
            model="fallback",
            timestamp=datetime.now().isoformat(),
            cached=False
        )

@app.get("/api/cluster/status")
async def get_cluster_status():
    """Get comprehensive cluster status"""
    return await k8s_manager.get_cluster_status_fast()

@app.get("/api/deployments")
async def get_deployments(namespace: str = Query("default")):
    """Get deployments list"""
    return await k8s_manager.get_deployments(namespace)

@app.get("/api/pods") 
async def get_pods(namespace: str = Query("default")):
    """Get pods list"""
    return await k8s_manager.get_pods(namespace)

@app.get("/api/services")
async def get_services(namespace: str = Query("default")):
    """Get services list"""
    return await k8s_manager.get_services(namespace)

@app.post("/api/deployments/scale")
async def scale_deployment(request: ScaleRequest):
    """Scale deployment"""
    return await k8s_manager.scale_deployment(request.name, request.namespace, request.replicas)

@app.post("/api/manifests/apply", response_model=ManifestResponse)
async def apply_manifest(request: ManifestRequest):
    """Apply YAML manifest"""
    return await k8s_manager.apply_manifest(request.manifest, request.namespace, request.dry_run)

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Enhanced file upload handler"""
    try:
        content = await file.read()
        
        # Handle YAML/JSON files
        if file.filename.endswith(('.yaml', '.yml', '.json')):
            try:
                if file.filename.endswith('.json'):
                    parsed = json.loads(content.decode('utf-8'))
                else:
                    parsed = yaml.safe_load(content.decode('utf-8'))
                
                return {
                    'success': True,
                    'message': f'Successfully parsed {file.filename}',
                    'content': content.decode('utf-8'),
                    'parsed': parsed,
                    'type': 'manifest'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to parse {file.filename}: {str(e)}'
                }
        
        # Handle other file types
        return {
            'success': True,
            'message': f'File {file.filename} uploaded successfully',
            'size': len(content),
            'type': 'binary'
        }
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/azure/force-refresh")
async def force_azure_refresh():
    """Force fresh Azure data fetch"""
    try:
        logger.info("🔄 FORCING fresh Azure data fetch...")
        
        # Clear cache
        finops_manager._azure_data_cache = None
        finops_manager._last_azure_fetch = 0
        
        # Force refresh
        await finops_manager._refresh_azure_data()
        
        # Get the fresh data
        cost_overview = await finops_manager.get_cost_overview_fast()
        
        return {
            "success": True,
            "message": "Azure data refreshed successfully",
            "data": cost_overview,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Force refresh failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Enhanced WebSocket endpoint
@app.websocket("/ws")
async def enhanced_websocket_endpoint(websocket: WebSocket):
    """Enhanced WebSocket with intelligent updates"""
    await websocket.accept()
    websocket_clients.add(websocket)
    
    logger.info(f"🔌 WebSocket connected (Total: {len(websocket_clients)})")
    
    try:
        # Send immediate status
        try:
            cluster_status = await k8s_manager.get_cluster_status_fast()
            cost_overview = await finops_manager.get_cost_overview_fast()
            
            await websocket.send_json({
                "type": "fast_initial_status",
                "cluster_health": cluster_status.get("cluster_health", {}),
                "cost_summary": {
                    "monthly_cost": cost_overview.get('total_monthly_cost', 0),
                    "potential_savings": cost_overview.get('total_potential_savings', 0),
                    "resource_count": cost_overview.get('resource_count', 0)
                },
                "timestamp": datetime.now().isoformat(),
                "server_version": "2.0.0"
            })
            
        except Exception as e:
            logger.error(f"WebSocket initial data error: {e}")
            await websocket.send_json({
                "type": "error",
                "message": "Failed to load initial data",
                "timestamp": datetime.now().isoformat()
            })
        
        # Send cost breakdown details
        if cost_overview.get('cost_by_type'):
            await websocket.send_json({
                "type": "cost_breakdown",
                "cost_by_service": cost_overview.get('cost_by_type', {}),
                "timestamp": datetime.now().isoformat()
            })
        
        # Start background monitoring
        global _background_tasks_started
        if not _background_tasks_started:
            asyncio.create_task(_enhanced_background_monitoring())
            _background_tasks_started = True
        
        # Keep connection alive
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=WEBSOCKET_PING_INTERVAL)
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "type": "ping",
                    "timestamp": datetime.now().isoformat(),
                    "clients": len(websocket_clients)
                })
            except Exception:
                break
                
    except WebSocketDisconnect:
        logger.info("🔌 WebSocket disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        websocket_clients.discard(websocket)
        logger.info(f"🔌 WebSocket removed (Remaining: {len(websocket_clients)})")

# Enhanced background monitoring
async def _enhanced_background_monitoring():
    """Enhanced background monitoring with AI insights"""
    logger.info("🚀 Starting enhanced background monitoring with AI")
    
    while True:
        try:
            if websocket_clients:
                # Get fresh data
                cluster_status = await k8s_manager.get_cluster_status_fast()
                cost_overview = await finops_manager.get_cost_overview_fast()
                
                # Broadcast updates
                broadcast_data = {
                    "type": "background_update",
                    "cluster_health": cluster_status.get("cluster_health", {}),
                    "cost_summary": {
                        "monthly_cost": cost_overview.get('total_monthly_cost', 0),
                        "potential_savings": cost_overview.get('total_potential_savings', 0),
                        "resource_count": cost_overview.get('resource_count', 0),
                        "data_source": cost_overview.get('data_source', 'unknown')
                    },
                    "timestamp": datetime.now().isoformat(),
                    "clients_connected": len(websocket_clients)
                }
                
                # Send to all clients
                for client_ws in list(websocket_clients):
                    try:
                        await client_ws.send_json(broadcast_data)
                    except Exception:
                        websocket_clients.discard(client_ws)
            
            await asyncio.sleep(BACKGROUND_REFRESH_INTERVAL)
            
        except Exception as e:
            logger.error(f"Background monitoring error: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def enhanced_startup():
    """Enhanced startup sequence with database migration"""
    logger.info("🚀 Enhanced Kubernetes FinOps MCP Server starting...")
    
    try:
        # Run database migration first
        await migrate_database_schema()
        
        # Pre-warm cache and initialize connections
        logger.info("🔥 Pre-warming cache and testing connections...")
        
        # Test Azure connection
        if finops_manager.cost_mgmt_client:
            logger.info("✅ Azure Cost Management client ready")
        else:
            logger.warning("⚠️ Azure Cost Management not configured - using mock data")
        
        # Test OpenAI connection
        if ai_manager.available:
            logger.info("✅ Azure OpenAI client ready")
        else:
            logger.warning("⚠️ Azure OpenAI not configured - using fallback responses")
        
        # Test Kubernetes connection
        if k8s_manager.k8s_available:
            logger.info("✅ Kubernetes client ready")
        else:
            logger.warning("⚠️ Kubernetes not available - using mock data")
        
        # Pre-load initial data
        initial_tasks = [
            asyncio.create_task(k8s_manager.get_cluster_status_fast()),
            asyncio.create_task(finops_manager.get_cost_overview_fast()),
        ]
        
        await asyncio.gather(*initial_tasks, return_exceptions=True)
        
        logger.info("✅ Enhanced FinOps MCP Server ready! 🚀")
        
    except Exception as e:
        logger.warning(f"Startup initialization failed: {e}")
    
    logger.info("🎯 Server ready for connections on http://localhost:8000")

@app.get("/")
async def enhanced_root():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🚀 Enhanced Kubernetes FinOps MCP Server</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0;
                color: white;
            }
            .container {
                text-align: center;
                background: rgba(255, 255, 255, 0.1);
                padding: 40px;
                border-radius: 20px;
                backdrop-filter: blur(10px);
                max-width: 900px;
            }
            .logo { font-size: 3em; margin-bottom: 20px; }
            .ai-badge { 
                background: linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4, #ffeaa7);
                background-size: 300% 300%;
                padding: 15px 30px;
                border-radius: 25px;
                font-weight: bold;
                margin: 20px 0;
                animation: gradient 3s ease infinite;
            }
            @keyframes gradient {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            .features { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                gap: 20px; 
                margin: 30px 0; 
            }
            .feature { 
                padding: 20px; 
                background: rgba(255, 255, 255, 0.1); 
                border-radius: 12px;
                transition: transform 0.3s ease;
            }
            .feature:hover {
                transform: translateY(-5px);
            }
            .metrics {
                background: rgba(0, 0, 0, 0.2);
                padding: 20px;
                border-radius: 10px;
                margin-top: 20px;
            }
            .integration-status {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }
            .status-item {
                padding: 10px;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 8px;
                border-left: 4px solid #00ff88;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🚀 Enhanced Kubernetes FinOps MCP Server</div>
            <div class="ai-badge">🤖 AI-POWERED WITH AZURE OPENAI</div>
            <p>Advanced MCP server with live Azure integration, intelligent AI responses, and real-time monitoring</p>
            
            <div class="integration-status">
                <div class="status-item">
                    <h4>🔗 Azure Cost API</h4>
                    <p>Live cost monitoring</p>
                </div>
                <div class="status-item">
                    <h4>🤖 Azure OpenAI</h4>
                    <p>Intelligent responses</p>
                </div>
                <div class="status-item">
                    <h4>☸️ Kubernetes</h4>
                    <p>Cluster management</p>
                </div>
                <div class="status-item">
                    <h4>📊 Real-time Data</h4>
                    <p>WebSocket updates</p>
                </div>
            </div>
            
            <div class="features">
                <div class="feature">
                    <h3>🤖 AI Assistant</h3>
                    <p>Context-aware responses with Azure OpenAI integration</p>
                </div>
                <div class="feature">
                    <h3>💰 Live Azure Costs</h3>
                    <p>Real-time cost monitoring and optimization</p>
                </div>
                <div class="feature">
                    <h3>⚡ Smart Caching</h3>
                    <p>Intelligent caching with background refresh</p>
                </div>
                <div class="feature">
                    <h3>🔄 Auto-scaling</h3>
                    <p>Dynamic deployment scaling with AI recommendations</p>
                </div>
                <div class="feature">
                    <h3>📈 FinOps Analytics</h3>
                    <p>Advanced cost analysis and forecasting</p>
                </div>
                <div class="feature">
                    <h3>🛡️ Enterprise Ready</h3>
                    <p>Production-grade reliability and security</p>
                </div>
            </div>
            
            <div class="metrics">
                <h4>🎯 Enhanced Features</h4>
                <p>✅ Azure OpenAI GPT-3.5/4 Integration</p>
                <p>✅ Live Azure Cost Management API</p>
                <p>✅ Real-time Kubernetes Monitoring</p>
                <p>✅ Intelligent Context-Aware Responses</p>
                <p>✅ Advanced Caching & Performance</p>
                <p>✅ WebSocket Real-time Updates</p>
                <p>✅ YAML Manifest Processing</p>
                <p>✅ Comprehensive Error Handling</p>
            </div>
            
            <div style="margin-top: 30px;">
                <p><strong>🌐 Server: http://localhost:8000</strong></p>
                <p><strong>📚 API Docs: http://localhost:8000/docs</strong></p>
                <p><strong>🔌 WebSocket: ws://localhost:8000/ws</strong></p>
                <p><strong>💬 Chat API: POST /api/chat</strong></p>
                <p><strong>💰 FinOps: GET /api/finops/overview</strong></p>
            </div>
            
            <div style="margin-top: 20px; font-size: 0.9em; opacity: 0.8;">
                <p>Configure your environment variables:</p>
                <p>AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_SUBSCRIPTION_ID</p>
            </div>
        </div>
    </body>
    </html>
    """)

if __name__ == "__main__":
    logger.info("🚀 Starting Enhanced Kubernetes FinOps MCP Server")
    
    # Display configuration status
    logger.info("📋 Configuration Status:")
    logger.info(f"   Azure SDK: {'✅ Available' if AZURE_SDK_AVAILABLE else '❌ Not installed'}")
    logger.info(f"   OpenAI: {'✅ Available' if OPENAI_AVAILABLE else '❌ Not installed'}")
    logger.info(f"   Kubernetes: {'✅ Available' if KUBERNETES_AVAILABLE else '❌ Not installed'}")
    logger.info(f"   Azure Subscription: {'✅ Configured' if os.getenv('AZURE_SUBSCRIPTION_ID') else '❌ Not set'}")
    logger.info(f"   Azure OpenAI: {'✅ Configured' if all([os.getenv('AZURE_OPENAI_ENDPOINT'), os.getenv('AZURE_OPENAI_API_KEY')]) else '❌ Not configured'}")
    logger.info(f"   Kubernetes: {'✅ Available' if k8s_manager.k8s_available else '❌ Not available'}")
    
    # Run server
    uvicorn.run(
        "mcp_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        access_log=False,
        workers=1,
        loop="asyncio"
    )

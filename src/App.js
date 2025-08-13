import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
    Paperclip, Send, X, Mic, Square, Gauge, Rocket, TrendingUp, 
    ChevronDown, Plus, Trash2, Edit, Play, Pause, FileText, 
    AlertTriangle, CheckCircle, DollarSign, Activity, Cloud, 
    Server, Database, Zap, Menu, Bell, Search, Settings, User, 
    Home, BarChart3, Layers, Shield, Sparkles, ArrowRight, Eye, 
    EyeOff, Calendar, Clock, MapPin, Globe, RefreshCw, Cpu,
    HardDrive, Network, AlertCircle, Info, Wifi, WifiOff
} from 'lucide-react';

// Enhanced API Configuration
const API_CONFIG = {
    BASE_URL: 'http://4.231.42.99:8000',
    WS_URL: 'ws://4.231.42.99:8000/ws',
    RETRY_ATTEMPTS: 3,
    RETRY_DELAY: 1000,
    REQUEST_TIMEOUT: 10000
};

// Enhanced API Client
class EnhancedAPIClient {
    static async request(endpoint, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.REQUEST_TIMEOUT);

        try {
            const response = await fetch(`${API_CONFIG.BASE_URL}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
                signal: controller.signal,
                ...options,
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            return data;
        } catch (error) {
            clearTimeout(timeoutId);
            console.error(`API Error (${endpoint}):`, error);
            throw error;
        }
    }

    static async getHealth() {
        return this.request('/api/health');
    }

    static async getClusterStatus() {
        return this.request('/api/cluster/status');
    }

    static async getDeployments(namespace = 'default') {
        return this.request(`/api/deployments?namespace=${namespace}`);
    }

    static async getPods(namespace = 'default') {
        return this.request(`/api/pods?namespace=${namespace}`);
    }

    static async getServices(namespace = 'default') {
        return this.request(`/api/services?namespace=${namespace}`);
    }

    static async scaleDeployment(name, namespace, replicas) {
        return this.request('/api/deployments/scale', {
            method: 'POST',
            body: JSON.stringify({ name, namespace, replicas }),
        });
    }

    static async getFinOpsOverview() {
        return this.request('/api/finops/overview');
    }

    static async chatWithAI(query, context = {}) {
        const lightContext = {
            ...context,
            finOpsSummary: context.realTimeData ? {
                totalCost: context.realTimeData.finOpsData?.cost_data?.total_monthly_cost || 0,
                potentialSavings: context.realTimeData.finOpsData?.cost_data?.total_potential_savings || 0
            } : {}
        };
        
        return this.request('/api/chat', {
            method: 'POST',
            body: JSON.stringify({ query, context: lightContext }),
        });
    }
}

// Enhanced WebSocket Manager
class EnhancedWebSocketManager {
    constructor(onMessage, onError, onStatusChange) {
        this.ws = null;
        this.onMessage = onMessage;
        this.onError = onError;
        this.onStatusChange = onStatusChange;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.heartbeatInterval = null;
        this.isConnecting = false;
        this.connectionStatus = 'disconnected';
    }

    connect() {
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        this.isConnecting = true;
        this.updateStatus('connecting');

        try {
            this.ws = new WebSocket(API_CONFIG.WS_URL);
            
            this.ws.onopen = () => {
                console.log('🔌 WebSocket connected to backend');
                this.reconnectAttempts = 0;
                this.isConnecting = false;
                this.updateStatus('connected');
                this.startHeartbeat();
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.onMessage(data);
                } catch (error) {
                    console.error('WebSocket message parse error:', error);
                }
            };

            this.ws.onclose = (event) => {
                console.log('🔌 WebSocket disconnected', event.code, event.reason);
                this.isConnecting = false;
                this.updateStatus('disconnected');
                this.stopHeartbeat();
                this.handleReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.isConnecting = false;
                this.updateStatus('error');
                this.onError?.(error);
            };
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.isConnecting = false;
            this.updateStatus('error');
            this.handleReconnect();
        }
    }

    updateStatus(status) {
        this.connectionStatus = status;
        this.onStatusChange?.(status);
    }

    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.send({ type: 'ping', timestamp: Date.now() });
            }
        }, 30000);
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            
            setTimeout(() => {
                this.connect();
            }, this.reconnectDelay * Math.min(this.reconnectAttempts, 5));
        } else {
            console.error('Max reconnection attempts reached');
            this.updateStatus('failed');
        }
    }

    disconnect() {
        this.stopHeartbeat();
        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
            this.ws = null;
        }
        this.updateStatus('disconnected');
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
            return true;
        }
        return false;
    }

    getStatus() {
        return this.connectionStatus;
    }
}

// Utility function to format INR currency
const formatINR = (amount, showSymbol = true) => {
    if (!amount || isNaN(amount)) return showSymbol ? '₹0' : '0';
    
    return new Intl.NumberFormat('en-IN', {
        style: showSymbol ? 'currency' : 'decimal',
        currency: 'INR',
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
    }).format(amount);
};

// Connection Status Indicator Component
const ConnectionStatusIndicator = ({ status, lastUpdate }) => {
    const getStatusConfig = () => {
        switch (status) {
            case 'connected':
                return {
                    icon: Wifi,
                    text: 'Connected',
                    bgClass: 'bg-green-500/20 border-green-500/30',
                    textClass: 'text-green-300',
                    iconClass: 'text-green-400'
                };
            case 'connecting':
                return {
                    icon: RefreshCw,
                    text: 'Connecting...',
                    bgClass: 'bg-yellow-500/20 border-yellow-500/30',
                    textClass: 'text-yellow-300',
                    iconClass: 'text-yellow-400 animate-spin'
                };
            case 'error':
                return {
                    icon: WifiOff,
                    text: 'Connection Error',
                    bgClass: 'bg-red-500/20 border-red-500/30',
                    textClass: 'text-red-300',
                    iconClass: 'text-red-400'
                };
            default:
                return {
                    icon: WifiOff,
                    text: 'Disconnected',
                    bgClass: 'bg-gray-500/20 border-gray-500/30',
                    textClass: 'text-gray-300',
                    iconClass: 'text-gray-400'
                };
        }
    };

    const config = getStatusConfig();
    const StatusIcon = config.icon;

    return (
        <div className={`flex items-center space-x-2 px-3 py-1.5 ${config.bgClass} border rounded-full`}>
            <StatusIcon size={16} className={config.iconClass} />
            <span className={`text-sm font-medium ${config.textClass}`}>
                {config.text}
            </span>
            {lastUpdate && status === 'connected' && (
                <span className="text-xs text-gray-400 ml-2">
                    {new Date(lastUpdate).toLocaleTimeString()}
                </span>
            )}
        </div>
    );
};

// Enhanced Dashboard Component
const EnhancedDashboard = ({ realTimeData, onRefresh, connectionStatus }) => {
    const [isRefreshing, setIsRefreshing] = useState(false);

    const handleRefresh = async () => {
        setIsRefreshing(true);
        try {
            await onRefresh();
        } finally {
            setIsRefreshing(false);
        }
    };

    const clusterHealth = realTimeData?.clusterHealth || {
        status: 'disconnected',
        score: 0,
        nodes: { ready: 0, total: 0 },
        pods: { running: 0, total: 0, pending: 0, failed: 0 }
    };

    const finOpsData = realTimeData?.finOpsData || {};
    const costData = finOpsData?.cost_data || finOpsData || {};

    const getHealthColor = () => {
        switch (clusterHealth.status) {
            case 'healthy': return 'from-green-500 to-emerald-500';
            case 'warning': return 'from-yellow-500 to-orange-500';
            case 'critical': return 'from-red-500 to-pink-500';
            default: return 'from-gray-500 to-slate-500';
        }
    };

    return (
        <div className="flex-1 p-8 space-y-8 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center mb-2">
                        <div className="bg-gradient-to-r from-blue-400 to-cyan-400 p-3 rounded-2xl mr-4">
                            <Home size={28} className="text-white" />
                        </div>
                        Live FinOps Dashboard
                    </h1>
                    <p className="text-slate-400">Real-time Azure & Kubernetes monitoring with AI insights</p>
                </div>
                <div className="flex items-center space-x-4">
                    <ConnectionStatusIndicator 
                        status={connectionStatus} 
                        lastUpdate={realTimeData?.lastUpdated}
                    />
                    <button 
                        onClick={handleRefresh}
                        disabled={isRefreshing}
                        className="px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white rounded-xl transition-all duration-200 hover:scale-105 disabled:opacity-50 flex items-center"
                    >
                        <RefreshCw className={`mr-2 ${isRefreshing ? 'animate-spin' : ''}`} size={16} />
                        Refresh
                    </button>
                </div>
            </div>

            {/* Cluster Health Overview */}
            <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-2xl p-8 border border-slate-700/50">
                <div className="flex items-center justify-between mb-6">
                    <h3 className="text-xl font-semibold text-white flex items-center">
                        <div className="bg-gradient-to-r from-green-400 to-emerald-400 p-2 rounded-xl mr-3">
                            <Activity size={20} className="text-white" />
                        </div>
                        Kubernetes Cluster Health
                    </h3>
                    <div className={`px-4 py-2 rounded-full text-sm font-bold text-white capitalize bg-gradient-to-r ${getHealthColor()}`}>
                        {clusterHealth.status} ({clusterHealth.score}%)
                    </div>
                </div>
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                    <div className="text-center p-6 bg-gradient-to-br from-blue-500/10 to-cyan-500/10 rounded-2xl border border-blue-500/20">
                        <div className="bg-gradient-to-r from-blue-400 to-cyan-400 p-3 rounded-2xl mx-auto w-fit mb-3">
                            <Server size={24} className="text-white" />
                        </div>
                        <p className="font-medium text-slate-400 mb-2">Nodes</p>
                        <p className="text-3xl font-bold text-white">
                            {clusterHealth.nodes?.ready || 0} / {clusterHealth.nodes?.total || 0}
                        </p>
                        <p className="text-xs text-green-400">Ready</p>
                    </div>
                    
                    <div className="text-center p-6 bg-gradient-to-br from-green-500/10 to-emerald-500/10 rounded-2xl border border-green-500/20">
                        <div className="bg-gradient-to-r from-green-400 to-emerald-400 p-3 rounded-2xl mx-auto w-fit mb-3">
                            <CheckCircle size={24} className="text-white" />
                        </div>
                        <p className="font-medium text-slate-400 mb-2">Running Pods</p>
                        <p className="text-3xl font-bold text-green-400">
                            {clusterHealth.pods?.running || 0}
                        </p>
                        <p className="text-xs text-slate-400">Active</p>
                    </div>
                    
                    <div className="text-center p-6 bg-gradient-to-br from-yellow-500/10 to-orange-500/10 rounded-2xl border border-yellow-500/20">
                        <div className="bg-gradient-to-r from-yellow-400 to-orange-400 p-3 rounded-2xl mx-auto w-fit mb-3">
                            <Clock size={24} className="text-white" />
                        </div>
                        <p className="font-medium text-slate-400 mb-2">Pending</p>
                        <p className="text-3xl font-bold text-yellow-400">
                            {clusterHealth.pods?.pending || 0}
                        </p>
                        <p className="text-xs text-slate-400">Waiting</p>
                    </div>
                    
                    <div className="text-center p-6 bg-gradient-to-br from-red-500/10 to-pink-500/10 rounded-2xl border border-red-500/20">
                        <div className="bg-gradient-to-r from-red-400 to-pink-400 p-3 rounded-2xl mx-auto w-fit mb-3">
                            <AlertTriangle size={24} className="text-white" />
                        </div>
                        <p className="font-medium text-slate-400 mb-2">Failed</p>
                        <p className="text-3xl font-bold text-red-400">
                            {clusterHealth.pods?.failed || 0}
                        </p>
                        <p className="text-xs text-slate-400">Errors</p>
                    </div>
                </div>
            </div>

            {/* Azure FinOps Overview */}
            <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-2xl p-8 border border-slate-700/50">
                <h3 className="text-xl font-semibold text-white flex items-center mb-6">
                    <div className="bg-gradient-to-r from-yellow-400 to-orange-400 p-2 rounded-xl mr-3">
                        <DollarSign size={20} className="text-white" />
                    </div>
                    Azure Cost Management (FinOps)
                </h3>
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-6">
                    <div className="text-center p-6 bg-gradient-to-br from-blue-500/10 to-cyan-500/10 rounded-2xl border border-blue-500/20">
                        <div className="bg-gradient-to-r from-blue-400 to-cyan-400 p-3 rounded-2xl mx-auto w-fit mb-3">
                            <DollarSign size={24} className="text-white" />
                        </div>
                        <p className="font-medium text-slate-400 mb-2">Monthly Cost</p>
                        <p className="text-3xl font-bold text-white">
                            {formatINR(costData?.total_monthly_cost || 0)}
                        </p>
                        <p className="text-xs text-slate-400">Total Azure Spend</p>
                    </div>
                    
                    <div className="text-center p-6 bg-gradient-to-br from-green-500/10 to-emerald-500/10 rounded-2xl border border-green-500/20">
                        <div className="bg-gradient-to-r from-green-400 to-emerald-400 p-3 rounded-2xl mx-auto w-fit mb-3">
                            <TrendingUp size={24} className="text-white" />
                        </div>
                        <p className="font-medium text-slate-400 mb-2">Potential Savings</p>
                        <p className="text-3xl font-bold text-green-400">
                            {formatINR(costData?.total_potential_savings || 0)}
                        </p>
                        <p className="text-xs text-slate-400">AI Recommended</p>
                    </div>
                    
                    <div className="text-center p-6 bg-gradient-to-br from-purple-500/10 to-pink-500/10 rounded-2xl border border-purple-500/20">
                        <div className="bg-gradient-to-r from-purple-400 to-pink-400 p-3 rounded-2xl mx-auto w-fit mb-3">
                            <Layers size={24} className="text-white" />
                        </div>
                        <p className="font-medium text-slate-400 mb-2">Resources</p>
                        <p className="text-3xl font-bold text-white">
                            {costData?.resource_count || 0}
                        </p>
                        <p className="text-xs text-slate-400">Monitored</p>
                    </div>
                    
                    <div className="text-center p-6 bg-gradient-to-br from-orange-500/10 to-red-500/10 rounded-2xl border border-orange-500/20">
                        <div className="bg-gradient-to-r from-orange-400 to-red-400 p-3 rounded-2xl mx-auto w-fit mb-3">
                            <Sparkles size={24} className="text-white" />
                        </div>
                        <p className="font-medium text-slate-400 mb-2">Optimizations</p>
                        <p className="text-3xl font-bold text-yellow-400">
                            {costData?.optimization_opportunities || 3}
                        </p>
                        <p className="text-xs text-slate-400">Available</p>
                    </div>
                </div>

                {/* Cost Breakdown */}
                <div>
                    <h4 className="font-semibold text-white mb-4 flex items-center">
                        <BarChart3 size={20} className="mr-2 text-blue-400" />
                        Cost Breakdown by Service (INR)
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {(() => {
                            let costByType = {};
                            
                            if (costData?.cost_by_type) {
                                costByType = costData.cost_by_type;
                            } else if (costData?.cost_by_service) {
                                costByType = costData.cost_by_service;
                            } else if (finOpsData?.cost_by_type) {
                                costByType = finOpsData.cost_by_type;
                            }

                            const totalCost = costData?.total_monthly_cost || 0;
                            
                            if (!costByType || Object.keys(costByType).length === 0) {
                                return (
                                    <div className="col-span-full text-center py-8">
                                        <Cloud className="mx-auto mb-4 text-slate-400" size={48} />
                                        <p className="text-slate-400 text-lg">Loading cost breakdown...</p>
                                        <p className="text-slate-500 text-sm mt-2">
                                            {connectionStatus === 'connected' 
                                                ? 'Fetching data from Azure Cost Management API' 
                                                : 'Connect to MCP server for live data'
                                            }
                                        </p>
                                    </div>
                                );
                            }
                            
                            return Object.entries(costByType).map(([type, cost]) => {
                                const costValue = typeof cost === 'object' ? (cost?.cost || 0) : (cost || 0);
                                const percentage = totalCost > 0 ? (costValue / totalCost) * 100 : 0;
                                
                                return (
                                    <div key={type} className="bg-slate-700/30 p-4 rounded-xl hover:bg-slate-700/50 transition-all duration-300 group">
                                        <div className="flex justify-between items-center mb-3">
                                            <span className="text-slate-300 font-medium text-sm truncate" title={type}>
                                                {type}
                                            </span>
                                            <span className="text-white font-bold">
                                                {formatINR(costValue)}
                                            </span>
                                        </div>
                                        <div className="w-full bg-slate-600/50 rounded-full h-2">
                                            <div 
                                                className="bg-gradient-to-r from-blue-500 to-cyan-500 h-2 rounded-full transition-all duration-1000 group-hover:from-blue-400 group-hover:to-cyan-400" 
                                                style={{ 
                                                    width: `${Math.min(Math.max(percentage, 0), 100)}%` 
                                                }}
                                            ></div>
                                        </div>
                                        <div className="mt-2 text-xs text-slate-400">
                                            {percentage.toFixed(1)}% of total
                                        </div>
                                    </div>
                                );
                            });
                        })()}
                    </div>
                </div>
            </div>

            {/* AI Recommendations */}
            {(finOpsData?.ai_analysis || costData?.ai_analysis) && (
                <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-2xl p-8 border border-slate-700/50">
                    <h3 className="text-xl font-semibold text-white flex items-center mb-6">
                        <div className="bg-gradient-to-r from-purple-400 to-pink-400 p-2 rounded-xl mr-3">
                            <Sparkles size={20} className="text-white" />
                        </div>
                        AI-Powered Recommendations
                    </h3>
                    <div className="bg-slate-700/30 p-6 rounded-xl">
                        <pre className="text-slate-200 whitespace-pre-wrap font-mono text-sm">
                            {finOpsData?.ai_analysis || costData?.ai_analysis}
                        </pre>
                    </div>
                </div>
            )}

            {/* Connection Status Details */}
            <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-2xl p-6 border border-slate-700/50">
                <h4 className="font-semibold text-white mb-4 flex items-center">
                    <Globe size={20} className="mr-2 text-green-400" />
                    System Status
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-slate-700/30 p-4 rounded-xl">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-slate-300 font-medium">Backend API</span>
                            <ConnectionStatusIndicator status={connectionStatus} />
                        </div>
                        <p className="text-xs text-slate-400">FastAPI MCP Server</p>
                    </div>
                    <div className="bg-slate-700/30 p-4 rounded-xl">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-slate-300 font-medium">Kubernetes</span>
                            <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                                clusterHealth.status === 'healthy' 
                                ? 'bg-green-500/20 text-green-300' 
                                : clusterHealth.status === 'disconnected'
                                ? 'bg-red-500/20 text-red-300'
                                : 'bg-yellow-500/20 text-yellow-300'
                            }`}>
                                {clusterHealth.status}
                            </span>
                        </div>
                        <p className="text-xs text-slate-400">Cluster API Connection</p>
                    </div>
                    <div className="bg-slate-700/30 p-4 rounded-xl">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-slate-300 font-medium">Azure Integration</span>
                            <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                                costData?.data_source === 'azure_api' 
                                ? 'bg-green-500/20 text-green-300' 
                                : 'bg-yellow-500/20 text-yellow-300'
                            }`}>
                                {costData?.data_source || 'unknown'}
                            </span>
                        </div>
                        <p className="text-xs text-slate-400">Cost Management API</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

// Enhanced Chat Panel
const EnhancedChatPanel = ({ 
    messages, 
    input, 
    setInput, 
    isLoading, 
    handleSendMessage, 
    handleFileUpload, 
    handleVoiceRecord, 
    isRecording, 
    connectionStatus,
    realTimeData 
}) => {
    const messagesEndRef = useRef(null);
    const [isModalOpen, setIsModalOpen] = useState(false);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const formatAIMessage = (text) => {
        // Check if the text contains code blocks or commands
        if (text.includes('```')) {
            // Split by code blocks and format
            const parts = text.split('```');
            return (
                <div className="space-y-2">
                    {parts.map((part, index) => {
                        if (index % 2 === 1) {
                            // This is a code block
                            const [language, ...codeLines] = part.split('\n');
                            const code = codeLines.join('\n');
                            return (
                                <div key={index} className="bg-slate-900/50 rounded-lg p-3 overflow-x-auto">
                                    <div className="text-xs text-slate-400 mb-2">{language || 'code'}</div>
                                    <pre className="text-sm text-slate-200 font-mono">{code}</pre>
                                </div>
                            );
                        }
                        // Regular text
                        return <div key={index} className="whitespace-pre-wrap">{part}</div>;
                    })}
                </div>
            );
        }
        return <div className="whitespace-pre-wrap">{text}</div>;
    };

    const getQuickActions = () => [
        {
            icon: DollarSign,
            label: "What's my Azure spend?",
            query: "Show me my current Azure costs and optimization opportunities"
        },
        {
            icon: Server,
            label: "Scale deployment",
            query: "Help me scale my nginx deployment to 3 replicas"
        },
        {
            icon: Activity,
            label: "Cluster health",
            query: "What's the current health status of my Kubernetes cluster?"
        },
        {
            icon: TrendingUp,
            label: "Cost optimization",
            query: "Analyze my costs and suggest optimization strategies"
        }
    ];

    const handleQuickAction = (query) => {
        setInput(query);
        const event = { preventDefault: () => {} };
        handleSendMessage(event, query);
    };

    // Safely extract cost data for status cards
    const costData = realTimeData?.finOpsData?.cost_data || realTimeData?.finOpsData || {};

    return (
        <div className="flex-1 flex flex-col h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
            <header className="p-6 border-b border-slate-700/50 bg-slate-900/50 backdrop-blur-xl">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white flex items-center mb-2">
                            <div className="bg-gradient-to-r from-purple-400 to-pink-400 p-2 rounded-xl mr-3">
                                <Sparkles size={24} className="text-white" />
                            </div>
                            AI-Powered FinOps Assistant
                        </h1>
                        <p className="text-slate-400 text-sm">Connected to live Azure & Kubernetes data with OpenAI integration</p>
                    </div>
                    <div className="flex items-center space-x-3">
                        <ConnectionStatusIndicator status={connectionStatus} lastUpdate={realTimeData?.lastUpdated} />
                    </div>
                </div>
            </header>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {messages.length === 0 && (
                    <div className="text-center mt-12">
                        <div className="mb-8">
                            <div className="bg-gradient-to-r from-blue-400 to-cyan-400 p-4 rounded-2xl mx-auto w-fit mb-4">
                                <Activity size={48} className="text-white" />
                            </div>
                            <h3 className="text-2xl font-bold text-white mb-3">Welcome to your AI-Powered FinOps Assistant!</h3>
                            <p className="text-slate-400 text-lg">Connected to live Azure and Kubernetes data with intelligent analysis</p>
                        </div>
                        
                        {/* Quick Actions */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl mx-auto mb-8">
                            {getQuickActions().map((action, index) => {
                                const Icon = action.icon;
                                return (
                                    <button
                                        key={index}
                                        onClick={() => handleQuickAction(action.query)}
                                        className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 p-6 rounded-2xl border border-slate-700/50 backdrop-blur-sm hover:scale-105 transition-transform duration-300 text-left group"
                                    >
                                        <div className="bg-gradient-to-r from-blue-400 to-cyan-400 p-2 rounded-xl w-fit mb-4 group-hover:scale-110 transition-transform">
                                            <Icon size={20} className="text-white" />
                                        </div>
                                        <h4 className="font-semibold text-white mb-2">{action.label}</h4>
                                        <p className="text-sm text-slate-400">{action.query}</p>
                                    </button>
                                );
                            })}
                        </div>

                        {/* Real-time Status Cards with INR formatting */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
                            <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 p-6 rounded-2xl border border-slate-700/50">
                                <div className="flex items-center mb-3">
                                    <Server className="mr-2 text-blue-400" size={20} />
                                    <h4 className="font-semibold text-white">Cluster Status</h4>
                                </div>
                                <p className="text-2xl font-bold text-white mb-1">
                                    {realTimeData?.clusterHealth?.status || 'Unknown'}
                                </p>
                                <p className="text-sm text-slate-400">
                                    {realTimeData?.clusterHealth?.nodes?.ready || 0} nodes ready
                                </p>
                            </div>
                            
                            <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 p-6 rounded-2xl border border-slate-700/50">
                                <div className="flex items-center mb-3">
                                    <DollarSign className="mr-2 text-green-400" size={20} />
                                    <h4 className="font-semibold text-white">Monthly Cost</h4>
                                </div>
                                <p className="text-2xl font-bold text-white mb-1">
                                    {formatINR(costData?.total_monthly_cost || 0)}
                                </p>
                                <p className="text-sm text-slate-400">Azure spending</p>
                            </div>
                            
                            <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 p-6 rounded-2xl border border-slate-700/50">
                                <div className="flex items-center mb-3">
                                    <TrendingUp className="mr-2 text-yellow-400" size={20} />
                                    <h4 className="font-semibold text-white">Savings</h4>
                                </div>
                                <p className="text-2xl font-bold text-white mb-1">
                                    {formatINR(costData?.total_potential_savings || 0)}
                                </p>
                                <p className="text-sm text-slate-400">Potential savings</p>
                            </div>
                        </div>

                        {connectionStatus !== 'connected' && (
                            <div className="mt-6 p-4 bg-yellow-500/20 border border-yellow-500/30 rounded-xl max-w-2xl mx-auto">
                                <div className="flex items-center justify-center mb-2">
                                    <AlertTriangle className="mr-2 text-yellow-400" size={20} />
                                    <p className="font-semibold text-yellow-300">Backend Connection Required</p>
                                </div>
                                <p className="text-yellow-200 text-sm">
                                    Start your Python MCP server to access live Azure and Kubernetes data
                                </p>
                                <p className="text-yellow-200 text-xs mt-2">
                                    Run: <code className="bg-black/30 px-2 py-1 rounded">python main.py</code>
                                </p>
                            </div>
                        )}
                    </div>
                )}
                
                {messages.map((message, index) => (
                    <div key={index} className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div
                            className={`max-w-2xl px-6 py-4 rounded-2xl shadow-lg backdrop-blur-sm ${
                                message.sender === 'user'
                                    ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white ml-12'
                                    : 'bg-gradient-to-br from-slate-800/80 to-slate-900/80 text-slate-100 border border-slate-700/50 mr-12'
                            }`}
                        >
                            {message.sender === 'ai' && (
                                <div className="flex items-center mb-2">
                                    <div className="bg-gradient-to-r from-purple-400 to-pink-400 p-1.5 rounded-lg mr-2">
                                        <Sparkles size={14} className="text-white" />
                                    </div>
                                    <span className="text-xs font-medium text-slate-400">AI FinOps Assistant</span>
                                    {connectionStatus === 'connected' && (
                                        <div className="ml-2 w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                                    )}
                                </div>
                            )}
                            <div className="leading-relaxed">
                                {message.sender === 'ai' ? formatAIMessage(message.text) : message.text}
                            </div>
                            {message.actions && (
                                <div className="mt-4 space-y-2">
                                    {message.actions.map((action, idx) => ( 
                                        <button
                                            key={idx}
                                            onClick={action.onClick}
                                            className="block w-full text-left px-4 py-2 bg-slate-700/50 hover:bg-slate-600/50 rounded-xl text-sm transition-all duration-200 hover:scale-105 border border-slate-600/30"
                                        >
                                            {action.label}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                ))}
                
                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/80 text-slate-100 px-6 py-4 rounded-2xl border border-slate-700/50 backdrop-blur-sm">
                            <div className="flex items-center space-x-3">
                                <div className="bg-gradient-to-r from-purple-400 to-pink-400 p-1.5 rounded-lg">
                                    <Sparkles size={14} className="text-white" />
                                </div>
                                <div className="flex items-center space-x-2">
                                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-400 border-t-transparent"></div>
                                    <span>AI is analyzing your live data with Azure OpenAI...</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSendMessage} className="p-6 border-t border-slate-700/50 bg-slate-900/50 backdrop-blur-xl">
                <div className="flex items-center gap-3 bg-slate-800/50 rounded-2xl p-2 border border-slate-700/50">
                    <button
                        type="button"
                        onClick={() => setIsModalOpen(true)}
                        className="p-3 rounded-xl text-slate-400 hover:bg-slate-700/50 hover:text-white transition-all duration-200 hover:scale-110"
                        title="Upload YAML Manifest"
                    >
                        <Paperclip size={20} />
                    </button>
                    <button
                        type="button"
                        onClick={handleVoiceRecord}
                        className={`p-3 rounded-xl transition-all duration-200 hover:scale-110 ${
                            isRecording 
                                ? 'bg-red-500 text-white animate-pulse' 
                                : 'text-slate-400 hover:bg-slate-700/50 hover:text-white'
                        }`}
                        title={isRecording ? "Stop Recording" : "Start Voice Command"}
                    >
                        {isRecording ? <Square size={20} /> : <Mic size={20} />}
                    </button>
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        className="flex-1 px-4 py-3 bg-transparent text-white placeholder-slate-400 focus:outline-none"
                        placeholder={connectionStatus === 'connected' 
                            ? "Ask about Azure costs, scale deployments, analyze cluster health..." 
                            : "Connect to MCP server for live AI analysis..."
                        }
                        disabled={isLoading}
                    />
                    <button
                        type="submit"
                        className="p-3 rounded-xl bg-gradient-to-r from-blue-600 to-blue-700 text-white hover:from-blue-500 hover:to-blue-600 transition-all duration-200 hover:scale-110 disabled:opacity-50"
                        disabled={isLoading || !input.trim()}
                    >
                        <Send size={20} />
                    </button>
                </div>
                {connectionStatus !== 'connected' && (
                    <p className="text-xs text-slate-500 mt-2 text-center">
                        MCP server connection required for AI-powered responses
                    </p>
                )}
            </form>
            
            <FileUploadModal show={isModalOpen} onClose={() => setIsModalOpen(false)} onFileSelect={handleFileUpload} />
        </div>
    );
};

// Enhanced File Upload Modal
const FileUploadModal = ({ show, onClose, onFileSelect }) => {
    if (!show) return null;

    const handleFileChange = (e) => {
        if (e.target.files.length > 0) {
            onFileSelect(e.target.files[0]);
        }
        onClose();
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="bg-gradient-to-br from-slate-800 to-slate-900 p-8 rounded-2xl shadow-2xl w-96 border border-slate-700/50">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-xl font-semibold text-white flex items-center">
                        <Paperclip className="mr-2 text-blue-400" size={20} />
                        Upload File
                    </h2>
                    <button 
                        onClick={onClose} 
                        className="text-slate-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-slate-700/50"
                    >
                        <X size={20} />
                    </button>
                </div>
                <div className="space-y-6">
                    <div className="border-2 border-dashed border-slate-600 rounded-xl p-6 text-center hover:border-blue-400 transition-colors">
                        <input
                            type="file"
                            onChange={handleFileChange}
                            accept=".yaml,.yml,.json,.png,.jpg,.jpeg,.svg"
                            className="hidden"
                            id="file-upload"
                        />
                        <label htmlFor="file-upload" className="cursor-pointer">
                            <div className="text-slate-400 mb-2">
                                <Cloud size={32} className="mx-auto mb-2" />
                            </div>
                            <p className="text-sm text-slate-300 mb-1">Click to upload or drag and drop</p>
                            <p className="text-xs text-slate-500">YAML, JSON manifests, and images</p>
                        </label>
                    </div>
                </div>
            </div>
        </div>
    );
};

// Enhanced Sidebar
const EnhancedSidebar = ({ activeSection, setActiveSection, connectionStatus, realTimeData }) => {
    const sections = [
        { id: 'chat', label: 'AI Assistant', icon: Sparkles, gradient: 'from-purple-500 to-pink-500' },
        { id: 'dashboard', label: 'Dashboard', icon: Home, gradient: 'from-blue-500 to-cyan-500' },
        { id: 'deployments', label: 'Deployments', icon: Rocket, gradient: 'from-green-500 to-emerald-500' },
        { id: 'resources', label: 'Resources', icon: Layers, gradient: 'from-orange-500 to-red-500' },
        { id: 'finops', label: 'FinOps', icon: TrendingUp, gradient: 'from-yellow-500 to-orange-500' },
        { id: 'manifests', label: 'Apply YAML', icon: FileText, gradient: 'from-indigo-500 to-purple-500' },
    ];
    
    const getConnectionStatusColor = () => {
        switch (connectionStatus) {
            case 'connected': return 'from-green-900/20 to-emerald-900/20 border-green-500/20';
            case 'error': return 'from-red-900/20 to-orange-900/20 border-red-500/20';
            default: return 'from-yellow-900/20 to-orange-900/20 border-yellow-500/20';
        }
    };

    const getConnectionStatusText = () => {
        switch (connectionStatus) {
            case 'connected': return { text: 'MCP Server Connected', icon: '✅' };
            case 'error': return { text: 'Connection Error', icon: '❌' };
            default: return { text: 'Connecting...', icon: '🔄' };
        }
    };

    // Safely extract cost data for sidebar stats
    const costData = realTimeData?.finOpsData?.cost_data || realTimeData?.finOpsData || {};
    
    return (
        <aside className="w-72 p-6 flex flex-col bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-r border-slate-700/50 backdrop-blur-xl">
            <div className="mb-8">
                <div className="text-2xl font-bold text-white flex items-center mb-2">
                    <div className="bg-gradient-to-r from-blue-400 to-cyan-400 p-2 rounded-xl mr-3">
                        <Cloud size={24} className="text-white" />
                    </div>
                    FinKubeOps AI
                </div>
                <p className="text-slate-400 text-sm">AI-powered Kubernetes FinOps with live Azure integration</p>
            </div>
            
            <nav className="flex-1">
                <ul className="space-y-2">
                    {sections.map((section) => {
                        const Icon = section.icon;
                        const isActive = activeSection === section.id;
                        return (
                            <li key={section.id}>
                                <button
                                    onClick={() => setActiveSection(section.id)}
                                    className={`flex items-center w-full p-4 rounded-xl transition-all duration-300 group ${
                                        isActive 
                                            ? 'bg-gradient-to-r ' + section.gradient + ' text-white shadow-lg scale-105' 
                                            : 'text-slate-400 hover:bg-slate-800/50 hover:text-white hover:scale-105'
                                    }`}
                                >
                                    <div className={`p-2 rounded-lg mr-3 transition-all duration-300 ${
                                        isActive 
                                            ? 'bg-white/20' 
                                            : 'bg-slate-700/50 group-hover:bg-slate-600/50'
                                    }`}>
                                        <Icon size={18} />
                                    </div>
                                    <span className="font-medium">{section.label}</span>
                                    {isActive && (
                                        <ArrowRight size={16} className="ml-auto opacity-80" />
                                    )}
                                </button>
                            </li>
                        );
                    })}
                </ul>
            </nav>
            
            {/* Connection Status */}
            <div className={`mt-8 p-4 bg-gradient-to-r ${getConnectionStatusColor()} border rounded-xl`}>
                <div className="flex items-center mb-2">
                    <span className="mr-2">{getConnectionStatusText().icon}</span>
                    <p className="font-semibold text-white text-sm">{getConnectionStatusText().text}</p>
                </div>
                <p className="text-slate-300 text-xs">
                    {connectionStatus === 'connected' ? 'Real-time Azure & K8s data' : 'Check MCP server connection'}
                </p>
            </div>

            {/* Quick Stats with INR formatting */}
            {connectionStatus === 'connected' && realTimeData && (
                <div className="mt-4 p-4 bg-slate-800/30 rounded-xl border border-slate-700/50">
                    <h4 className="text-sm font-semibold text-white mb-3">Quick Stats</h4>
                    <div className="space-y-2 text-xs">
                        <div className="flex justify-between">
                            <span className="text-slate-400">Nodes Ready:</span>
                            <span className="text-white font-medium">
                                {realTimeData.clusterHealth?.nodes?.ready || 0}/{realTimeData.clusterHealth?.nodes?.total || 0}
                            </span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-slate-400">Monthly Cost:</span>
                            <span className="text-green-400 font-medium">
                                {formatINR(costData?.total_monthly_cost || 0, false)}
                            </span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-slate-400">Potential Savings:</span>
                            <span className="text-yellow-400 font-medium">
                                {formatINR(costData?.total_potential_savings || 0, false)}
                            </span>
                        </div>
                    </div>
                </div>
            )}
        </aside>
    );
};

// Main App Component
export default function EnhancedFinKubeOpsApp() {
    const [activeSection, setActiveSection] = useState('chat');
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    
    // FIXED: Separate state for different data types
    const [realTimeData, setRealTimeData] = useState({
        clusterHealth: null,
        finOpsData: null,
        lastUpdated: null
    });

    const [connectionStatus, setConnectionStatus] = useState('disconnected');
    const [wsManager, setWsManager] = useState(null);

    // FIXED: WebSocket message handling callback defined first
    const handleWebSocketMessage = useCallback((data) => {
        console.log('📡 WebSocket message:', data.type);
        
        switch (data.type) {
            case 'fast_initial_status':
            case 'background_update':
                setRealTimeData(prev => {
                    const newData = { ...prev };

                    // Update cluster health
                    if (data.cluster_health) {
                        newData.clusterHealth = data.cluster_health;
                    }

                    // Update cost summary only (not full finOps data)
                    if (data.cost_summary) {
                        newData.finOpsData = {
                            ...prev.finOpsData,
                            cost_data: {
                                ...prev.finOpsData?.cost_data,
                                total_monthly_cost: data.cost_summary.monthly_cost,
                                total_potential_savings: data.cost_summary.potential_savings,
                                resource_count: data.cost_summary.resource_count,
                            }
                        };
                    }

                    newData.lastUpdated = data.timestamp;
                    return newData;
                });
                break;
                
            case 'error':
                console.error('Backend error:', data.message);
                break;
        }
    }, []);

    // WebSocket error handler
    const handleWebSocketError = useCallback((error) => {
        console.error('❌ WebSocket error:', error);
        setConnectionStatus('error');
    }, []);

    // FIXED: Load FinOps data independently
    const loadFinOpsData = useCallback(async () => {
        try {
            console.log('📊 Loading FinOps data independently...');
            
            const finOpsResponse = await EnhancedAPIClient.getFinOpsOverview();
            
            if (finOpsResponse) {
                setRealTimeData(prev => ({
                    ...prev,
                    finOpsData: finOpsResponse,
                    lastUpdated: new Date().toISOString()
                }));
                console.log('✅ FinOps data loaded successfully:', finOpsResponse);
            }
            
        } catch (error) {
            console.error('❌ Error loading FinOps data:', error);
            // Set fallback data
            setRealTimeData(prev => ({
                ...prev,
                finOpsData: {
                    cost_data: {
                        total_monthly_cost: 0,
                        total_potential_savings: 0,
                        resource_count: 0,
                        cost_by_type: {},
                        data_source: 'error'
                    }
                }
            }));
        }
    }, []);

    // FIXED: Load cluster data independently
    const loadClusterData = useCallback(async () => {
        try {
            console.log('📊 Loading cluster data independently...');
            
            const clusterResponse = await EnhancedAPIClient.getClusterStatus();
            
            if (clusterResponse) {
                setRealTimeData(prev => ({
                    ...prev,
                    clusterHealth: clusterResponse.cluster_health || clusterResponse,
                    lastUpdated: new Date().toISOString()
                }));
                console.log('✅ Cluster data loaded successfully');
            }
            
        } catch (error) {
            console.error('❌ Error loading cluster data:', error);
            setRealTimeData(prev => ({
                ...prev,
                clusterHealth: {
                    status: 'disconnected',
                    score: 0,
                    nodes: { ready: 0, total: 0 },
                    pods: { running: 0, total: 0, pending: 0, failed: 0 }
                }
            }));
        }
    }, []);

    // Initialize app with proper separation
    useEffect(() => {
        const initializeApp = async () => {
            try {
                console.log('🚀 Initializing Enhanced FinKubeOps...');
                
                // Test backend connection
                try {
                    const health = await EnhancedAPIClient.getHealth();
                    console.log('✅ Backend health check passed:', health);
                    setConnectionStatus('connected');
                } catch (error) {
                    console.warn('⚠️ Backend health check failed:', error);
                    setConnectionStatus('error');
                }

                // Load data independently and in parallel
                await Promise.allSettled([
                    loadFinOpsData(),
                    loadClusterData()
                ]);

                // Initialize WebSocket
                const ws = new EnhancedWebSocketManager(
                    handleWebSocketMessage,
                    handleWebSocketError,
                    setConnectionStatus
                );
                
                ws.connect();
                setWsManager(ws);

            } catch (error) {
                console.error('❌ App initialization error:', error);
                setConnectionStatus('error');
            }
        };

        initializeApp();

        return () => {
            if (wsManager) {
                wsManager.disconnect();
            }
        };
    }, [handleWebSocketMessage, handleWebSocketError, loadFinOpsData, loadClusterData]);

    // FIXED: Chat handling without FinOps conflicts
    const handleSendMessage = async (e, quickQuery = null) => {
        e.preventDefault();
        const query = quickQuery || input;
        if (!query.trim()) return;

        const userMessage = { 
            sender: 'user', 
            text: query,
            timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            if (connectionStatus === 'connected') {
                // FIXED: Use light context to prevent conflicts
                const lightContext = {
                    clusterHealth: realTimeData?.clusterHealth,
                    finOpsSummary: {
                        totalCost: realTimeData?.finOpsData?.cost_data?.total_monthly_cost || 0,
                        potentialSavings: realTimeData?.finOpsData?.cost_data?.total_potential_savings || 0
                    },
                    connectionStatus,
                    activeSection
                };

                const response = await EnhancedAPIClient.chatWithAI(query, { realTimeData: lightContext });

                if (response.response) {
                    addAIMessage(response.response, response.actions);
                } else {
                    addAIMessage('I received your message but got an empty response. Please try again.');
                }
            } else {
                addAIMessage(
                    '🔌 I need a connection to the MCP server to provide AI-powered responses with live data.\n\n' +
                    'However, I can still help with general Kubernetes and FinOps questions! What would you like to know?'
                );
            }
        } catch (error) {
            console.error('Chat error:', error);
            addAIMessage(
                `❌ Sorry, I encountered an error: ${error.message}\n\n` +
                'Please check your MCP server connection and try again.'
            );
        } finally {
            setIsLoading(false);
        }
    };

    // FIXED: Refresh data function
    const handleRefreshData = useCallback(async () => {
        await Promise.allSettled([
            loadFinOpsData(),
            loadClusterData()
        ]);
    }, [loadFinOpsData, loadClusterData]);

    const addAIMessage = (text, actions = null) => {
        setMessages(prev => [...prev, { 
            sender: 'ai', 
            text, 
            actions,
            timestamp: new Date().toISOString()
        }]);
    };

    // Placeholder functions for features not yet implemented
    const handleFileUpload = (file) => {
        console.log('File upload:', file.name);
        addAIMessage(`📎 I received your file "${file.name}" but file processing is not yet implemented. This will be available in a future update.`);
    };

    const handleVoiceRecord = () => {
        console.log('Voice recording not yet implemented');
        addAIMessage('🎤 Voice recording feature is coming soon! For now, please type your questions.');
    };

    const renderContent = () => {
        switch (activeSection) {
            case 'dashboard':
                return (
                    <EnhancedDashboard 
                        realTimeData={realTimeData}
                        onRefresh={handleRefreshData}
                        connectionStatus={connectionStatus}
                    />
                );
            case 'deployments':
                return (
                    <DeploymentsPanel 
                        realTimeData={realTimeData}
                        connectionStatus={connectionStatus}
                    />
                );
            case 'resources':
                return (
                    <ResourcesPanel 
                        realTimeData={realTimeData}
                        connectionStatus={connectionStatus}
                    />
                );
            case 'finops':
                return (
                    <FinOpsPanel 
                        realTimeData={realTimeData}
                        connectionStatus={connectionStatus}
                    />
                );
            case 'manifests':
                return (
                    <ManifestsPanel 
                        onApplyManifest={(manifest) => {
                            addAIMessage(`📄 YAML manifest received! Manifest application is not yet implemented but will be available soon.\n\nManifest preview:\n\`\`\`yaml\n${manifest.substring(0, 200)}${manifest.length > 200 ? '...' : ''}\n\`\`\``);
                        }}
                        connectionStatus={connectionStatus}
                    />
                );
            case 'chat':
            default:
                return (
                    <EnhancedChatPanel
                        messages={messages}
                        input={input}
                        setInput={setInput}
                        isLoading={isLoading}
                        handleSendMessage={handleSendMessage}
                        handleFileUpload={handleFileUpload}
                        handleVoiceRecord={handleVoiceRecord}
                        isRecording={false}
                        connectionStatus={connectionStatus}
                        realTimeData={realTimeData}
                    />
                );
        }
    };

    return (
        <div className="flex h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white overflow-hidden">
            <EnhancedSidebar
                activeSection={activeSection}
                setActiveSection={setActiveSection}
                connectionStatus={connectionStatus}
                realTimeData={realTimeData}
            />
            {renderContent()}
        </div>
    );
}

// Additional Panels for different sections

// Deployments Panel
const DeploymentsPanel = ({ realTimeData, connectionStatus }) => {
    const [deployments, setDeployments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedNamespace, setSelectedNamespace] = useState('default');

    useEffect(() => {
        loadDeployments();
    }, [selectedNamespace]);

    const loadDeployments = async () => {
        try {
            setLoading(true);
            const data = await EnhancedAPIClient.getDeployments(selectedNamespace);
            setDeployments(data || []);
        } catch (error) {
            console.error('Failed to load deployments:', error);
            setDeployments([]);
        } finally {
            setLoading(false);
        }
    };

    const handleScaleDeployment = async (name, currentReplicas) => {
        const newReplicas = prompt(`Scale ${name} to how many replicas?`, currentReplicas);
        if (newReplicas === null) return;

        try {
            await EnhancedAPIClient.scaleDeployment(name, selectedNamespace, parseInt(newReplicas));
            await loadDeployments(); // Refresh
        } catch (error) {
            console.error('Failed to scale deployment:', error);
            alert('Failed to scale deployment: ' + error.message);
        }
    };

    return (
        <div className="flex-1 p-8 space-y-8 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 overflow-y-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center mb-2">
                        <div className="bg-gradient-to-r from-green-400 to-emerald-400 p-3 rounded-2xl mr-4">
                            <Rocket size={28} className="text-white" />
                        </div>
                        Kubernetes Deployments
                    </h1>
                    <p className="text-slate-400">Manage and scale your applications</p>
                </div>
                <div className="flex items-center space-x-4">
                    <select 
                        value={selectedNamespace}
                        onChange={(e) => setSelectedNamespace(e.target.value)}
                        className="px-4 py-2 bg-slate-800 text-white rounded-xl border border-slate-700 focus:outline-none focus:border-blue-500"
                    >
                        <option value="default">default</option>
                        <option value="kube-system">kube-system</option>
                        <option value="all">all namespaces</option>
                    </select>
                    <button 
                        onClick={loadDeployments}
                        className="px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white rounded-xl transition-all duration-200 hover:scale-105 flex items-center"
                    >
                        <RefreshCw className={`mr-2 ${loading ? 'animate-spin' : ''}`} size={16} />
                        Refresh
                    </button>
                </div>
            </div>

            {connectionStatus !== 'connected' && (
                <div className="bg-yellow-500/20 border border-yellow-500/30 rounded-xl p-4">
                    <div className="flex items-center">
                        <AlertTriangle className="mr-2 text-yellow-400" size={20} />
                        <p className="text-yellow-300">MCP server connection required to manage deployments</p>
                    </div>
                </div>
            )}

            {loading ? (
                <div className="flex items-center justify-center py-12">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-400 border-t-transparent"></div>
                </div>
            ) : (
                <div className="grid gap-6">
                    {deployments.length === 0 ? (
                        <div className="text-center py-12">
                            <Rocket className="mx-auto mb-4 text-slate-400" size={48} />
                            <p className="text-slate-400 text-lg">No deployments found in {selectedNamespace}</p>
                        </div>
                    ) : (
                        deployments.map((deployment, index) => (
                            <div key={index} className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-2xl p-6 border border-slate-700/50">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <h3 className="text-xl font-semibold text-white mb-2">{deployment.name}</h3>
                                        <p className="text-slate-400">Namespace: {deployment.namespace}</p>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-2xl font-bold text-white mb-1">
                                            {deployment.ready_replicas || 0} / {deployment.replicas || 0}
                                        </div>
                                        <p className="text-slate-400 text-sm">Ready / Desired</p>
                                    </div>
                                </div>
                                
                                <div className="mt-4 flex items-center justify-between">
                                    <div className="flex items-center space-x-4">
                                        <div className={`px-3 py-1 rounded-full text-sm font-semibold ${
                                            (deployment.ready_replicas || 0) === (deployment.replicas || 0)
                                                ? 'bg-green-500/20 text-green-300'
                                                : 'bg-yellow-500/20 text-yellow-300'
                                        }`}>
                                            {(deployment.ready_replicas || 0) === (deployment.replicas || 0) ? 'Ready' : 'Scaling'}
                                        </div>
                                        <span className="text-slate-400 text-sm">
                                            Available: {deployment.available_replicas || 0}
                                        </span>
                                    </div>
                                    <button
                                        onClick={() => handleScaleDeployment(deployment.name, deployment.replicas)}
                                        disabled={connectionStatus !== 'connected'}
                                        className="px-4 py-2 bg-gradient-to-r from-green-600 to-green-700 hover:from-green-500 hover:to-green-600 text-white rounded-xl transition-all duration-200 hover:scale-105 disabled:opacity-50 flex items-center"
                                    >
                                        <Zap className="mr-2" size={16} />
                                        Scale
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
};

// Resources Panel
const ResourcesPanel = ({ realTimeData, connectionStatus }) => {
    const [resources, setResources] = useState({ pods: [], services: [] });
    const [loading, setLoading] = useState(true);
    const [selectedResourceType, setSelectedResourceType] = useState('pods');
    const [selectedNamespace, setSelectedNamespace] = useState('default');

    useEffect(() => {
        loadResources();
    }, [selectedResourceType, selectedNamespace]);

    const loadResources = async () => {
        try {
            setLoading(true);
            let data = [];
            
            if (selectedResourceType === 'pods') {
                data = await EnhancedAPIClient.getPods(selectedNamespace);
            } else if (selectedResourceType === 'services') {
                data = await EnhancedAPIClient.getServices(selectedNamespace);
            }
            
            setResources(prev => ({ ...prev, [selectedResourceType]: data || [] }));
        } catch (error) {
            console.error('Failed to load resources:', error);
            setResources(prev => ({ ...prev, [selectedResourceType]: [] }));
        } finally {
            setLoading(false);
        }
    };

    const getStatusColor = (status) => {
        switch (status?.toLowerCase()) {
            case 'running': return 'bg-green-500/20 text-green-300';
            case 'pending': return 'bg-yellow-500/20 text-yellow-300';
            case 'failed': return 'bg-red-500/20 text-red-300';
            default: return 'bg-gray-500/20 text-gray-300';
        }
    };

    return (
        <div className="flex-1 p-8 space-y-8 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 overflow-y-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center mb-2">
                        <div className="bg-gradient-to-r from-orange-400 to-red-400 p-3 rounded-2xl mr-4">
                            <Layers size={28} className="text-white" />
                        </div>
                        Kubernetes Resources
                    </h1>
                    <p className="text-slate-400">Monitor your cluster resources</p>
                </div>
                <div className="flex items-center space-x-4">
                    <select 
                        value={selectedResourceType}
                        onChange={(e) => setSelectedResourceType(e.target.value)}
                        className="px-4 py-2 bg-slate-800 text-white rounded-xl border border-slate-700 focus:outline-none focus:border-blue-500"
                    >
                        <option value="pods">Pods</option>
                        <option value="services">Services</option>
                    </select>
                    <select 
                        value={selectedNamespace}
                        onChange={(e) => setSelectedNamespace(e.target.value)}
                        className="px-4 py-2 bg-slate-800 text-white rounded-xl border border-slate-700 focus:outline-none focus:border-blue-500"
                    >
                        <option value="default">default</option>
                        <option value="kube-system">kube-system</option>
                        <option value="all">all namespaces</option>
                    </select>
                    <button 
                        onClick={loadResources}
                        className="px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white rounded-xl transition-all duration-200 hover:scale-105 flex items-center"
                    >
                        <RefreshCw className={`mr-2 ${loading ? 'animate-spin' : ''}`} size={16} />
                        Refresh
                    </button>
                </div>
            </div>

            {loading ? (
                <div className="flex items-center justify-center py-12">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-400 border-t-transparent"></div>
                </div>
            ) : (
                <div className="grid gap-4">
                    {resources[selectedResourceType]?.length === 0 ? (
                        <div className="text-center py-12">
                            <Layers className="mx-auto mb-4 text-slate-400" size={48} />
                            <p className="text-slate-400 text-lg">No {selectedResourceType} found in {selectedNamespace}</p>
                        </div>
                    ) : (
                        resources[selectedResourceType]?.map((resource, index) => (
                            <div key={index} className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-xl p-4 border border-slate-700/50">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <h3 className="text-lg font-semibold text-white">{resource.name}</h3>
                                        <p className="text-slate-400 text-sm">Namespace: {resource.namespace}</p>
                                        {resource.node && (
                                            <p className="text-slate-400 text-sm">Node: {resource.node}</p>
                                        )}
                                    </div>
                                    <div className="text-right">
                                        <div className={`px-3 py-1 rounded-full text-sm font-semibold ${getStatusColor(resource.phase || resource.status)}`}>
                                            {resource.phase || resource.status || 'Unknown'}
                                        </div>
                                        {resource.ready && (
                                            <p className="text-slate-400 text-sm mt-1">Ready: {resource.ready}</p>
                                        )}
                                        {resource.restarts !== undefined && (
                                            <p className="text-slate-400 text-sm mt-1">Restarts: {resource.restarts}</p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
};

// FinOps Panel with INR formatting
const FinOpsPanel = ({ realTimeData, connectionStatus }) => {
    const finOpsData = realTimeData?.finOpsData || {};
    const costData = finOpsData?.cost_data || finOpsData || {};

    return (
        <div className="flex-1 p-8 space-y-8 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 overflow-y-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center mb-2">
                        <div className="bg-gradient-to-r from-yellow-400 to-orange-400 p-3 rounded-2xl mr-4">
                            <TrendingUp size={28} className="text-white" />
                        </div>
                        Azure FinOps Analysis
                    </h1>
                    <p className="text-slate-400">Cost optimization insights powered by AI (All amounts in INR)</p>
                </div>
            </div>

            {/* Cost Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 rounded-2xl p-6 border border-blue-500/20">
                    <div className="flex items-center mb-4">
                        <DollarSign className="mr-3 text-blue-400" size={24} />
                        <h3 className="font-semibold text-white">Total Monthly Cost</h3>
                    </div>
                    <p className="text-3xl font-bold text-white">
                        {formatINR(costData?.total_monthly_cost || 0)}
                    </p>
                    <p className="text-slate-400 text-sm mt-2">
                        Current Azure spending • {new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                    </p>
                </div>

                <div className="bg-gradient-to-br from-green-500/10 to-emerald-500/10 rounded-2xl p-6 border border-green-500/20">
                    <div className="flex items-center mb-4">
                        <TrendingUp className="mr-3 text-green-400" size={24} />
                        <h3 className="font-semibold text-white">Potential Savings</h3>
                    </div>
                    <p className="text-3xl font-bold text-green-400">
                        {formatINR(costData?.total_potential_savings || 0)}
                    </p>
                    <p className="text-slate-400 text-sm mt-2">AI-identified opportunities</p>
                </div>

                <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 rounded-2xl p-6 border border-purple-500/20">
                    <div className="flex items-center mb-4">
                        <Database className="mr-3 text-purple-400" size={24} />
                        <h3 className="font-semibold text-white">Resources</h3>
                    </div>
                    <p className="text-3xl font-bold text-white">
                        {costData?.resource_count || 0}
                    </p>
                    <p className="text-slate-400 text-sm mt-2">Monitored resources</p>
                </div>

                <div className="bg-gradient-to-br from-orange-500/10 to-red-500/10 rounded-2xl p-6 border border-orange-500/20">
                    <div className="flex items-center mb-4">
                        <Zap className="mr-3 text-orange-400" size={24} />
                        <h3 className="font-semibold text-white">Efficiency Score</h3>
                    </div>
                    <p className="text-3xl font-bold text-yellow-400">
                        {costData?.total_monthly_cost > 0 
                            ? Math.round((1 - (costData.total_potential_savings / costData.total_monthly_cost)) * 100)
                            : 0}%
                    </p>
                    <p className="text-slate-400 text-sm mt-2">Cost efficiency</p>
                </div>
            </div>

            {/* AI Analysis */}
            {(finOpsData?.ai_analysis || costData?.ai_analysis) && (
                <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-2xl p-8 border border-slate-700/50">
                    <h3 className="text-xl font-semibold text-white flex items-center mb-6">
                        <div className="bg-gradient-to-r from-purple-400 to-pink-400 p-2 rounded-xl mr-3">
                            <Sparkles size={20} className="text-white" />
                        </div>
                        AI Cost Analysis & Recommendations
                    </h3>
                    <div className="bg-slate-900/50 p-6 rounded-xl border border-slate-700/30">
                        <pre className="text-slate-200 whitespace-pre-wrap font-mono text-sm leading-relaxed">
                            {finOpsData?.ai_analysis || costData?.ai_analysis}
                        </pre>
                    </div>
                </div>
            )}

            {/* Cost Breakdown */}
            <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-2xl p-8 border border-slate-700/50">
                <div className="flex items-center justify-between mb-6">
                    <h3 className="text-xl font-semibold text-white flex items-center">
                        <BarChart3 className="mr-3 text-blue-400" size={20} />
                        Cost Breakdown by Service Type (INR)
                    </h3>
                    <span className="text-sm text-slate-400">
                        {new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                    </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {(() => {
                        const costByType = costData?.cost_by_type || costData?.cost_by_service || {};
                        const totalCost = costData?.total_monthly_cost || 0;
                        
                        if (Object.keys(costByType).length === 0) {
                            return (
                                <div className="col-span-full text-center py-12">
                                    <div className="bg-slate-600/30 p-8 rounded-xl">
                                        <Cloud className="mx-auto mb-4 text-slate-400" size={48} />
                                        <p className="text-slate-400 text-lg mb-2">No cost breakdown data available</p>
                                        <p className="text-slate-500">Connect to Azure Cost Management API to see detailed service costs</p>
                                        <div className="mt-4 p-3 bg-blue-500/20 border border-blue-500/30 rounded-lg">
                                            <p className="text-blue-300 text-sm">
                                                Tip: Configure AZURE_SUBSCRIPTION_ID in your .env file
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            );
                        }
                        
                        return Object.entries(costByType).map(([type, cost]) => {
                            const costValue = typeof cost === 'object' ? (cost?.cost || 0) : (cost || 0);
                            const percentage = totalCost > 0 ? (costValue / totalCost) * 100 : 0;
                            
                            return (
                                <div key={type} className="bg-slate-700/30 p-4 rounded-xl hover:bg-slate-700/50 transition-all duration-300 group">
                                    <div className="flex justify-between items-center mb-3">
                                        <span className="text-slate-300 font-medium group-hover:text-white transition-colors">{type}</span>
                                        <span className="text-white font-bold">{formatINR(costValue)}</span>
                                    </div>
                                    <div className="w-full bg-slate-600/50 rounded-full h-2 mb-2">
                                        <div 
                                            className="bg-gradient-to-r from-blue-500 to-cyan-500 h-2 rounded-full transition-all duration-1000 group-hover:from-blue-400 group-hover:to-cyan-400" 
                                            style={{ width: `${Math.min(percentage, 100)}%` }}
                                        ></div>
                                    </div>
                                    <div className="flex justify-between items-center text-xs">
                                        <span className="text-slate-400">
                                            {percentage.toFixed(1)}% of total
                                        </span>
                                        <span className="text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity">
                                            {formatINR(costValue, false)}
                                        </span>
                                    </div>
                                </div>
                            );
                        });
                    })()}
                </div>
                
                <div className="mt-6 pt-4 border-t border-slate-600/30">
                    <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-400">
                            Data Source: {costData?.data_source || 'Unknown'} | Last Updated: {costData?.last_updated 
                                ? new Date(costData.last_updated).toLocaleDateString('en-IN')
                                : 'Never'
                            }
                        </span>
                        <span className="text-slate-300">
                            All amounts in Indian Rupees (INR)
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
};

// Manifests Panel
const ManifestsPanel = ({ onApplyManifest, connectionStatus }) => {
    const [manifestContent, setManifestContent] = useState('');
    const [selectedNamespace, setSelectedNamespace] = useState('default');
    const [dryRun, setDryRun] = useState(false);

    const exampleManifest = `apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  labels:
    app: nginx
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.21
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "64Mi"
            cpu: "250m"
          limits:
            memory: "128Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  selector:
    app: nginx
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
  type: LoadBalancer`;

    const handleApply = () => {
        if (!manifestContent.trim()) {
            alert('Please enter a manifest');
            return;
        }
        onApplyManifest(manifestContent);
    };

    return (
        <div className="flex-1 p-8 space-y-8 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 overflow-y-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center mb-2">
                        <div className="bg-gradient-to-r from-indigo-400 to-purple-400 p-3 rounded-2xl mr-4">
                            <FileText size={28} className="text-white" />
                        </div>
                        Apply YAML Manifests
                    </h1>
                    <p className="text-slate-400">Deploy resources to your Kubernetes cluster</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Manifest Editor */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-2xl p-6 border border-slate-700/50">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold text-white">YAML Manifest</h3>
                            <button
                                onClick={() => setManifestContent(exampleManifest)}
                                className="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors"
                            >
                                Load Example
                            </button>
                        </div>
                        <textarea
                            value={manifestContent}
                            onChange={(e) => setManifestContent(e.target.value)}
                            className="w-full h-96 bg-slate-900/50 text-white font-mono text-sm p-4 rounded-xl border border-slate-700 focus:outline-none focus:border-blue-500 resize-none"
                            placeholder="Paste your YAML manifest here..."
                        />
                    </div>

                    {/* Apply Controls */}
                    <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-2xl p-6 border border-slate-700/50">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-2">Namespace</label>
                                    <select 
                                        value={selectedNamespace}
                                        onChange={(e) => setSelectedNamespace(e.target.value)}
                                        className="px-3 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 focus:outline-none focus:border-blue-500"
                                    >
                                        <option value="default">default</option>
                                        <option value="kube-system">kube-system</option>
                                        <option value="custom">custom namespace</option>
                                    </select>
                                </div>
                                <div className="flex items-center">
                                    <input
                                        type="checkbox"
                                        id="dryRun"
                                        checked={dryRun}
                                        onChange={(e) => setDryRun(e.target.checked)}
                                        className="mr-2"
                                    />
                                    <label htmlFor="dryRun" className="text-sm text-slate-300">Dry run (validate only)</label>
                                </div>
                            </div>
                            <button
                                onClick={handleApply}
                                disabled={connectionStatus !== 'connected' || !manifestContent.trim()}
                                className="px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white rounded-xl transition-all duration-200 hover:scale-105 disabled:opacity-50 flex items-center"
                            >
                                <Play className="mr-2" size={16} />
                                {dryRun ? 'Validate' : 'Apply'} Manifest
                            </button>
                        </div>
                    </div>
                </div>

                {/* Help Panel */}
                <div className="space-y-6">
                    <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-2xl p-6 border border-slate-700/50">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
                            <Info className="mr-2 text-blue-400" size={20} />
                            Quick Tips
                        </h3>
                        <div className="space-y-3 text-sm text-slate-300">
                            <div className="flex items-start">
                                <CheckCircle className="mr-2 text-green-400 mt-0.5 flex-shrink-0" size={16} />
                                <span>Use dry run to validate before applying</span>
                            </div>
                            <div className="flex items-start">
                                <CheckCircle className="mr-2 text-green-400 mt-0.5 flex-shrink-0" size={16} />
                                <span>Multiple resources can be separated by ---</span>
                            </div>
                            <div className="flex items-start">
                                <CheckCircle className="mr-2 text-green-400 mt-0.5 flex-shrink-0" size={16} />
                                <span>Set resource requests and limits</span>
                            </div>
                            <div className="flex items-start">
                                <CheckCircle className="mr-2 text-green-400 mt-0.5 flex-shrink-0" size={16} />
                                <span>Use labels for better organization</span>
                            </div>
                        </div>
                    </div>

                    <div className="bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-2xl p-6 border border-slate-700/50">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
                            <Shield className="mr-2 text-green-400" size={20} />
                            Supported Resources
                        </h3>
                        <div className="space-y-2 text-sm text-slate-300">
                            <div className="flex items-center justify-between">
                                <span>Deployments</span>
                                <CheckCircle className="text-green-400" size={16} />
                            </div>
                            <div className="flex items-center justify-between">
                                <span>Services</span>
                                <CheckCircle className="text-green-400" size={16} />
                            </div>
                            <div className="flex items-center justify-between">
                                <span>ConfigMaps</span>
                                <AlertCircle className="text-yellow-400" size={16} />
                            </div>
                            <div className="flex items-center justify-between">
                                <span>Secrets</span>
                                <AlertCircle className="text-yellow-400" size={16} />
                            </div>
                            <div className="flex items-center justify-between">
                                <span>Ingress</span>
                                <AlertCircle className="text-yellow-400" size={16} />
                            </div>
                        </div>
                        <p className="text-xs text-slate-500 mt-3">
                            ✅ Full support | ⚠️ Limited support
                        </p>
                    </div>

                    {connectionStatus !== 'connected' && (
                        <div className="bg-red-500/20 border border-red-500/30 rounded-xl p-4">
                            <div className="flex items-center mb-2">
                                <AlertTriangle className="mr-2 text-red-400" size={20} />
                                <p className="font-semibold text-red-300">No Connection</p>
                            </div>
                            <p className="text-red-200 text-sm">
                                MCP server connection required to apply manifests
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

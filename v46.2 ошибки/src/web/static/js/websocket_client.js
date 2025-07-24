/**
 * WebSocket Client for Trading System
 * Handles real-time communication with the server
 */

class TradingWebSocketClient {
    constructor(config = {}) {
        this.config = {
            url: config.url || '/',
            reconnectDelay: config.reconnectDelay || 1000,
            maxReconnectDelay: config.maxReconnectDelay || 30000,
            reconnectAttempts: config.reconnectAttempts || 5,
            pingInterval: config.pingInterval || 30000,
            debug: config.debug || false,
            ...config
        };
        
        this.socket = null;
        this.reconnectCount = 0;
        this.reconnectTimer = null;
        this.pingTimer = null;
        this.eventHandlers = new Map();
        this.connectionStatus = 'disconnected';
        this.isIntentionalDisconnect = false;
        
        // Default event handlers
        this.setupDefaultHandlers();
    }
    
    /**
     * Initialize WebSocket connection
     */
    connect() {
        if (this.socket && (this.socket.connected || this.socket.connecting)) {
            this.log('Already connected or connecting');
            return;
        }
        
        this.log('Connecting to WebSocket...');
        this.isIntentionalDisconnect = false;
        
        // Create socket connection
        this.socket = io(this.config.url, {
            transports: ['websocket', 'polling'],
            reconnection: false, // We'll handle reconnection manually
            timeout: 20000
        });
        
        // Setup socket event listeners
        this.setupSocketListeners();
    }
    
    /**
     * Setup default event handlers
     */
    setupDefaultHandlers() {
        // Connection status handler
        this.on('connection_status', (status) => {
            this.updateConnectionStatus(status);
        });
        
        // Error handler
        this.on('error', (error) => {
            console.error('WebSocket Error:', error);
            this.emit('notification', {
                type: 'error',
                message: `Ошибка подключения: ${error.message || 'Неизвестная ошибка'}`
            });
        });
    }
    
    /**
     * Setup socket event listeners
     */
    setupSocketListeners() {
        // Connection established
        this.socket.on('connect', () => {
            this.log('Connected to WebSocket');
            this.connectionStatus = 'connected';
            this.reconnectCount = 0;
            
            // Clear reconnect timer
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
            
            // Start ping timer
            this.startPingTimer();
            
            // Emit connection event
            this.emit('connected');
            this.emit('connection_status', 'connected');
            
            // Request initial data
            this.requestInitialData();
        });
        
        // Connection lost
        this.socket.on('disconnect', (reason) => {
            this.log(`Disconnected: ${reason}`);
            this.connectionStatus = 'disconnected';
            
            // Stop ping timer
            this.stopPingTimer();
            
            // Emit disconnection event
            this.emit('disconnected', reason);
            this.emit('connection_status', 'disconnected');
            
            // Attempt reconnection if not intentional
            if (!this.isIntentionalDisconnect && reason !== 'io client disconnect') {
                this.scheduleReconnect();
            }
        });
        
        // Connection error
        this.socket.on('connect_error', (error) => {
            this.log(`Connection error: ${error.message}`);
            this.emit('connection_error', error);
        });
        
        // Reconnection attempts
        this.socket.on('reconnect_attempt', (attemptNumber) => {
            this.log(`Reconnection attempt ${attemptNumber}`);
            this.emit('reconnecting', attemptNumber);
        });
        
        // Listen for all events and forward to handlers
        this.socket.onAny((eventName, ...args) => {
            this.log(`Received event: ${eventName}`, args);
            this.emit(eventName, ...args);
        });
    }
    
    /**
     * Request initial data after connection
     */
    requestInitialData() {
        // Request current signals matrix
        this.emit('request_signals_matrix');
        
        // Request active trades
        this.emit('request_active_trades');
        
        // Request portfolio status
        this.emit('request_portfolio_status');
    }
    
    /**
     * Start ping timer to keep connection alive
     */
    startPingTimer() {
        this.stopPingTimer();
        
        this.pingTimer = setInterval(() => {
            if (this.socket && this.socket.connected) {
                this.socket.emit('ping');
                this.log('Ping sent');
            }
        }, this.config.pingInterval);
    }
    
    /**
     * Stop ping timer
     */
    stopPingTimer() {
        if (this.pingTimer) {
            clearInterval(this.pingTimer);
            this.pingTimer = null;
        }
    }
    
    /**
     * Schedule reconnection attempt
     */
    scheduleReconnect() {
        if (this.reconnectCount >= this.config.reconnectAttempts) {
            this.log('Max reconnection attempts reached');
            this.emit('max_reconnect_attempts');
            return;
        }
        
        this.reconnectCount++;
        const delay = Math.min(
            this.config.reconnectDelay * Math.pow(2, this.reconnectCount - 1),
            this.config.maxReconnectDelay
        );
        
        this.log(`Scheduling reconnect in ${delay}ms (attempt ${this.reconnectCount})`);
        this.emit('connection_status', 'reconnecting');
        
        this.reconnectTimer = setTimeout(() => {
            this.connect();
        }, delay);
    }
    
    /**
     * Disconnect from WebSocket
     */
    disconnect() {
        this.log('Disconnecting...');
        this.isIntentionalDisconnect = true;
        
        // Clear timers
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        this.stopPingTimer();
        
        // Disconnect socket
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
        
        this.connectionStatus = 'disconnected';
        this.emit('connection_status', 'disconnected');
    }
    
    /**
     * Send event to server
     */
    send(eventName, data, callback) {
        if (!this.socket || !this.socket.connected) {
            this.log(`Cannot send ${eventName}: not connected`);
            if (callback) {
                callback({ error: 'Not connected' });
            }
            return;
        }
        
        this.log(`Sending ${eventName}`, data);
        
        if (callback) {
            this.socket.emit(eventName, data, callback);
        } else {
            this.socket.emit(eventName, data);
        }
    }
    
    /**
     * Register event handler
     */
    on(eventName, handler) {
        if (!this.eventHandlers.has(eventName)) {
            this.eventHandlers.set(eventName, new Set());
        }
        
        this.eventHandlers.get(eventName).add(handler);
        
        // Return unsubscribe function
        return () => this.off(eventName, handler);
    }
    
    /**
     * Unregister event handler
     */
    off(eventName, handler) {
        if (this.eventHandlers.has(eventName)) {
            this.eventHandlers.get(eventName).delete(handler);
        }
    }
    
    /**
     * Emit event to all registered handlers
     */
    emit(eventName, ...args) {
        if (this.eventHandlers.has(eventName)) {
            this.eventHandlers.get(eventName).forEach(handler => {
                try {
                    handler(...args);
                } catch (error) {
                    console.error(`Error in handler for ${eventName}:`, error);
                }
            });
        }
    }
    
    /**
     * Update connection status in UI
     */
    updateConnectionStatus(status) {
        const statusElements = document.querySelectorAll('.connection-status');
        statusElements.forEach(element => {
            switch (status) {
                case 'connected':
                    element.innerHTML = `
                        <span class="status-dot status-online"></span>
                        <span>Подключено</span>
                    `;
                    element.classList.remove('text-danger', 'text-warning');
                    element.classList.add('text-success');
                    break;
                    
                case 'disconnected':
                    element.innerHTML = `
                        <span class="status-dot status-offline"></span>
                        <span>Отключено</span>
                    `;
                    element.classList.remove('text-success', 'text-warning');
                    element.classList.add('text-danger');
                    break;
                    
                case 'reconnecting':
                    element.innerHTML = `
                        <span class="status-dot status-offline"></span>
                        <span>Переподключение...</span>
                    `;
                    element.classList.remove('text-success', 'text-danger');
                    element.classList.add('text-warning');
                    break;
            }
        });
    }
    
    /**
     * Check if connected
     */
    isConnected() {
        return this.socket && this.socket.connected;
    }
    
    /**
     * Get connection status
     */
    getStatus() {
        return this.connectionStatus;
    }
    
    /**
     * Log message if debug enabled
     */
    log(...args) {
        if (this.config.debug) {
            console.log('[WebSocket]', ...args);
        }
    }
}

/**
 * Singleton instance of WebSocket client
 */
let wsClientInstance = null;

/**
 * Get or create WebSocket client instance
 */
function getWebSocketClient(config = {}) {
    if (!wsClientInstance) {
        wsClientInstance = new TradingWebSocketClient(config);
    }
    return wsClientInstance;
}

/**
 * Initialize WebSocket client
 */
function initializeWebSocket(config = {}) {
    const client = getWebSocketClient(config);
    
    // Setup global event handlers
    client.on('notification', (notification) => {
        showNotification(notification.message, notification.type);
    });
    
    client.on('signal_matrix_update', (data) => {
        // Update signals matrix if on that page
        if (window.matrixApp) {
            window.matrixApp.handleSignalUpdate(data);
        }
    });
    
    client.on('trade_update', (data) => {
        // Update trades if on that page
        if (window.tradesManager) {
            window.tradesManager.handleTradeUpdate(data);
        }
    });
    
    client.on('analytics_update', (data) => {
        // Update analytics if on that page
        if (window.analyticsApp) {
            window.analyticsApp.handleAnalyticsUpdate(data);
        }
    });
    
    // Connect
    client.connect();
    
    return client;
}

/**
 * Show notification helper
 */
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type} fade-in`;
    notification.innerHTML = `
        <i class="fas fa-${getNotificationIcon(type)}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

/**
 * Get notification icon based on type
 */
function getNotificationIcon(type) {
    const icons = {
        success: 'check-circle',
        error: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle'
    };
    return icons[type] || icons.info;
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        TradingWebSocketClient,
        getWebSocketClient,
        initializeWebSocket
    };
}
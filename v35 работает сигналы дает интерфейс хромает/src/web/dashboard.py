"""
Современный дашборд для торгового бота
Файл: src/web/dashboard.py
"""

def get_dashboard_html():
    """Возвращает HTML код современного дашборда"""
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Trading Bot - Professional Dashboard</title>
    
    <!-- Bootstrap 5 -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- Custom CSS -->
    <style>
        :root {
            --primary-color: #2563eb;
            --success-color: #10b981;
            --danger-color: #ef4444;
            --warning-color: #f59e0b;
            --dark-bg: #1a1a1a;
            --card-bg: #2d2d2d;
            --text-primary: #ffffff;
            --text-secondary: #a0a0a0;
        }

        body {
            background-color: var(--dark-bg);
            color: var(--text-primary);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        .navbar {
            background-color: var(--card-bg) !important;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }

        .card {
            background-color: var(--card-bg);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.375rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
        }

        .status-badge.active {
            background-color: rgba(16, 185, 129, 0.2);
            color: #10b981;
        }

        .status-badge.inactive {
            background-color: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }

        .metric-card {
            position: relative;
            overflow: hidden;
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 100px;
            height: 100px;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            transform: translate(30px, -30px);
        }

        .chart-container {
            position: relative;
            height: 300px;
        }

        .position-row {
            transition: all 0.3s ease;
        }

        .position-row:hover {
            background-color: rgba(255,255,255,0.05);
        }

        .strategy-card {
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .strategy-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 12px rgba(0,0,0,0.4);
        }

        .loading-spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 1s ease-in-out infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .ticker-item {
            padding: 0.5rem 1rem;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            margin: 0.25rem;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }

        .price-up { color: var(--success-color); }
        .price-down { color: var(--danger-color); }

        .log-entry {
            padding: 0.5rem;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 0.875rem;
        }

        .log-entry.error { color: var(--danger-color); }
        .log-entry.warning { color: var(--warning-color); }
        .log-entry.success { color: var(--success-color); }

        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            min-width: 300px;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            z-index: 9999;
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <i class="fas fa-robot"></i> Crypto Trading Bot v3.0
            </a>
            <div class="ms-auto d-flex align-items-center gap-3">
                <span class="text-secondary">
                    <i class="fas fa-server"></i> Server: <span id="server-status" class="text-success">Connected</span>
                </span>
                <span class="text-secondary">
                    <i class="fas fa-clock"></i> <span id="current-time">--:--:--</span>
                </span>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <div class="container-fluid py-4">
        <!-- Top Stats Row -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h6 class="text-secondary mb-1">Bot Status</h6>
                                <h3 class="mb-2" id="bot-status">
                                    <span class="status-badge inactive">
                                        <i class="fas fa-circle me-2" style="font-size: 8px;"></i>
                                        Stopped
                                    </span>
                                </h3>
                                <small class="text-secondary">Uptime: <span id="uptime">0h 0m</span></small>
                            </div>
                            <div class="text-end">
                                <button class="btn btn-success btn-sm" id="start-bot-btn">
                                    <i class="fas fa-play"></i> Start
                                </button>
                                <button class="btn btn-danger btn-sm d-none" id="stop-bot-btn">
                                    <i class="fas fa-stop"></i> Stop
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <h6 class="text-secondary mb-1">Total Balance</h6>
                        <h3 class="mb-2">$<span id="total-balance">0.00</span></h3>
                        <small>
                            <span id="balance-change" class="price-up">
                                <i class="fas fa-arrow-up"></i> 0.00%
                            </span>
                            Today
                        </small>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <h6 class="text-secondary mb-1">Active Positions</h6>
                        <h3 class="mb-2" id="active-positions">0</h3>
                        <small>
                            P&L: <span id="total-pnl" class="price-up">$0.00</span>
                        </small>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body">
                        <h6 class="text-secondary mb-1">Today's Performance</h6>
                        <h3 class="mb-2">
                            <span id="win-rate">0</span>%
                        </h3>
                        <small>
                            <span id="trades-today">0</span> trades
                        </small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Live Tickers -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="mb-3">
                            <i class="fas fa-chart-line"></i> Live Market Data
                        </h5>
                        <div id="tickers-container" class="d-flex flex-wrap">
                            <!-- Tickers will be inserted here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Main Content Area -->
        <div class="row">
            <!-- Left Column -->
            <div class="col-lg-8">
                <!-- Chart -->
                <div class="card mb-4">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5><i class="fas fa-chart-area"></i> Price Chart</h5>
                            <div>
                                <select id="chart-symbol" class="form-select form-select-sm d-inline-block w-auto">
                                    <option value="BTCUSDT">BTC/USDT</option>
                                    <option value="ETHUSDT">ETH/USDT</option>
                                    <option value="BNBUSDT">BNB/USDT</option>
                                </select>
                                <select id="chart-interval" class="form-select form-select-sm d-inline-block w-auto ms-2">
                                    <option value="1m">1m</option>
                                    <option value="5m">5m</option>
                                    <option value="15m">15m</option>
                                    <option value="1h">1h</option>
                                </select>
                            </div>
                        </div>
                        <div class="chart-container">
                            <canvas id="price-chart"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Active Positions -->
                <div class="card mb-4">
                    <div class="card-body">
                        <h5 class="mb-3">
                            <i class="fas fa-list"></i> Active Positions
                        </h5>
                        <div class="table-responsive">
                            <table class="table table-dark table-hover">
                                <thead>
                                    <tr>
                                        <th>Symbol</th>
                                        <th>Side</th>
                                        <th>Size</th>
                                        <th>Entry</th>
                                        <th>Current</th>
                                        <th>P&L</th>
                                        <th>Strategy</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="positions-table">
                                    <tr>
                                        <td colspan="8" class="text-center text-secondary">No active positions</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Recent Trades -->
                <div class="card">
                    <div class="card-body">
                        <h5 class="mb-3">
                            <i class="fas fa-history"></i> Recent Trades
                        </h5>
                        <div class="table-responsive">
                            <table class="table table-dark table-hover">
                                <thead>
                                    <tr>
                                        <th>Time</th>
                                        <th>Symbol</th>
                                        <th>Side</th>
                                        <th>Price</th>
                                        <th>Size</th>
                                        <th>P&L</th>
                                        <th>Strategy</th>
                                    </tr>
                                </thead>
                                <tbody id="trades-table">
                                    <tr>
                                        <td colspan="7" class="text-center text-secondary">No recent trades</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Right Column -->
            <div class="col-lg-4">
                <!-- Strategies Status -->
                <div class="card mb-4">
                    <div class="card-body">
                        <h5 class="mb-3">
                            <i class="fas fa-brain"></i> Active Strategies
                        </h5>
                        <div id="strategies-container">
                            <!-- Strategy cards will be inserted here -->
                        </div>
                    </div>
                </div>

                <!-- System Logs -->
                <div class="card">
                    <div class="card-body">
                        <h5 class="mb-3">
                            <i class="fas fa-terminal"></i> System Logs
                        </h5>
                        <div id="logs-container" style="height: 400px; overflow-y: auto;">
                            <!-- Logs will be inserted here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    
    <script>
        // Global state
        const state = {
            isConnected: false,
            socket: null,
            charts: {},
            updateIntervals: {},
            currentData: {
                balance: 0,
                positions: [],
                trades: [],
                strategies: {},
                tickers: {}
            }
        };

        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            initializeWebSocket();
            initializeCharts();
            setupEventListeners();
            startPeriodicUpdates();
            
            // Update time
            setInterval(updateTime, 1000);
        });

        // WebSocket connection
        function initializeWebSocket() {
            // Connect to Flask-SocketIO
            state.socket = io('http://localhost:5000');
            
            state.socket.on('connect', () => {
                console.log('WebSocket connected');
                state.isConnected = true;
                updateConnectionStatus(true);
                showNotification('Connected to server', 'success');
            });

            state.socket.on('disconnect', () => {
                console.log('WebSocket disconnected');
                state.isConnected = false;
                updateConnectionStatus(false);
                showNotification('Disconnected from server', 'error');
            });

            // Listen for updates
            state.socket.on('bot_status', handleBotStatus);
            state.socket.on('balance_update', handleBalanceUpdate);
            state.socket.on('position_update', handlePositionUpdate);
            state.socket.on('trade_update', handleTradeUpdate);
            state.socket.on('strategy_update', handleStrategyUpdate);
            state.socket.on('ticker_update', handleTickerUpdate);
            state.socket.on('log_message', handleLogMessage);
        }

        // Initialize charts
        function initializeCharts() {
            const ctx = document.getElementById('price-chart').getContext('2d');
            state.charts.price = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Price',
                        data: [],
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: { 
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { color: '#a0a0a0' }
                        },
                        y: { 
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { color: '#a0a0a0' }
                        }
                    }
                }
            });
        }

        // Event listeners
        function setupEventListeners() {
            document.getElementById('start-bot-btn').addEventListener('click', startBot);
            document.getElementById('stop-bot-btn').addEventListener('click', stopBot);
            document.getElementById('chart-symbol').addEventListener('change', updateChart);
            document.getElementById('chart-interval').addEventListener('change', updateChart);
        }

        // Bot control
        async function startBot() {
            try {
                const response = await fetch('/api/bot/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                
                if (data.success) {
                    showNotification('Bot started successfully', 'success');
                } else {
                    showNotification('Failed to start bot: ' + data.message, 'error');
                }
            } catch (error) {
                showNotification('Error starting bot', 'error');
            }
        }

        async function stopBot() {
            try {
                const response = await fetch('/api/bot/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                
                if (data.success) {
                    showNotification('Bot stopped successfully', 'success');
                } else {
                    showNotification('Failed to stop bot: ' + data.message, 'error');
                }
            } catch (error) {
                showNotification('Error stopping bot', 'error');
            }
        }

        // Update handlers
        function handleBotStatus(data) {
            const statusEl = document.getElementById('bot-status');
            const startBtn = document.getElementById('start-bot-btn');
            const stopBtn = document.getElementById('stop-bot-btn');
            
            if (data.is_running) {
                statusEl.innerHTML = `
                    <span class="status-badge active">
                        <i class="fas fa-circle me-2" style="font-size: 8px;"></i>
                        Running
                    </span>
                `;
                startBtn.classList.add('d-none');
                stopBtn.classList.remove('d-none');
            } else {
                statusEl.innerHTML = `
                    <span class="status-badge inactive">
                        <i class="fas fa-circle me-2" style="font-size: 8px;"></i>
                        Stopped
                    </span>
                `;
                startBtn.classList.remove('d-none');
                stopBtn.classList.add('d-none');
            }
            
            // Update uptime
            if (data.uptime) {
                document.getElementById('uptime').textContent = data.uptime;
            }
        }

        function handleBalanceUpdate(data) {
            state.currentData.balance = data.total_usdt;
            document.getElementById('total-balance').textContent = data.total_usdt.toFixed(2);
            
            // Update balance change
            const changeEl = document.getElementById('balance-change');
            const change = data.change_24h || 0;
            changeEl.className = change >= 0 ? 'price-up' : 'price-down';
            changeEl.innerHTML = `
                <i class="fas fa-arrow-${change >= 0 ? 'up' : 'down'}"></i> 
                ${Math.abs(change).toFixed(2)}%
            `;
        }

        function handlePositionUpdate(data) {
            state.currentData.positions = data.positions || [];
            updatePositionsTable();
            
            // Update stats
            document.getElementById('active-positions').textContent = data.positions.length;
            
            const totalPnl = data.positions.reduce((sum, pos) => sum + (pos.pnl || 0), 0);
            const pnlEl = document.getElementById('total-pnl');
            pnlEl.textContent = `$${totalPnl.toFixed(2)}`;
            pnlEl.className = totalPnl >= 0 ? 'price-up' : 'price-down';
        }

        function handleTradeUpdate(data) {
            state.currentData.trades = data.trades || [];
            updateTradesTable();
            
            // Update today's stats
            const todayTrades = data.trades.filter(t => 
                new Date(t.timestamp).toDateString() === new Date().toDateString()
            );
            
            document.getElementById('trades-today').textContent = todayTrades.length;
            
            const winningTrades = todayTrades.filter(t => t.pnl > 0).length;
            const winRate = todayTrades.length > 0 ? (winningTrades / todayTrades.length * 100) : 0;
            document.getElementById('win-rate').textContent = winRate.toFixed(0);
        }

        function handleStrategyUpdate(data) {
            state.currentData.strategies = data.strategies || {};
            updateStrategiesDisplay();
        }

        function handleTickerUpdate(data) {
            state.currentData.tickers = data.tickers || {};
            updateTickersDisplay();
            
            // Update chart if needed
            const selectedSymbol = document.getElementById('chart-symbol').value;
            if (data.tickers[selectedSymbol]) {
                updateChartData(selectedSymbol, data.tickers[selectedSymbol]);
            }
        }

        function handleLogMessage(data) {
            addLogEntry(data);
        }

        // UI Update functions
        function updatePositionsTable() {
            const tbody = document.getElementById('positions-table');
            
            if (state.currentData.positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center text-secondary">No active positions</td></tr>';
                return;
            }
            
            tbody.innerHTML = state.currentData.positions.map(pos => `
                <tr class="position-row">
                    <td>${pos.symbol}</td>
                    <td>
                        <span class="badge bg-${pos.side === 'BUY' ? 'success' : 'danger'}">
                            ${pos.side}
                        </span>
                    </td>
                    <td>${pos.size}</td>
                    <td>$${pos.entry_price.toFixed(2)}</td>
                    <td>$${pos.current_price.toFixed(2)}</td>
                    <td class="${pos.pnl >= 0 ? 'price-up' : 'price-down'}">
                        $${pos.pnl.toFixed(2)} (${pos.pnl_percent.toFixed(2)}%)
                    </td>
                    <td>${pos.strategy}</td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="closePosition('${pos.id}')">
                            Close
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        function updateTradesTable() {
            const tbody = document.getElementById('trades-table');
            const recentTrades = state.currentData.trades.slice(0, 10);
            
            if (recentTrades.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-secondary">No recent trades</td></tr>';
                return;
            }
            
            tbody.innerHTML = recentTrades.map(trade => `
                <tr>
                    <td>${new Date(trade.timestamp).toLocaleTimeString()}</td>
                    <td>${trade.symbol}</td>
                    <td>
                        <span class="badge bg-${trade.side === 'BUY' ? 'success' : 'danger'}">
                            ${trade.side}
                        </span>
                    </td>
                    <td>$${trade.price.toFixed(2)}</td>
                    <td>${trade.size}</td>
                    <td class="${trade.pnl >= 0 ? 'price-up' : 'price-down'}">
                        $${trade.pnl.toFixed(2)}
                    </td>
                    <td>${trade.strategy}</td>
                </tr>
            `).join('');
        }

        function updateStrategiesDisplay() {
            const container = document.getElementById('strategies-container');
            const strategies = Object.entries(state.currentData.strategies);
            
            container.innerHTML = strategies.map(([name, data]) => `
                <div class="strategy-card card mb-2" style="background-color: rgba(255,255,255,0.05);">
                    <div class="card-body p-3">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="mb-1">${name}</h6>
                                <small class="text-secondary">
                                    Weight: ${data.weight}% | Signals: ${data.signals_count}
                                </small>
                            </div>
                            <div>
                                <span class="badge bg-${data.active ? 'success' : 'secondary'}">
                                    ${data.active ? 'Active' : 'Inactive'}
                                </span>
                            </div>
                        </div>
                        ${data.last_signal ? `
                            <div class="mt-2">
                                <small class="text-info">
                                    Last: ${data.last_signal.action} ${data.last_signal.symbol}
                                </small>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `).join('');
        }

        function updateTickersDisplay() {
            const container = document.getElementById('tickers-container');
            const tickers = Object.entries(state.currentData.tickers);
            
            container.innerHTML = tickers.map(([symbol, data]) => `
                <div class="ticker-item">
                    <strong>${symbol}</strong>
                    <span>$${data.price.toFixed(2)}</span>
                    <span class="${data.change_24h >= 0 ? 'price-up' : 'price-down'}">
                        ${data.change_24h >= 0 ? '+' : ''}${data.change_24h.toFixed(2)}%
                    </span>
                </div>
            `).join('');
        }

        function addLogEntry(log) {
            const container = document.getElementById('logs-container');
            const logClass = log.level === 'ERROR' ? 'error' : 
                           log.level === 'WARNING' ? 'warning' : 
                           log.level === 'SUCCESS' ? 'success' : '';
            
            const entry = document.createElement('div');
            entry.className = `log-entry ${logClass}`;
            entry.innerHTML = `
                <span class="text-secondary">${new Date(log.timestamp).toLocaleTimeString()}</span>
                [${log.level}] ${log.message}
            `;
            
            container.insertBefore(entry, container.firstChild);
            
            // Keep only last 100 logs
            while (container.children.length > 100) {
                container.removeChild(container.lastChild);
            }
        }

        // Helper functions
        function updateTime() {
            document.getElementById('current-time').textContent = 
                new Date().toLocaleTimeString();
        }

        function updateConnectionStatus(connected) {
            const statusEl = document.getElementById('server-status');
            statusEl.textContent = connected ? 'Connected' : 'Disconnected';
            statusEl.className = connected ? 'text-success' : 'text-danger';
        }

        function showNotification(message, type = 'info') {
            const notification = document.createElement('div');
            notification.className = `notification alert alert-${type}`;
            notification.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span>${message}</span>
                    <button class="btn-close btn-close-white ms-3" onclick="this.parentElement.parentElement.remove()"></button>
                </div>
            `;
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.remove();
            }, 5000);
        }

        async function closePosition(positionId) {
            if (!confirm('Are you sure you want to close this position?')) return;
            
            try {
                const response = await fetch(`/api/positions/${positionId}/close`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                
                if (data.success) {
                    showNotification('Position closed successfully', 'success');
                } else {
                    showNotification('Failed to close position', 'error');
                }
            } catch (error) {
                showNotification('Error closing position', 'error');
            }
        }

        function updateChart() {
            const symbol = document.getElementById('chart-symbol').value;
            const interval = document.getElementById('chart-interval').value;
            
            // Fetch new data
            fetchChartData(symbol, interval);
        }

        async function fetchChartData(symbol, interval) {
            try {
                const response = await fetch(`/api/charts/candles/${symbol}?interval=${interval}`);
                const data = await response.json();
                
                if (data.success) {
                    updateChartWithData(data.candles);
                }
            } catch (error) {
                console.error('Error fetching chart data:', error);
            }
        }

        function updateChartWithData(candles) {
            const chart = state.charts.price;
            chart.data.labels = candles.map(c => new Date(c.timestamp).toLocaleTimeString());
            chart.data.datasets[0].data = candles.map(c => c.close);
            chart.update();
        }

        function updateChartData(symbol, ticker) {
            const chart = state.charts.price;
            const now = new Date().toLocaleTimeString();
            
            // Add new point
            chart.data.labels.push(now);
            chart.data.datasets[0].data.push(ticker.price);
            
            // Keep only last 50 points
            if (chart.data.labels.length > 50) {
                chart.data.labels.shift();
                chart.data.datasets[0].data.shift();
            }
            
            chart.update('none'); // Update without animation
        }

        // Start periodic updates
        function startPeriodicUpdates() {
            // Update balance every 30 seconds
            setInterval(async () => {
                try {
                    const response = await fetch('/api/balance');
                    const data = await response.json();
                    if (data.success) {
                        handleBalanceUpdate(data);
                    }
                } catch (error) {
                    console.error('Error fetching balance:', error);
                }
            }, 30000);

            // Update positions every 10 seconds
            setInterval(async () => {
                try {
                    const response = await fetch('/api/bot/positions');
                    const data = await response.json();
                    if (data.success) {
                        handlePositionUpdate(data);
                    }
                } catch (error) {
                    console.error('Error fetching positions:', error);
                }
            }, 10000);

            // Initial chart data
            updateChart();
        }
    </script>
</body>
</html>"""
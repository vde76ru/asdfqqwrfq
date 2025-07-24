/**
 * Trades Management Module
 * Handles all functionality for trades management
 */

class TradesManager {
    constructor() {
        this.activeTrades = [];
        this.historyTrades = [];
        this.virtualTrades = [];
        this.portfolio = {
            balance: 10000,
            equity: 10000,
            margin: 0,
            freeMargin: 10000,
            marginLevel: 0,
            totalPnL: 0
        };
        this.wsClient = null;
        this.charts = {};
        this.updateInterval = null;
        this.selectedTrade = null;
        
        // Trade management settings
        this.settings = {
            defaultLeverage: 10,
            defaultRiskPercent: 2,
            trailingStopPercent: 2,
            breakEvenPips: 10,
            partialClosePercent: 50
        };
        
        this.init();
    }
    
    /**
     * Initialize trades manager
     */
    async init() {
        console.log('🚀 Initializing Trades Manager...');
        
        // Setup WebSocket
        this.setupWebSocket();
        
        // Load all data
        await this.loadAllData();
        
        // Initialize charts
        this.initCharts();
        
        // Setup event handlers
        this.setupEventHandlers();
        
        // Start auto-update
        this.startAutoUpdate();
        
        // Initialize UI components
        this.initializeUI();
    }
    
    /**
     * Setup WebSocket connection
     */
    setupWebSocket() {
        this.wsClient = getWebSocketClient();
        
        // Register event handlers
        this.wsClient.on('trade_update', (data) => {
            this.handleTradeUpdate(data);
        });
        
        this.wsClient.on('position_closed', (data) => {
            this.handlePositionClosed(data);
        });
        
        this.wsClient.on('trade_opened', (data) => {
            this.handleTradeOpened(data);
        });
        
        this.wsClient.on('portfolio_update', (data) => {
            this.updatePortfolio(data);
        });
        
        this.wsClient.on('price_update', (data) => {
            this.handlePriceUpdate(data);
        });
    }
    
    /**
     * Load all trades data
     */
    async loadAllData() {
        try {
            await Promise.all([
                this.loadActiveTrades(),
                this.loadTradeHistory(),
                this.loadVirtualTrades(),
                this.loadPortfolioStatus()
            ]);
            
            this.updateStatistics();
            this.updatePortfolioUI();
        } catch (error) {
            console.error('Failed to load data:', error);
            showNotification('Ошибка при загрузке данных', 'error');
        }
    }
    
    /**
     * Load active trades
     */
    async loadActiveTrades() {
        try {
            const response = await fetch('/api/trades/active');
            const result = await response.json();
            
            if (result.success) {
                this.activeTrades = result.trades || [];
                this.renderActiveTrades();
            }
        } catch (error) {
            console.error('Failed to load active trades:', error);
        }
    }
    
    /**
     * Load trade history
     */
    async loadTradeHistory() {
        try {
            const response = await fetch('/api/trades/history?limit=100');
            const result = await response.json();
            
            if (result.success) {
                this.historyTrades = result.trades || [];
                this.renderTradeHistory();
            }
        } catch (error) {
            console.error('Failed to load trade history:', error);
        }
    }
    
    /**
     * Load virtual trades
     */
    async loadVirtualTrades() {
        try {
            const response = await fetch('/api/trades/virtual');
            const result = await response.json();
            
            if (result.success) {
                this.virtualTrades = result.trades || [];
                this.renderVirtualTrades();
            }
        } catch (error) {
            console.error('Failed to load virtual trades:', error);
        }
    }
    
    /**
     * Load portfolio status
     */
    async loadPortfolioStatus() {
        try {
            const response = await fetch('/api/portfolio/status');
            const result = await response.json();
            
            if (result.success) {
                this.portfolio = { ...this.portfolio, ...result.data };
            }
        } catch (error) {
            console.error('Failed to load portfolio status:', error);
        }
    }
    
    /**
     * Render active trades table
     */
    renderActiveTrades() {
        const tbody = document.getElementById('activeTradesBody');
        if (!tbody) return;
        
        if (this.activeTrades.length === 0) {
            tbody.innerHTML = this.getEmptyTradesHTML('active');
            return;
        }
        
        tbody.innerHTML = this.activeTrades.map(trade => this.createActiveTradeRow(trade)).join('');
        
        // Attach event listeners
        this.attachTradeEventListeners();
    }
    
    /**
     * Create active trade row HTML
     */
    createActiveTradeRow(trade) {
        const pnl = this.calculatePnL(trade);
        const pnlPercent = this.calculatePnLPercent(trade, pnl);
        const pnlClass = pnl >= 0 ? 'text-success' : 'text-danger';
        
        return `
            <tr class="trade-row" data-trade-id="${trade.id}">
                <td>#${trade.id}</td>
                <td>
                    <div class="symbol-info">
                        <div class="fw-bold">${trade.symbol}</div>
                        <small class="text-muted">${trade.strategy || 'Manual'}</small>
                    </div>
                </td>
                <td>
                    <span class="badge badge-${trade.side === 'BUY' ? 'success' : 'danger'}">
                        ${trade.side}
                    </span>
                </td>
                <td>${this.formatQuantity(trade.quantity)}</td>
                <td>$${this.formatPrice(trade.entry_price)}</td>
                <td class="current-price" data-symbol="${trade.symbol}">
                    $${this.formatPrice(trade.current_price || trade.entry_price)}
                </td>
                <td class="${pnlClass} fw-bold">
                    ${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toFixed(2)}
                    <small>(${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%)</small>
                </td>
                <td>${this.formatDateTime(trade.created_at)}</td>
                <td>
                    <div class="small">
                        ${trade.stop_loss ? `<span class="text-danger">SL: $${this.formatPrice(trade.stop_loss)}</span>` : '<span class="text-muted">No SL</span>'}<br>
                        ${trade.take_profit ? `<span class="text-success">TP: $${this.formatPrice(trade.take_profit)}</span>` : '<span class="text-muted">No TP</span>'}
                    </div>
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-danger" 
                                onclick="tradesManager.closeTrade(${trade.id})"
                                title="Закрыть позицию">
                            <i class="fas fa-times"></i>
                        </button>
                        <button class="btn btn-warning" 
                                onclick="tradesManager.modifyTrade(${trade.id})"
                                title="Изменить">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-info" 
                                onclick="tradesManager.showTradeChart(${trade.id})"
                                title="График">
                            <i class="fas fa-chart-line"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }
    
    /**
     * Render trade history table
     */
    renderTradeHistory() {
        const tbody = document.getElementById('historyTradesBody');
        if (!tbody) return;
        
        if (this.historyTrades.length === 0) {
            tbody.innerHTML = this.getEmptyTradesHTML('history');
            return;
        }
        
        tbody.innerHTML = this.historyTrades.map(trade => this.createHistoryTradeRow(trade)).join('');
    }
    
    /**
     * Create history trade row HTML
     */
    createHistoryTradeRow(trade) {
        const pnlClass = trade.pnl >= 0 ? 'text-success' : 'text-danger';
        const statusClass = trade.pnl >= 0 ? 'badge-success' : 'badge-danger';
        
        return `
            <tr class="trade-row" data-trade-id="${trade.id}">
                <td>#${trade.id}</td>
                <td>${trade.symbol}</td>
                <td>
                    <span class="badge badge-${trade.side === 'BUY' ? 'success' : 'danger'}">
                        ${trade.side}
                    </span>
                </td>
                <td>${this.formatQuantity(trade.quantity)}</td>
                <td>$${this.formatPrice(trade.entry_price)}</td>
                <td>$${this.formatPrice(trade.exit_price)}</td>
                <td class="${pnlClass} fw-bold">
                    ${trade.pnl >= 0 ? '+' : ''}$${Math.abs(trade.pnl).toFixed(2)}
                </td>
                <td>${this.formatDateTime(trade.created_at)}</td>
                <td>${this.formatDateTime(trade.closed_at)}</td>
                <td>
                    <span class="badge ${statusClass}">
                        ${trade.pnl >= 0 ? 'Profit' : 'Loss'}
                    </span>
                </td>
                <td>
                    <span class="badge badge-secondary">${trade.strategy || 'Manual'}</span>
                </td>
            </tr>
        `;
    }
    
    /**
     * Render virtual trades table
     */
    renderVirtualTrades() {
        const tbody = document.getElementById('virtualTradesBody');
        if (!tbody) return;
        
        if (this.virtualTrades.length === 0) {
            tbody.innerHTML = this.getEmptyTradesHTML('virtual');
            return;
        }
        
        tbody.innerHTML = this.virtualTrades.map(trade => this.createVirtualTradeRow(trade)).join('');
    }
    
    /**
     * Create virtual trade row HTML
     */
    createVirtualTradeRow(trade) {
        const pnl = this.calculatePnL(trade);
        const pnlClass = pnl >= 0 ? 'text-success' : 'text-danger';
        
        return `
            <tr class="trade-row" data-trade-id="${trade.id}">
                <td>#V${trade.id}</td>
                <td>${trade.symbol}</td>
                <td>
                    <span class="badge badge-${trade.side === 'BUY' ? 'success' : 'danger'}">
                        ${trade.side}
                    </span>
                </td>
                <td>${this.formatQuantity(trade.quantity)}</td>
                <td>$${this.formatPrice(trade.entry_price)}</td>
                <td class="current-price" data-symbol="${trade.symbol}">
                    $${this.formatPrice(trade.current_price || trade.entry_price)}
                </td>
                <td class="${pnlClass} fw-bold">
                    ${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toFixed(2)}
                </td>
                <td>${this.formatDateTime(trade.created_at)}</td>
                <td>${trade.strategy || 'Manual'}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-danger" 
                                onclick="tradesManager.closeVirtualTrade(${trade.id})"
                                title="Закрыть">
                            <i class="fas fa-times"></i>
                        </button>
                        <button class="btn btn-success" 
                                onclick="tradesManager.convertToReal(${trade.id})"
                                title="Конвертировать в реальную">
                            <i class="fas fa-rocket"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }
    
    /**
     * Calculate P&L for a trade
     */
    calculatePnL(trade) {
        if (!trade.current_price) return 0;
        
        const priceDiff = trade.side === 'BUY' 
            ? trade.current_price - trade.entry_price
            : trade.entry_price - trade.current_price;
            
        return priceDiff * trade.quantity;
    }
    
    /**
     * Calculate P&L percentage
     */
    calculatePnLPercent(trade, pnl) {
        const investment = trade.entry_price * trade.quantity;
        return investment > 0 ? (pnl / investment) * 100 : 0;
    }
    
    /**
     * Update statistics
     */
    updateStatistics() {
        const stats = {
            totalPnL: 0,
            activeTrades: this.activeTrades.length,
            totalVolume: 0,
            wins: 0,
            losses: 0,
            totalProfit: 0,
            totalLoss: 0,
            largestWin: 0,
            largestLoss: 0,
            avgHoldTime: 0,
            profitFactor: 0
        };
        
        // Calculate from active trades
        this.activeTrades.forEach(trade => {
            const pnl = this.calculatePnL(trade);
            stats.totalPnL += pnl;
            stats.totalVolume += trade.quantity * (trade.current_price || trade.entry_price);
        });
        
        // Calculate from history
        let totalHoldTime = 0;
        this.historyTrades.forEach(trade => {
            if (trade.pnl > 0) {
                stats.wins++;
                stats.totalProfit += trade.pnl;
                stats.largestWin = Math.max(stats.largestWin, trade.pnl);
            } else if (trade.pnl < 0) {
                stats.losses++;
                stats.totalLoss += Math.abs(trade.pnl);
                stats.largestLoss = Math.max(stats.largestLoss, Math.abs(trade.pnl));
            }
            
            // Calculate hold time
            if (trade.created_at && trade.closed_at) {
                const holdTime = new Date(trade.closed_at) - new Date(trade.created_at);
                totalHoldTime += holdTime;
            }
        });
        
        // Calculate derived stats
        const totalTrades = stats.wins + stats.losses;
        stats.winRate = totalTrades > 0 ? (stats.wins / totalTrades * 100) : 0;
        stats.avgProfit = stats.wins > 0 ? stats.totalProfit / stats.wins : 0;
        stats.avgLoss = stats.losses > 0 ? stats.totalLoss / stats.losses : 0;
        stats.profitFactor = stats.totalLoss > 0 ? stats.totalProfit / stats.totalLoss : 
                            stats.totalProfit > 0 ? 999 : 0;
        stats.avgHoldTime = totalTrades > 0 ? totalHoldTime / totalTrades : 0;
        
        // Update UI
        this.updateStatisticsUI(stats);
        this.updateCharts(stats);
    }
    
    /**
     * Update statistics UI
     */
    updateStatisticsUI(stats) {
        // Update summary cards
        document.getElementById('totalPnL').textContent = `$${stats.totalPnL.toFixed(2)}`;
        document.getElementById('totalPnLChange').innerHTML = `
            <i class="fas fa-arrow-${stats.totalPnL >= 0 ? 'up' : 'down'} 
               text-${stats.totalPnL >= 0 ? 'success' : 'danger'}"></i>
            <span>${stats.totalPnL >= 0 ? '+' : ''}${(stats.totalPnL / this.portfolio.balance * 100).toFixed(2)}%</span>
        `;
        
        document.getElementById('activePositions').textContent = stats.activeTrades;
        document.getElementById('totalVolume').textContent = `Объем: $${this.formatVolume(stats.totalVolume)}`;
        
        document.getElementById('winRate').textContent = `${stats.winRate.toFixed(1)}%`;
        document.getElementById('totalTrades').textContent = `${stats.wins + stats.losses} сделок`;
        
        document.getElementById('avgProfit').textContent = `$${stats.avgProfit.toFixed(2)}`;
        document.getElementById('profitFactor').textContent = `PF: ${stats.profitFactor.toFixed(2)}`;
        
        // Update additional statistics if elements exist
        this.updateDetailedStats(stats);
    }
    
    /**
     * Update detailed statistics
     */
    updateDetailedStats(stats) {
        // Win/Loss ratio
        const winLossRatio = stats.losses > 0 ? stats.wins / stats.losses : stats.wins;
        document.getElementById('winLossRatio')?.textContent = winLossRatio.toFixed(2);
        
        // Largest win/loss
        document.getElementById('largestWin')?.textContent = `$${stats.largestWin.toFixed(2)}`;
        document.getElementById('largestLoss')?.textContent = `-$${stats.largestLoss.toFixed(2)}`;
        
        // Average hold time
        const avgHoldHours = stats.avgHoldTime / (1000 * 60 * 60);
        document.getElementById('avgHoldTime')?.textContent = `${avgHoldHours.toFixed(1)}h`;
        
        // Sharpe ratio (simplified)
        const sharpeRatio = this.calculateSharpeRatio(this.historyTrades);
        document.getElementById('sharpeRatio')?.textContent = sharpeRatio.toFixed(2);
    }
    
    /**
     * Calculate Sharpe ratio
     */
    calculateSharpeRatio(trades) {
        if (trades.length < 2) return 0;
        
        const returns = trades.map(t => t.pnl / (t.entry_price * t.quantity));
        const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
        
        const variance = returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length;
        const stdDev = Math.sqrt(variance);
        
        return stdDev > 0 ? (avgReturn / stdDev) * Math.sqrt(252) : 0; // Annualized
    }
    
    /**
     * Initialize charts
     */
    initCharts() {
        // P&L Chart
        this.initPnLChart();
        
        // Distribution Chart
        this.initDistributionChart();
        
        // Performance Chart
        this.initPerformanceChart();
        
        // Win Rate Chart
        this.initWinRateChart();
    }
    
    /**
     * Initialize P&L chart
     */
    initPnLChart() {
        const ctx = document.getElementById('pnlChart')?.getContext('2d');
        if (!ctx) return;
        
        this.charts.pnl = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Cumulative P&L',
                    data: [],
                    borderColor: 'rgb(50, 115, 220)',
                    backgroundColor: 'rgba(50, 115, 220, 0.1)',
                    tension: 0.1,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return `P&L: $${context.parsed.y.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { 
                            color: '#a0a9c9',
                            callback: (value) => '$' + value
                        }
                    },
                    x: {
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { color: '#a0a9c9' }
                    }
                }
            }
        });
    }
    
    /**
     * Initialize distribution chart
     */
    initDistributionChart() {
        const ctx = document.getElementById('distributionChart')?.getContext('2d');
        if (!ctx) return;
        
        this.charts.distribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    backgroundColor: [
                        '#3273dc',
                        '#00ff88',
                        '#ff3860',
                        '#ffdd57',
                        '#b362ff'
                    ],
                    borderColor: 'transparent'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { color: '#a0a9c9' }
                    }
                }
            }
        });
    }
    
    /**
     * Update charts with new data
     */
    updateCharts(stats) {
        this.updatePnLChart();
        this.updateDistributionChart();
        this.updatePerformanceMetrics(stats);
    }
    
    /**
     * Update P&L chart
     */
    updatePnLChart() {
        if (!this.charts.pnl) return;
        
        // Create cumulative P&L data
        const sortedTrades = [...this.historyTrades].sort((a, b) => 
            new Date(a.closed_at) - new Date(b.closed_at)
        );
        
        let cumulativePnL = 0;
        const labels = [];
        const data = [];
        
        sortedTrades.slice(-50).forEach((trade, index) => {
            cumulativePnL += trade.pnl || 0;
            labels.push(`Trade ${index + 1}`);
            data.push(cumulativePnL);
        });
        
        // Add current P&L from active trades
        if (this.activeTrades.length > 0) {
            const currentPnL = this.activeTrades.reduce((sum, trade) => 
                sum + this.calculatePnL(trade), 0
            );
            labels.push('Current');
            data.push(cumulativePnL + currentPnL);
        }
        
        this.charts.pnl.data.labels = labels;
        this.charts.pnl.data.datasets[0].data = data;
        this.charts.pnl.update();
    }
    
    /**
     * Update distribution chart
     */
    updateDistributionChart() {
        if (!this.charts.distribution) return;
        
        const symbolCounts = {};
        
        // Count by symbol
        [...this.activeTrades, ...this.virtualTrades].forEach(trade => {
            symbolCounts[trade.symbol] = (symbolCounts[trade.symbol] || 0) + 1;
        });
        
        // Sort and take top 5
        const sorted = Object.entries(symbolCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5);
        
        this.charts.distribution.data.labels = sorted.map(([symbol]) => symbol);
        this.charts.distribution.data.datasets[0].data = sorted.map(([, count]) => count);
        this.charts.distribution.update();
    }
    
    /**
     * Update portfolio UI
     */
    updatePortfolioUI() {
        // Update portfolio values
        document.getElementById('portfolioBalance')?.textContent = `$${this.portfolio.balance.toFixed(2)}`;
        document.getElementById('portfolioEquity')?.textContent = `$${this.portfolio.equity.toFixed(2)}`;
        document.getElementById('portfolioMargin')?.textContent = `$${this.portfolio.margin.toFixed(2)}`;
        document.getElementById('portfolioFreeMargin')?.textContent = `$${this.portfolio.freeMargin.toFixed(2)}`;
        
        // Update margin level indicator
        const marginLevel = this.portfolio.marginLevel || 0;
        const marginLevelEl = document.getElementById('marginLevel');
        if (marginLevelEl) {
            marginLevelEl.textContent = marginLevel > 0 ? `${marginLevel.toFixed(0)}%` : '∞';
            marginLevelEl.className = marginLevel < 100 ? 'text-danger' : 
                                     marginLevel < 200 ? 'text-warning' : 
                                     'text-success';
        }
    }
    
    /**
     * Close trade
     */
    async closeTrade(tradeId, partial = false, amount = null) {
        const confirmMsg = partial 
            ? `Закрыть ${amount}% позиции #${tradeId}?`
            : `Вы уверены, что хотите закрыть позицию #${tradeId}?`;
            
        if (!confirm(confirmMsg)) return;
        
        try {
            const endpoint = partial ? `/api/trades/partial-close/${tradeId}` : `/api/trades/close/${tradeId}`;
            const body = partial ? { percent: amount } : {};
            
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            
            if (response.ok) {
                showNotification(
                    partial ? 'Позиция частично закрыта' : 'Позиция закрыта успешно', 
                    'success'
                );
                await this.loadAllData();
            } else {
                throw new Error('Failed to close trade');
            }
        } catch (error) {
            console.error('Error closing trade:', error);
            showNotification('Ошибка при закрытии позиции', 'error');
        }
    }
    
    /**
     * Modify trade
     */
    modifyTrade(tradeId) {
        const trade = this.activeTrades.find(t => t.id === tradeId);
        if (!trade) return;
        
        this.selectedTrade = trade;
        
        // Create modify dialog
        const dialog = `
            <div class="modal fade" id="modifyTradeModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content bg-card">
                        <div class="modal-header">
                            <h5 class="modal-title">Изменить позицию #${trade.id}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <form id="modifyTradeForm">
                                <div class="mb-3">
                                    <label class="form-label">Символ</label>
                                    <input type="text" class="form-control" value="${trade.symbol}" disabled>
                                </div>
                                <div class="row mb-3">
                                    <div class="col">
                                        <label class="form-label">Цена входа</label>
                                        <input type="text" class="form-control" 
                                               value="$${this.formatPrice(trade.entry_price)}" disabled>
                                    </div>
                                    <div class="col">
                                        <label class="form-label">Текущая цена</label>
                                        <input type="text" class="form-control" 
                                               value="$${this.formatPrice(trade.current_price)}" disabled>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Stop Loss</label>
                                    <div class="input-group">
                                        <input type="number" class="form-control" name="stopLoss" 
                                               value="${trade.stop_loss || ''}" step="0.01">
                                        <button class="btn btn-outline-secondary" type="button"
                                                onclick="tradesManager.calculateSL('percent')">
                                            <i class="fas fa-percentage"></i>
                                        </button>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Take Profit</label>
                                    <div class="input-group">
                                        <input type="number" class="form-control" name="takeProfit" 
                                               value="${trade.take_profit || ''}" step="0.01">
                                        <button class="btn btn-outline-secondary" type="button"
                                                onclick="tradesManager.calculateTP('rr')">
                                            <i class="fas fa-chart-line"></i>
                                        </button>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Trailing Stop (%)</label>
                                    <input type="number" class="form-control" name="trailingStop" 
                                           value="${trade.trailing_stop || ''}" step="0.1" min="0">
                                </div>
                                <div class="form-check mb-3">
                                    <input class="form-check-input" type="checkbox" 
                                           id="moveToBreakeven" name="moveToBreakeven">
                                    <label class="form-check-label" for="moveToBreakeven">
                                        Перевести в безубыток
                                    </label>
                                </div>
                            </form>
                            
                            <!-- Risk calculations -->
                            <div class="alert alert-info">
                                <div class="d-flex justify-content-between">
                                    <span>Текущий P&L:</span>
                                    <span class="${trade.pnl >= 0 ? 'text-success' : 'text-danger'}">
                                        ${trade.pnl >= 0 ? '+' : ''}$${Math.abs(trade.pnl || 0).toFixed(2)}
                                    </span>
                                </div>
                                <div class="d-flex justify-content-between mt-1">
                                    <span>Риск (с новым SL):</span>
                                    <span id="newRiskAmount">-</span>
                                </div>
                                <div class="d-flex justify-content-between mt-1">
                                    <span>Потенциал (с новым TP):</span>
                                    <span id="newRewardAmount">-</span>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                Отмена
                            </button>
                            <button type="button" class="btn btn-primary" 
                                    onclick="tradesManager.saveTradeModifications()">
                                Сохранить изменения
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', dialog);
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('modifyTradeModal'));
        modal.show();
        
        // Setup event listeners
        this.setupModifyFormListeners();
        
        // Clean up on hide
        document.getElementById('modifyTradeModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }
    
    /**
     * Save trade modifications
     */
    async saveTradeModifications() {
        const form = document.getElementById('modifyTradeForm');
        const formData = new FormData(form);
        
        try {
            const modifications = {
                stop_loss: parseFloat(formData.get('stopLoss')) || null,
                take_profit: parseFloat(formData.get('takeProfit')) || null,
                trailing_stop: parseFloat(formData.get('trailingStop')) || null
            };
            
            if (formData.get('moveToBreakeven')) {
                modifications.stop_loss = this.selectedTrade.entry_price;
            }
            
            const response = await fetch(`/api/trades/modify/${this.selectedTrade.id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(modifications)
            });
            
            if (response.ok) {
                showNotification('Позиция обновлена успешно', 'success');
                bootstrap.Modal.getInstance(document.getElementById('modifyTradeModal')).hide();
                await this.loadAllData();
            } else {
                throw new Error('Failed to modify trade');
            }
        } catch (error) {
            console.error('Error modifying trade:', error);
            showNotification('Ошибка при обновлении позиции', 'error');
        }
    }
    
    /**
     * Show trade chart
     */
    async showTradeChart(tradeId) {
        const trade = [...this.activeTrades, ...this.historyTrades].find(t => t.id === tradeId);
        if (!trade) return;
        
        // Create chart modal
        const modal = `
            <div class="modal fade" id="tradeChartModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content bg-card">
                        <div class="modal-header">
                            <h5 class="modal-title">График ${trade.symbol} - Позиция #${trade.id}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="tradePriceChart" style="height: 400px;"></div>
                            <div class="mt-3">
                                <div class="row">
                                    <div class="col-md-3">
                                        <strong>Вход:</strong> $${this.formatPrice(trade.entry_price)}
                                    </div>
                                    <div class="col-md-3">
                                        <strong>Текущая:</strong> $${this.formatPrice(trade.current_price || trade.exit_price)}
                                    </div>
                                    <div class="col-md-3">
                                        <strong>SL:</strong> ${trade.stop_loss ? '$' + this.formatPrice(trade.stop_loss) : 'Не установлен'}
                                    </div>
                                    <div class="col-md-3">
                                        <strong>TP:</strong> ${trade.take_profit ? '$' + this.formatPrice(trade.take_profit) : 'Не установлен'}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modal);
        
        const modalEl = new bootstrap.Modal(document.getElementById('tradeChartModal'));
        modalEl.show();
        
        // Load and render chart
        await this.loadTradeChart(trade);
        
        // Clean up
        document.getElementById('tradeChartModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }
    
    /**
     * Load and render trade chart
     */
    async loadTradeChart(trade) {
        try {
            // Load price data
            const response = await fetch(`/api/charts/price/${trade.symbol}?period=1h&bars=100`);
            const data = await response.json();
            
            if (data.success) {
                this.renderTradeChart(data.data, trade);
            }
        } catch (error) {
            console.error('Failed to load chart data:', error);
        }
    }
    
    /**
     * Render trade chart using Plotly
     */
    renderTradeChart(priceData, trade) {
        const trace = {
            x: priceData.timestamps,
            y: priceData.prices,
            type: 'scatter',
            mode: 'lines',
            name: 'Price',
            line: { color: 'rgb(50, 115, 220)', width: 2 }
        };
        
        const shapes = [
            // Entry line
            {
                type: 'line',
                x0: priceData.timestamps[0],
                x1: priceData.timestamps[priceData.timestamps.length - 1],
                y0: trade.entry_price,
                y1: trade.entry_price,
                line: { color: 'yellow', width: 2, dash: 'dash' }
            }
        ];
        
        // Add SL line
        if (trade.stop_loss) {
            shapes.push({
                type: 'line',
                x0: priceData.timestamps[0],
                x1: priceData.timestamps[priceData.timestamps.length - 1],
                y0: trade.stop_loss,
                y1: trade.stop_loss,
                line: { color: 'red', width: 2, dash: 'dot' }
            });
        }
        
        // Add TP line
        if (trade.take_profit) {
            shapes.push({
                type: 'line',
                x0: priceData.timestamps[0],
                x1: priceData.timestamps[priceData.timestamps.length - 1],
                y0: trade.take_profit,
                y1: trade.take_profit,
                line: { color: 'green', width: 2, dash: 'dot' }
            });
        }
        
        const layout = {
            title: '',
            xaxis: { title: 'Time', color: '#a0a9c9' },
            yaxis: { title: 'Price ($)', color: '#a0a9c9' },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#a0a9c9' },
            shapes: shapes,
            margin: { t: 20, r: 20, b: 40, l: 60 }
        };
        
        Plotly.newPlot('tradePriceChart', [trace], layout, { responsive: true });
    }
    
    /**
     * Quick actions
     */
    async closeAllPositions() {
        const count = this.activeTrades.length;
        if (count === 0) {
            showNotification('Нет активных позиций для закрытия', 'info');
            return;
        }
        
        if (!confirm(`Вы уверены, что хотите закрыть ВСЕ ${count} позиций?`)) return;
        
        try {
            const response = await fetch('/api/trades/close-all', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (response.ok) {
                showNotification(`Закрыто ${count} позиций`, 'success');
                await this.loadAllData();
            } else {
                throw new Error('Failed to close all positions');
            }
        } catch (error) {
            console.error('Error closing all positions:', error);
            showNotification('Ошибка при закрытии позиций', 'error');
        }
    }
    
    async moveStopsToBreakeven() {
        const eligibleTrades = this.activeTrades.filter(trade => {
            const pnl = this.calculatePnL(trade);
            return pnl > 0 && (!trade.stop_loss || trade.stop_loss < trade.entry_price);
        });
        
        if (eligibleTrades.length === 0) {
            showNotification('Нет позиций для перевода в безубыток', 'info');
            return;
        }
        
        try {
            const response = await fetch('/api/trades/breakeven', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (response.ok) {
                showNotification(`${eligibleTrades.length} позиций переведено в безубыток`, 'success');
                await this.loadAllData();
            }
        } catch (error) {
            console.error('Error moving stops:', error);
            showNotification('Ошибка при переводе в безубыток', 'error');
        }
    }
    
    async enableTrailingStop() {
        const percent = prompt('Введите процент для трейлинг стопа:', '2');
        if (!percent) return;
        
        try {
            const response = await fetch('/api/trades/trailing', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ percent: parseFloat(percent) })
            });
            
            if (response.ok) {
                showNotification('Трейлинг стоп активирован', 'success');
                await this.loadAllData();
            }
        } catch (error) {
            console.error('Error enabling trailing stop:', error);
            showNotification('Ошибка при активации трейлинг стопа', 'error');
        }
    }
    
    /**
     * Risk calculator
     */
    showRiskCalculator() {
        // Create risk calculator modal
        const modal = `
            <div class="modal fade" id="riskCalculatorModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content bg-card">
                        <div class="modal-header">
                            <h5 class="modal-title">Калькулятор рисков</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <form id="riskCalculatorForm">
                                <div class="mb-3">
                                    <label class="form-label">Баланс счета</label>
                                    <input type="number" class="form-control" name="balance" 
                                           value="${this.portfolio.balance}" step="0.01">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Риск на сделку (%)</label>
                                    <input type="number" class="form-control" name="riskPercent" 
                                           value="${this.settings.defaultRiskPercent}" 
                                           step="0.1" min="0.1" max="10">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Цена входа</label>
                                    <input type="number" class="form-control" name="entryPrice" 
                                           step="0.01" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Stop Loss</label>
                                    <input type="number" class="form-control" name="stopLoss" 
                                           step="0.01" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Take Profit (опционально)</label>
                                    <input type="number" class="form-control" name="takeProfit" 
                                           step="0.01">
                                </div>
                            </form>
                            
                            <div id="riskCalculationResult" class="alert alert-info d-none">
                                <!-- Results will be shown here -->
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                Закрыть
                            </button>
                            <button type="button" class="btn btn-primary" 
                                    onclick="tradesManager.calculateRiskPosition()">
                                Рассчитать
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modal);
        
        const modalEl = new bootstrap.Modal(document.getElementById('riskCalculatorModal'));
        modalEl.show();
        
        // Clean up
        document.getElementById('riskCalculatorModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }
    
    /**
     * Calculate risk position
     */
    calculateRiskPosition() {
        const form = document.getElementById('riskCalculatorForm');
        const formData = new FormData(form);
        
        const balance = parseFloat(formData.get('balance'));
        const riskPercent = parseFloat(formData.get('riskPercent'));
        const entryPrice = parseFloat(formData.get('entryPrice'));
        const stopLoss = parseFloat(formData.get('stopLoss'));
        const takeProfit = parseFloat(formData.get('takeProfit'));
        
        // Calculate risk amount
        const riskAmount = balance * (riskPercent / 100);
        
        // Calculate position size based on risk
        const stopDistance = Math.abs(entryPrice - stopLoss);
        const positionSize = riskAmount / stopDistance;
        
        // Calculate potential profit
        let potentialProfit = 0;
        let riskRewardRatio = 0;
        
        if (takeProfit) {
            const profitDistance = Math.abs(takeProfit - entryPrice);
            potentialProfit = positionSize * profitDistance;
            riskRewardRatio = potentialProfit / riskAmount;
        }
        
        // Show results
        const resultDiv = document.getElementById('riskCalculationResult');
        resultDiv.classList.remove('d-none');
        resultDiv.innerHTML = `
            <h6>Результаты расчета:</h6>
            <div class="row">
                <div class="col-6">
                    <strong>Риск:</strong> $${riskAmount.toFixed(2)}
                </div>
                <div class="col-6">
                    <strong>Размер позиции:</strong> ${positionSize.toFixed(4)}
                </div>
            </div>
            <div class="row mt-2">
                <div class="col-6">
                    <strong>Дистанция до SL:</strong> $${stopDistance.toFixed(2)}
                </div>
                <div class="col-6">
                    <strong>Потенциальная прибыль:</strong> $${potentialProfit.toFixed(2)}
                </div>
            </div>
            ${riskRewardRatio > 0 ? `
            <div class="row mt-2">
                <div class="col-12">
                    <strong>Risk/Reward:</strong> 1:${riskRewardRatio.toFixed(2)}
                    <span class="${riskRewardRatio >= 2 ? 'text-success' : riskRewardRatio >= 1 ? 'text-warning' : 'text-danger'}">
                        ${riskRewardRatio >= 2 ? '✓ Отличное' : riskRewardRatio >= 1 ? '⚠ Приемлемое' : '✗ Низкое'}
                    </span>
                </div>
            </div>
            ` : ''}
        `;
    }
    
    /**
     * Handle real-time updates
     */
    handleTradeUpdate(data) {
        // Update active trade
        const tradeIndex = this.activeTrades.findIndex(t => t.id === data.id);
        if (tradeIndex !== -1) {
            this.activeTrades[tradeIndex] = { ...this.activeTrades[tradeIndex], ...data };
            this.updateTradeRow(data);
        }
        
        // Update statistics
        this.updateStatistics();
    }
    
    handlePositionClosed(data) {
        // Remove from active trades
        this.activeTrades = this.activeTrades.filter(t => t.id !== data.id);
        
        // Add to history
        this.historyTrades.unshift(data);
        
        // Re-render tables
        this.renderActiveTrades();
        this.renderTradeHistory();
        
        // Update statistics
        this.updateStatistics();
        
        // Show notification
        const pnlClass = data.pnl >= 0 ? 'success' : 'danger';
        showNotification(
            `Позиция #${data.id} закрыта. P&L: ${data.pnl >= 0 ? '+' : ''}$${data.pnl.toFixed(2)}`,
            data.pnl >= 0 ? 'success' : 'warning'
        );
    }
    
    handleTradeOpened(data) {
        // Add to active trades
        this.activeTrades.push(data);
        
        // Re-render table
        this.renderActiveTrades();
        
        // Update statistics
        this.updateStatistics();
        
        // Show notification
        showNotification(`Новая позиция открыта: ${data.symbol} ${data.side}`, 'success');
    }
    
    handlePriceUpdate(priceData) {
        // Update current prices in active trades
        priceData.forEach(({ symbol, price }) => {
            // Update in data
            this.activeTrades.forEach(trade => {
                if (trade.symbol === symbol) {
                    trade.current_price = price;
                }
            });
            
            // Update in UI
            document.querySelectorAll(`.current-price[data-symbol="${symbol}"]`).forEach(el => {
                el.textContent = `$${this.formatPrice(price)}`;
            });
        });
        
        // Update P&L values
        this.updatePnLValues();
    }
    
    /**
     * Update P&L values in the table
     */
    updatePnLValues() {
        this.activeTrades.forEach(trade => {
            const row = document.querySelector(`tr[data-trade-id="${trade.id}"]`);
            if (row) {
                const pnl = this.calculatePnL(trade);
                const pnlPercent = this.calculatePnLPercent(trade, pnl);
                const pnlCell = row.querySelector('td:nth-child(7)');
                
                if (pnlCell) {
                    pnlCell.className = pnl >= 0 ? 'text-success fw-bold' : 'text-danger fw-bold';
                    pnlCell.innerHTML = `
                        ${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toFixed(2)}
                        <small>(${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%)</small>
                    `;
                }
            }
        });
        
        // Update statistics
        this.updateStatistics();
    }
    
    /**
     * Start auto-update
     */
    startAutoUpdate() {
        // Update every 5 seconds
        this.updateInterval = setInterval(() => {
            if (this.activeTrades.length > 0) {
                this.loadActiveTrades();
            }
        }, 5000);
    }
    
    /**
     * Setup event handlers
     */
    setupEventHandlers() {
        // Tab change handler
        document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
            tab.addEventListener('shown.bs.tab', (e) => {
                const target = e.target.getAttribute('data-bs-target');
                if (target === '#history' && this.historyTrades.length === 0) {
                    this.loadTradeHistory();
                } else if (target === '#virtual' && this.virtualTrades.length === 0) {
                    this.loadVirtualTrades();
                }
            });
        });
        
        // Quick action buttons
        document.getElementById('closeAllBtn')?.addEventListener('click', () => {
            this.closeAllPositions();
        });
        
        document.getElementById('breakEvenBtn')?.addEventListener('click', () => {
            this.moveStopsToBreakeven();
        });
        
        document.getElementById('trailingStopBtn')?.addEventListener('click', () => {
            this.enableTrailingStop();
        });
        
        document.getElementById('riskCalculatorBtn')?.addEventListener('click', () => {
            this.showRiskCalculator();
        });
        
        // Export button
        document.getElementById('exportTradesBtn')?.addEventListener('click', () => {
            this.exportTrades();
        });
        
        // New trade button
        document.getElementById('newTradeBtn')?.addEventListener('click', () => {
            this.openNewTradeDialog();
        });
    }
    
    /**
     * Initialize UI components
     */
    initializeUI() {
        // Initialize tooltips
        const tooltipTriggerList = [].slice.call(
            document.querySelectorAll('[data-bs-toggle="tooltip"]')
        );
        tooltipTriggerList.map(tooltipTriggerEl => 
            new bootstrap.Tooltip(tooltipTriggerEl)
        );
    }
    
    /**
     * Export trades
     */
    exportTrades() {
        const allTrades = [...this.activeTrades, ...this.historyTrades];
        const csv = this.convertTradesToCSV(allTrades);
        
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `trades_export_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
        
        showNotification('Данные экспортированы', 'success');
    }
    
    /**
     * Convert trades to CSV
     */
    convertTradesToCSV(trades) {
        const headers = [
            'ID', 'Symbol', 'Side', 'Quantity', 'Entry Price', 
            'Exit Price', 'P&L', 'Created At', 'Closed At', 
            'Strategy', 'Status'
        ];
        
        const rows = trades.map(trade => [
            trade.id,
            trade.symbol,
            trade.side,
            trade.quantity,
            trade.entry_price,
            trade.exit_price || trade.current_price || '',
            trade.pnl || this.calculatePnL(trade),
            trade.created_at,
            trade.closed_at || '',
            trade.strategy || 'Manual',
            trade.closed_at ? 'Closed' : 'Active'
        ]);
        
        return [headers, ...rows].map(row => row.join(',')).join('\n');
    }
    
    // Utility methods
    formatPrice(price) {
        return parseFloat(price || 0).toFixed(2);
    }
    
    formatQuantity(quantity) {
        return parseFloat(quantity || 0).toFixed(4);
    }
    
    formatVolume(volume) {
        if (volume > 1e6) return (volume / 1e6).toFixed(2) + 'M';
        if (volume > 1e3) return (volume / 1e3).toFixed(2) + 'K';
        return volume.toFixed(0);
    }
    
    formatDateTime(timestamp) {
        if (!timestamp) return '-';
        const date = new Date(timestamp);
        return date.toLocaleString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    getEmptyTradesHTML(type) {
        const messages = {
            active: 'Нет активных позиций',
            history: 'История сделок пуста',
            virtual: 'Нет виртуальных сделок'
        };
        
        const icons = {
            active: 'inbox',
            history: 'history',
            virtual: 'flask'
        };
        
        return `
            <tr>
                <td colspan="10" class="text-center py-5">
                    <i class="fas fa-${icons[type]} fa-3x text-muted mb-3"></i>
                    <p class="text-muted">${messages[type]}</p>
                </td>
            </tr>
        `;
    }
    
    /**
     * Cleanup on destroy
     */
    destroy() {
        // Clear intervals
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        // Remove event listeners
        this.wsClient?.off('trade_update');
        this.wsClient?.off('position_closed');
        this.wsClient?.off('trade_opened');
        this.wsClient?.off('portfolio_update');
        this.wsClient?.off('price_update');
    }
}

// Initialize on page load
let tradesManager = null;

document.addEventListener('DOMContentLoaded', () => {
    // Initialize WebSocket if not already done
    if (!window.wsClient) {
        initializeWebSocket({ debug: true });
    }
    
    // Initialize trades manager
    tradesManager = new TradesManager();
    
    // Make it globally accessible
    window.tradesManager = tradesManager;
});
/**
 * Signals Matrix Management Module
 * Handles all functionality for the signals matrix page
 */

class SignalsMatrixManager {
    constructor() {
        this.signals = new Map();
        this.filters = {
            strategy: '',
            signal: '',
            risk: '',
            minConfidence: 0,
            search: ''
        };
        this.sortConfig = {
            field: 'symbol',
            direction: 'asc'
        };
        this.autoRefresh = true;
        this.refreshInterval = 30000; // 30 seconds
        this.refreshTimer = null;
        this.wsClient = null;
        this.selectedSymbol = null;
        this.viewMode = 'table'; // table or cards
        
        // Strategy configuration
        this.strategyConfig = {
            whale_hunting: { name: 'Whale Hunting', shortName: 'WH', weight: 1.5 },
            sleeping_giants: { name: 'Sleeping Giants', shortName: 'SG', weight: 1.3 },
            order_book_analysis: { name: 'Order Book Analysis', shortName: 'OB', weight: 1.2 },
            multi_indicator: { name: 'Multi Indicator', shortName: 'MI', weight: 1.0 },
            ml_prediction: { name: 'ML Prediction', shortName: 'ML', weight: 1.0 },
            momentum: { name: 'Momentum', shortName: 'MO', weight: 0.8 },
            mean_reversion: { name: 'Mean Reversion', shortName: 'MR', weight: 0.7 },
            scalping: { name: 'Scalping', shortName: 'SC', weight: 0.5 }
        };
        
        this.init();
    }
    
    /**
     * Initialize the signals matrix manager
     */
    async init() {
        console.log('🚀 Initializing Signals Matrix Manager...');
        
        // Setup WebSocket connection
        this.setupWebSocket();
        
        // Load initial data
        await this.loadSignalsMatrix();
        
        // Setup event handlers
        this.setupEventHandlers();
        
        // Setup auto-refresh
        this.setupAutoRefresh();
        
        // Initialize UI components
        this.initializeUI();
        
        // Update statistics
        this.updateStatistics();
    }
    
    /**
     * Setup WebSocket connection
     */
    setupWebSocket() {
        this.wsClient = getWebSocketClient();
        
        // Register event handlers
        this.wsClient.on('signal_matrix_update', (data) => {
            this.handleSignalUpdate(data);
        });
        
        this.wsClient.on('signal_alert', (data) => {
            this.handleSignalAlert(data);
        });
        
        this.wsClient.on('strategy_performance_update', (data) => {
            this.updateStrategyPerformance(data);
        });
    }
    
    /**
     * Load signals matrix data
     */
    async loadSignalsMatrix() {
        try {
            this.showLoading(true);
            
            const response = await fetch('/api/signals/matrix');
            const result = await response.json();
            
            if (result.success && result.data) {
                // Clear existing signals
                this.signals.clear();
                
                // Process each signal
                result.data.forEach(signal => {
                    this.signals.set(signal.symbol, this.processSignalData(signal));
                });
                
                // Render the view
                this.renderView();
                
                this.showLoading(false);
            } else {
                throw new Error(result.message || 'Failed to load signals');
            }
        } catch (error) {
            console.error('Failed to load signals matrix:', error);
            this.showError('Не удалось загрузить данные сигналов');
            this.showLoading(false);
        }
    }
    
    /**
     * Process signal data with enhancements
     */
    processSignalData(signal) {
        const processed = {
            ...signal,
            processed_at: new Date(),
            strength_score: this.calculateStrengthScore(signal),
            recommendation: this.generateRecommendation(signal),
            trend: this.analyzeTrend(signal),
            signals_count: this.countSignals(signal)
        };
        
        return processed;
    }
    
    /**
     * Calculate signal strength score
     */
    calculateStrengthScore(signal) {
        let score = 0;
        let weights = 0;
        
        if (signal.strategies_analysis) {
            Object.entries(signal.strategies_analysis).forEach(([strategy, data]) => {
                if (data.confidence && this.strategyConfig[strategy]) {
                    const weight = this.strategyConfig[strategy].weight;
                    score += data.confidence * weight;
                    weights += weight;
                }
            });
        }
        
        if (weights > 0) {
            score = score / weights;
        }
        
        // Factor in risk assessment
        if (signal.risk_assessment) {
            const riskMultiplier = {
                'LOW': 1.1,
                'MEDIUM': 1.0,
                'HIGH': 0.9
            };
            score *= riskMultiplier[signal.risk_assessment.level] || 1;
        }
        
        return Math.min(100, Math.round(score * 100));
    }
    
    /**
     * Generate recommendation based on signal analysis
     */
    generateRecommendation(signal) {
        const recommendations = [];
        
        if (signal.aggregated_signal) {
            const { action, confidence } = signal.aggregated_signal;
            
            if (confidence > 0.8) {
                recommendations.push(`Очень сильный сигнал на ${action === 'BUY' ? 'покупку' : action === 'SELL' ? 'продажу' : 'ожидание'}`);
            } else if (confidence > 0.6) {
                recommendations.push(`Сильный сигнал на ${action === 'BUY' ? 'покупку' : action === 'SELL' ? 'продажу' : 'ожидание'}`);
            } else if (confidence > 0.4) {
                recommendations.push(`Умеренный сигнал на ${action === 'BUY' ? 'покупку' : action === 'SELL' ? 'продажу' : 'ожидание'}`);
            } else {
                recommendations.push('Слабый сигнал, рекомендуется ожидание');
            }
        }
        
        if (signal.risk_assessment) {
            if (signal.risk_assessment.level === 'HIGH') {
                recommendations.push('⚠️ Высокий риск - уменьшите размер позиции');
            } else if (signal.risk_assessment.level === 'LOW') {
                recommendations.push('✅ Низкий риск - благоприятные условия');
            }
        }
        
        return recommendations.join('. ');
    }
    
    /**
     * Analyze price trend
     */
    analyzeTrend(signal) {
        if (!signal.price_change_24h) return 'neutral';
        
        if (signal.price_change_24h > 5) return 'strong_up';
        if (signal.price_change_24h > 2) return 'up';
        if (signal.price_change_24h < -5) return 'strong_down';
        if (signal.price_change_24h < -2) return 'down';
        
        return 'neutral';
    }
    
    /**
     * Count signals by type
     */
    countSignals(signal) {
        const counts = { buy: 0, sell: 0, neutral: 0 };
        
        if (signal.strategies_analysis) {
            Object.values(signal.strategies_analysis).forEach(strategy => {
                if (strategy.signal === 'BUY') counts.buy++;
                else if (strategy.signal === 'SELL') counts.sell++;
                else counts.neutral++;
            });
        }
        
        return counts;
    }
    
    /**
     * Render the current view (table or cards)
     */
    renderView() {
        if (this.viewMode === 'table') {
            this.renderTableView();
        } else {
            this.renderCardsView();
        }
    }
    
    /**
     * Render table view
     */
    renderTableView() {
        const tbody = document.getElementById('signalsTableBody');
        if (!tbody) return;
        
        const filteredSignals = this.getFilteredAndSortedSignals();
        
        if (filteredSignals.length === 0) {
            tbody.innerHTML = this.getEmptyStateHTML();
            return;
        }
        
        tbody.innerHTML = filteredSignals.map(signal => this.createSignalRow(signal)).join('');
        
        // Add event listeners to rows
        this.attachRowEventListeners();
    }
    
    /**
     * Create signal table row HTML
     */
    createSignalRow(signal) {
        const priceChangeClass = signal.price_change_24h >= 0 ? 'price-up' : 'price-down';
        const trendIcon = this.getTrendIcon(signal.trend);
        
        return `
            <tr class="signal-row" data-symbol="${signal.symbol}">
                <td>
                    <div class="symbol-info">
                        <div class="symbol-icon">${this.getSymbolIcon(signal.symbol)}</div>
                        <div class="symbol-details">
                            <div class="symbol-name">${signal.symbol}</div>
                            <div class="symbol-volume">Vol: ${this.formatVolume(signal.volume_24h)}</div>
                        </div>
                    </div>
                </td>
                <td>
                    <div class="price-info">
                        <div class="current-price">$${this.formatPrice(signal.current_price)}</div>
                        <div class="${priceChangeClass}">
                            ${trendIcon}
                            ${signal.price_change_24h >= 0 ? '+' : ''}${signal.price_change_24h?.toFixed(2) || 0}%
                        </div>
                    </div>
                </td>
                <td>${this.renderStrategyPills(signal)}</td>
                <td>${this.renderConfidenceMeter(signal.aggregated_signal?.confidence)}</td>
                <td>${this.renderAggregatedSignal(signal.aggregated_signal)}</td>
                <td>${this.renderRiskBadge(signal.risk_assessment)}</td>
                <td>${this.renderTargetLevels(signal.aggregated_signal)}</td>
                <td>${this.renderActionButtons(signal)}</td>
            </tr>
        `;
    }
    
    /**
     * Render strategy pills
     */
    renderStrategyPills(signal) {
        if (!signal.strategies_analysis) return '-';
        
        const pills = Object.entries(signal.strategies_analysis)
            .map(([strategy, data]) => {
                const config = this.strategyConfig[strategy];
                if (!config) return '';
                
                const signalClass = (data.signal || 'NEUTRAL').toLowerCase();
                const confidence = Math.round((data.confidence || 0) * 100);
                
                return `
                    <span class="badge badge-${signalClass} strategy-pill" 
                          data-strategy="${strategy}"
                          data-bs-toggle="tooltip" 
                          title="${config.name}: ${confidence}% уверенность">
                        ${config.shortName}
                    </span>
                `;
            })
            .join('');
        
        return `<div class="strategy-pills">${pills}</div>`;
    }
    
    /**
     * Render confidence meter
     */
    renderConfidenceMeter(confidence) {
        if (!confidence) return '-';
        
        const percent = Math.round(confidence * 100);
        const colorClass = percent >= 70 ? 'bg-success' : 
                          percent >= 50 ? 'bg-warning' : 
                          'bg-danger';
        
        return `
            <div class="confidence-meter">
                <div class="progress">
                    <div class="progress-bar ${colorClass}" 
                         style="width: ${percent}%"
                         role="progressbar">
                    </div>
                </div>
                <span class="confidence-value">${percent}%</span>
            </div>
        `;
    }
    
    /**
     * Render aggregated signal badge
     */
    renderAggregatedSignal(signal) {
        if (!signal || !signal.action) return '-';
        
        const signalClass = signal.action.toLowerCase();
        return `<span class="badge badge-lg badge-${signalClass}">${signal.action}</span>`;
    }
    
    /**
     * Render risk badge
     */
    renderRiskBadge(risk) {
        if (!risk || !risk.level) return '-';
        
        const riskClass = `risk-${risk.level.toLowerCase()}`;
        return `
            <span class="badge ${riskClass}" 
                  data-bs-toggle="tooltip" 
                  title="Риск-счет: ${Math.round((risk.score || 0) * 100)}%">
                ${risk.level}
            </span>
        `;
    }
    
    /**
     * Render target levels
     */
    renderTargetLevels(signal) {
        if (!signal) return '-';
        
        const levels = [];
        
        if (signal.take_profit) {
            levels.push(`<span class="text-success">TP: $${this.formatPrice(signal.take_profit)}</span>`);
        }
        
        if (signal.stop_loss) {
            levels.push(`<span class="text-danger">SL: $${this.formatPrice(signal.stop_loss)}</span>`);
        }
        
        if (signal.risk_reward_ratio) {
            levels.push(`<span class="text-muted">RR: ${signal.risk_reward_ratio.toFixed(2)}</span>`);
        }
        
        return levels.length > 0 ? `<div class="target-levels">${levels.join('<br>')}</div>` : '-';
    }
    
    /**
     * Render action buttons
     */
    renderActionButtons(signal) {
        return `
            <div class="btn-group btn-group-sm">
                <button class="btn btn-success" 
                        onclick="signalsMatrix.openVirtualTrade('${signal.symbol}', 'BUY')"
                        title="Виртуальная покупка">
                    <i class="fas fa-arrow-up"></i>
                </button>
                <button class="btn btn-danger" 
                        onclick="signalsMatrix.openVirtualTrade('${signal.symbol}', 'SELL')"
                        title="Виртуальная продажа">
                    <i class="fas fa-arrow-down"></i>
                </button>
                <button class="btn btn-info" 
                        onclick="signalsMatrix.showSignalDetails('${signal.symbol}')"
                        title="Детальный анализ">
                    <i class="fas fa-chart-line"></i>
                </button>
                <button class="btn btn-secondary" 
                        onclick="signalsMatrix.addToWatchlist('${signal.symbol}')"
                        title="Добавить в избранное">
                    <i class="fas fa-star"></i>
                </button>
            </div>
        `;
    }
    
    /**
     * Get filtered and sorted signals
     */
    getFilteredAndSortedSignals() {
        let signals = Array.from(this.signals.values());
        
        // Apply filters
        signals = this.applyFilters(signals);
        
        // Apply sorting
        signals = this.applySorting(signals);
        
        return signals;
    }
    
    /**
     * Apply filters to signals
     */
    applyFilters(signals) {
        return signals.filter(signal => {
            // Search filter
            if (this.filters.search) {
                const searchLower = this.filters.search.toLowerCase();
                if (!signal.symbol.toLowerCase().includes(searchLower)) {
                    return false;
                }
            }
            
            // Strategy filter
            if (this.filters.strategy) {
                if (!signal.strategies_analysis || 
                    !signal.strategies_analysis[this.filters.strategy]) {
                    return false;
                }
            }
            
            // Signal type filter
            if (this.filters.signal) {
                if (!signal.aggregated_signal || 
                    signal.aggregated_signal.action !== this.filters.signal) {
                    return false;
                }
            }
            
            // Risk filter
            if (this.filters.risk) {
                if (!signal.risk_assessment || 
                    signal.risk_assessment.level !== this.filters.risk) {
                    return false;
                }
            }
            
            // Confidence filter
            if (this.filters.minConfidence > 0) {
                const confidence = (signal.aggregated_signal?.confidence || 0) * 100;
                if (confidence < this.filters.minConfidence) {
                    return false;
                }
            }
            
            return true;
        });
    }
    
    /**
     * Apply sorting to signals
     */
    applySorting(signals) {
        const { field, direction } = this.sortConfig;
        const multiplier = direction === 'asc' ? 1 : -1;
        
        return signals.sort((a, b) => {
            let aValue, bValue;
            
            switch (field) {
                case 'symbol':
                    aValue = a.symbol;
                    bValue = b.symbol;
                    break;
                case 'price':
                    aValue = a.current_price || 0;
                    bValue = b.current_price || 0;
                    break;
                case 'change':
                    aValue = a.price_change_24h || 0;
                    bValue = b.price_change_24h || 0;
                    break;
                case 'confidence':
                    aValue = a.aggregated_signal?.confidence || 0;
                    bValue = b.aggregated_signal?.confidence || 0;
                    break;
                case 'strength':
                    aValue = a.strength_score || 0;
                    bValue = b.strength_score || 0;
                    break;
                default:
                    return 0;
            }
            
            if (aValue < bValue) return -1 * multiplier;
            if (aValue > bValue) return 1 * multiplier;
            return 0;
        });
    }
    
    /**
     * Handle signal update from WebSocket
     */
    handleSignalUpdate(updates) {
        if (!Array.isArray(updates)) {
            updates = [updates];
        }
        
        updates.forEach(update => {
            const processed = this.processSignalData(update);
            this.signals.set(update.symbol, processed);
            
            // Update specific row if in table view
            if (this.viewMode === 'table') {
                this.updateSignalRow(processed);
            }
        });
        
        // Update statistics
        this.updateStatistics();
        
        // Re-render if in cards view
        if (this.viewMode === 'cards') {
            this.renderView();
        }
    }
    
    /**
     * Update specific signal row
     */
    updateSignalRow(signal) {
        const row = document.querySelector(`tr[data-symbol="${signal.symbol}"]`);
        if (row) {
            const newRow = document.createElement('tr');
            newRow.innerHTML = this.createSignalRow(signal);
            row.replaceWith(newRow.firstElementChild);
            
            // Add highlight effect
            const updatedRow = document.querySelector(`tr[data-symbol="${signal.symbol}"]`);
            updatedRow.classList.add('row-updated');
            setTimeout(() => {
                updatedRow.classList.remove('row-updated');
            }, 1000);
        }
    }
    
    /**
     * Show signal details modal
     */
    async showSignalDetails(symbol) {
        this.selectedSymbol = symbol;
        const signal = this.signals.get(symbol);
        
        if (!signal) return;
        
        // Show loading in modal
        this.showModalLoading(true);
        
        try {
            // Load additional details
            const response = await fetch(`/api/signals/details/${symbol}`);
            const result = await response.json();
            
            if (result.success) {
                this.renderDetailModal(signal, result.data);
            } else {
                throw new Error(result.message || 'Failed to load details');
            }
        } catch (error) {
            console.error('Failed to load signal details:', error);
            this.renderDetailModal(signal, null);
        } finally {
            this.showModalLoading(false);
        }
    }
    
    /**
     * Render detail modal content
     */
    renderDetailModal(signal, additionalDetails) {
        const modalTitle = document.getElementById('modalTitle');
        const modalBody = document.getElementById('modalBody');
        
        modalTitle.textContent = `Детальный анализ ${signal.symbol}`;
        
        modalBody.innerHTML = `
            <!-- Nav tabs -->
            <ul class="nav nav-tabs mb-4" role="tablist">
                <li class="nav-item">
                    <a class="nav-link active" data-bs-toggle="tab" href="#overview-tab">Обзор</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" data-bs-toggle="tab" href="#strategies-tab">Стратегии</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" data-bs-toggle="tab" href="#indicators-tab">Индикаторы</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" data-bs-toggle="tab" href="#chart-tab">График</a>
                </li>
            </ul>
            
            <!-- Tab content -->
            <div class="tab-content">
                <!-- Overview Tab -->
                <div class="tab-pane fade show active" id="overview-tab">
                    ${this.renderOverviewTab(signal, additionalDetails)}
                </div>
                
                <!-- Strategies Tab -->
                <div class="tab-pane fade" id="strategies-tab">
                    ${this.renderStrategiesTab(signal)}
                </div>
                
                <!-- Indicators Tab -->
                <div class="tab-pane fade" id="indicators-tab">
                    ${this.renderIndicatorsTab(additionalDetails)}
                </div>
                
                <!-- Chart Tab -->
                <div class="tab-pane fade" id="chart-tab">
                    <div id="priceChart" class="chart-container large"></div>
                </div>
            </div>
        `;
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('detailModal'));
        modal.show();
        
        // Initialize chart when tab is shown
        document.querySelector('a[href="#chart-tab"]').addEventListener('shown.bs.tab', () => {
            if (additionalDetails?.price_data) {
                this.renderPriceChart(additionalDetails.price_data);
            }
        });
    }
    
    /**
     * Open virtual trade dialog
     */
    async openVirtualTrade(symbol, side) {
        const signal = this.signals.get(symbol);
        if (!signal) return;
        
        // Create trade dialog
        const dialog = `
            <div class="modal fade" id="virtualTradeModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content bg-card">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                Виртуальная ${side === 'BUY' ? 'покупка' : 'продажа'} ${symbol}
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <form id="virtualTradeForm">
                                <div class="mb-3">
                                    <label class="form-label">Текущая цена</label>
                                    <input type="text" class="form-control" 
                                           value="$${this.formatPrice(signal.current_price)}" 
                                           disabled>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Количество</label>
                                    <input type="number" class="form-control" 
                                           name="quantity" value="0.001" 
                                           step="0.001" min="0.001" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Stop Loss</label>
                                    <input type="number" class="form-control" 
                                           name="stopLoss" 
                                           value="${signal.aggregated_signal?.stop_loss || ''}"
                                           step="0.01">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Take Profit</label>
                                    <input type="number" class="form-control" 
                                           name="takeProfit" 
                                           value="${signal.aggregated_signal?.take_profit || ''}"
                                           step="0.01">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Стратегия</label>
                                    <select class="form-control" name="strategy">
                                        <option value="manual">Ручная</option>
                                        ${Object.entries(this.strategyConfig).map(([key, config]) => 
                                            `<option value="${key}">${config.name}</option>`
                                        ).join('')}
                                    </select>
                                </div>
                            </form>
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle"></i>
                                Уверенность в сигнале: ${Math.round((signal.aggregated_signal?.confidence || 0) * 100)}%
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                Отмена
                            </button>
                            <button type="button" class="btn btn-${side === 'BUY' ? 'success' : 'danger'}" 
                                    onclick="signalsMatrix.executeVirtualTrade('${symbol}', '${side}')">
                                ${side === 'BUY' ? 'Купить' : 'Продать'}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', dialog);
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('virtualTradeModal'));
        modal.show();
        
        // Clean up on hide
        document.getElementById('virtualTradeModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }
    
    /**
     * Execute virtual trade
     */
    async executeVirtualTrade(symbol, side) {
        const form = document.getElementById('virtualTradeForm');
        const formData = new FormData(form);
        
        try {
            const response = await fetch('/api/trades/virtual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: symbol,
                    side: side,
                    quantity: parseFloat(formData.get('quantity')),
                    stop_loss: parseFloat(formData.get('stopLoss')) || null,
                    take_profit: parseFloat(formData.get('takeProfit')) || null,
                    strategy: formData.get('strategy')
                })
            });
            
            if (response.ok) {
                showNotification('Виртуальная сделка открыта успешно!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('virtualTradeModal')).hide();
            } else {
                throw new Error('Failed to open trade');
            }
        } catch (error) {
            console.error('Trade error:', error);
            showNotification('Ошибка при открытии сделки', 'error');
        }
    }
    
    /**
     * Update statistics
     */
    updateStatistics() {
        const stats = {
            total: 0,
            buy: 0,
            sell: 0,
            neutral: 0,
            totalConfidence: 0,
            highRisk: 0,
            strongSignals: 0
        };
        
        this.signals.forEach(signal => {
            stats.total++;
            
            if (signal.aggregated_signal) {
                const action = signal.aggregated_signal.action;
                if (action === 'BUY') stats.buy++;
                else if (action === 'SELL') stats.sell++;
                else stats.neutral++;
                
                if (signal.aggregated_signal.confidence) {
                    stats.totalConfidence += signal.aggregated_signal.confidence;
                    if (signal.aggregated_signal.confidence > 0.7) {
                        stats.strongSignals++;
                    }
                }
            }
            
            if (signal.risk_assessment?.level === 'HIGH') {
                stats.highRisk++;
            }
        });
        
        // Update UI
        this.updateStatisticsUI(stats);
    }
    
    /**
     * Update statistics UI
     */
    updateStatisticsUI(stats) {
        // Update counters
        document.getElementById('totalSignals').textContent = stats.total;
        document.getElementById('buySignals').textContent = stats.buy;
        document.getElementById('sellSignals').textContent = stats.sell;
        
        // Update average confidence
        const avgConfidence = stats.total > 0 ? 
            Math.round(stats.totalConfidence / stats.total * 100) : 0;
        document.getElementById('avgConfidence').textContent = avgConfidence + '%';
        
        // Update badges
        this.updateStatBadges(stats);
    }
    
    /**
     * Update stat badges
     */
    updateStatBadges(stats) {
        // Buy signals badge
        const buyBadge = document.querySelector('#buySignals').parentElement;
        if (buyBadge) {
            const changeEl = buyBadge.querySelector('.stat-change');
            if (stats.buy > stats.sell) {
                changeEl.innerHTML = '<i class="fas fa-arrow-up"></i> Сильные';
                changeEl.classList.add('text-success');
            } else {
                changeEl.innerHTML = '<i class="fas fa-arrow-right"></i> Умеренные';
                changeEl.classList.remove('text-success');
            }
        }
        
        // Add more badge updates as needed
    }
    
    /**
     * Setup event handlers
     */
    setupEventHandlers() {
        // Filter controls
        document.getElementById('strategyFilter')?.addEventListener('change', (e) => {
            this.filters.strategy = e.target.value;
            this.renderView();
        });
        
        document.getElementById('signalFilter')?.addEventListener('change', (e) => {
            this.filters.signal = e.target.value;
            this.renderView();
        });
        
        document.getElementById('riskFilter')?.addEventListener('change', (e) => {
            this.filters.risk = e.target.value;
            this.renderView();
        });
        
        document.getElementById('confidenceFilter')?.addEventListener('input', (e) => {
            this.filters.minConfidence = parseFloat(e.target.value) || 0;
            this.renderView();
        });
        
        document.getElementById('searchFilter')?.addEventListener('input', (e) => {
            this.filters.search = e.target.value;
            this.renderView();
        });
        
        // Sort controls
        document.querySelectorAll('.sortable').forEach(header => {
            header.addEventListener('click', () => {
                const field = header.dataset.sort;
                if (this.sortConfig.field === field) {
                    this.sortConfig.direction = this.sortConfig.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    this.sortConfig.field = field;
                    this.sortConfig.direction = 'asc';
                }
                this.renderView();
                this.updateSortIndicators();
            });
        });
        
        // View mode toggle
        document.getElementById('viewModeToggle')?.addEventListener('click', () => {
            this.viewMode = this.viewMode === 'table' ? 'cards' : 'table';
            this.renderView();
        });
        
        // Refresh button
        document.getElementById('refreshButton')?.addEventListener('click', () => {
            this.loadSignalsMatrix();
        });
        
        // Auto-refresh toggle
        document.getElementById('autoRefreshToggle')?.addEventListener('click', () => {
            this.autoRefresh = !this.autoRefresh;
            this.setupAutoRefresh();
            this.updateAutoRefreshUI();
        });
        
        // Export button
        document.getElementById('exportButton')?.addEventListener('click', () => {
            this.exportSignals();
        });
    }
    
    /**
     * Setup auto-refresh
     */
    setupAutoRefresh() {
        // Clear existing timer
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
        
        // Setup new timer if enabled
        if (this.autoRefresh) {
            this.refreshTimer = setInterval(() => {
                this.loadSignalsMatrix();
            }, this.refreshInterval);
        }
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
        
        // Initialize popovers
        const popoverTriggerList = [].slice.call(
            document.querySelectorAll('[data-bs-toggle="popover"]')
        );
        popoverTriggerList.map(popoverTriggerEl => 
            new bootstrap.Popover(popoverTriggerEl)
        );
        
        // Update UI state
        this.updateAutoRefreshUI();
    }
    
    /**
     * Export signals data
     */
    exportSignals() {
        const data = Array.from(this.signals.values());
        const csv = this.convertToCSV(data);
        
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `trading_signals_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
    }
    
    /**
     * Convert data to CSV
     */
    convertToCSV(data) {
        const headers = [
            'Symbol', 'Price', 'Change 24h', 'Volume', 'Signal', 
            'Confidence', 'Risk', 'TP', 'SL', 'Strength Score'
        ];
        
        const rows = data.map(signal => [
            signal.symbol,
            signal.current_price,
            signal.price_change_24h,
            signal.volume_24h,
            signal.aggregated_signal?.action || '',
            Math.round((signal.aggregated_signal?.confidence || 0) * 100) + '%',
            signal.risk_assessment?.level || '',
            signal.aggregated_signal?.take_profit || '',
            signal.aggregated_signal?.stop_loss || '',
            signal.strength_score || ''
        ]);
        
        return [headers, ...rows].map(row => row.join(',')).join('\n');
    }
    
    // Utility methods
    formatPrice(price) {
        if (!price) return '0.00';
        return parseFloat(price).toFixed(2);
    }
    
    formatVolume(volume) {
        if (!volume) return '0';
        if (volume > 1e9) return (volume / 1e9).toFixed(2) + 'B';
        if (volume > 1e6) return (volume / 1e6).toFixed(2) + 'M';
        if (volume > 1e3) return (volume / 1e3).toFixed(2) + 'K';
        return volume.toFixed(0);
    }
    
    getSymbolIcon(symbol) {
        const base = symbol.replace('USDT', '').replace('USD', '');
        return base.substring(0, 3).toUpperCase();
    }
    
    getTrendIcon(trend) {
        const icons = {
            strong_up: '<i class="fas fa-arrow-up"></i>',
            up: '<i class="fas fa-angle-up"></i>',
            neutral: '<i class="fas fa-minus"></i>',
            down: '<i class="fas fa-angle-down"></i>',
            strong_down: '<i class="fas fa-arrow-down"></i>'
        };
        return icons[trend] || icons.neutral;
    }
    
    getEmptyStateHTML() {
        return `
            <tr>
                <td colspan="8" class="text-center py-5">
                    <i class="fas fa-inbox fa-3x text-muted mb-3"></i>
                    <p class="text-muted">Нет сигналов, соответствующих фильтрам</p>
                    <button class="btn btn-primary" onclick="signalsMatrix.clearFilters()">
                        Сбросить фильтры
                    </button>
                </td>
            </tr>
        `;
    }
    
    showLoading(show) {
        const tbody = document.getElementById('signalsTableBody');
        if (show) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center">
                        <div class="loading">
                            <div class="spinner"></div>
                        </div>
                    </td>
                </tr>
            `;
        }
    }
    
    showError(message) {
        const tbody = document.getElementById('signalsTableBody');
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-5">
                    <i class="fas fa-exclamation-triangle fa-3x text-danger mb-3"></i>
                    <p class="text-danger">${message}</p>
                    <button class="btn btn-primary" onclick="signalsMatrix.loadSignalsMatrix()">
                        <i class="fas fa-redo"></i> Повторить попытку
                    </button>
                </td>
            </tr>
        `;
    }
    
    clearFilters() {
        this.filters = {
            strategy: '',
            signal: '',
            risk: '',
            minConfidence: 0,
            search: ''
        };
        
        // Reset UI
        document.getElementById('strategyFilter').value = '';
        document.getElementById('signalFilter').value = '';
        document.getElementById('riskFilter').value = '';
        document.getElementById('confidenceFilter').value = '';
        document.getElementById('searchFilter').value = '';
        
        this.renderView();
    }
}

// Initialize on page load
let signalsMatrix = null;

document.addEventListener('DOMContentLoaded', () => {
    // Initialize WebSocket
    initializeWebSocket({ debug: true });
    
    // Initialize signals matrix manager
    signalsMatrix = new SignalsMatrixManager();
    
    // Make it globally accessible
    window.signalsMatrix = signalsMatrix;
});
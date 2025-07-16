
/**
 * AnalyticsManager - Управляет страницей аналитики.
 * Загружает данные производительности и рендерит сложные графики.
 */
class AnalyticsManager {
    constructor() {
        this.charts = {};
        this.currentDays = 30; // Период по умолчанию
        
        console.log('📈 AnalyticsManager создан');
        this.initialize();
    }

    /**
     * Инициализация
     */
    async initialize() {
        this.initializeCharts();
        this.initializeAdditionalCharts(); 
        this.setupEventHandlers();
        await this.loadAnalyticsData();
        await this.loadDetailedAnalytics(); 
    }
    
    /**
     * Инициализация всех графиков с пустыми данными
     */
    initializeCharts() {
        const commonOptions = (extraOptions = {}) => ({
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#d1d4dc' } } },
            scales: {
                x: { ticks: { color: '#787b86' }, grid: { color: '#363a45' } },
                y: { ticks: { color: '#787b86' }, grid: { color: '#363a45' } }
            },
            ...extraOptions
        });

        // P&L Chart
        const pnlCtx = document.getElementById('pnlChart')?.getContext('2d');
        if(pnlCtx) {
            this.charts.pnl = new Chart(pnlCtx, {
                type: 'line',
                data: { labels: [], datasets: [{ label: 'Накопленная прибыль', data: [], borderColor: '#26a69a', tension: 0.1, fill: true, backgroundColor: 'rgba(38,166,154,0.1)' }] },
                options: commonOptions()
            });
        }
        
        // Strategy Distribution Chart
        const strategyCtx = document.getElementById('strategyDistribution')?.getContext('2d');
        if(strategyCtx) {
            this.charts.strategy = new Chart(strategyCtx, {
                type: 'doughnut',
                data: { labels: [], datasets: [{ data: [], backgroundColor: ['#26a69a', '#ef5350', '#ffb74d', '#2196f3', '#7e57c2'] }] },
                options: commonOptions({ scales: {} })
            });
        }
        
        // ML Accuracy Chart
        const mlAccuracyCtx = document.getElementById('mlAccuracyChart')?.getContext('2d');
        if(mlAccuracyCtx) {
            this.charts.mlAccuracy = new Chart(mlAccuracyCtx, {
                type: 'bar',
                data: { labels: [], datasets: [{ label: 'Точность', data: [], backgroundColor: '#2196f3' }] },
                options: commonOptions()
            });
        }

        // Feature Importance Chart
        const featureImportanceCtx = document.getElementById('featureImportanceChart')?.getContext('2d');
        if(featureImportanceCtx) {
            this.charts.featureImportance = new Chart(featureImportanceCtx, {
                type: 'bar',
                data: { labels: [], datasets: [{ label: 'Важность', data: [], backgroundColor: '#ffb74d' }] },
                options: commonOptions({ indexAxis: 'y' })
            });
        }
    }
    
    initializeAdditionalCharts() {
        // График прибыли по валютам
        const currencyProfitCtx = document.getElementById('currencyProfitChart')?.getContext('2d');
        if (currencyProfitCtx) {
            this.charts.currencyProfit = new Chart(currencyProfitCtx, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Прибыль ($)',
                        data: [],
                        backgroundColor: [],
                        borderColor: [],
                        borderWidth: 1
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
                            ticks: { color: '#787b86' },
                            grid: { color: '#363a45' }
                        },
                        y: {
                            ticks: {
                                color: '#787b86',
                                callback: function(value) {
                                    return '$' + value.toFixed(0);
                                }
                            },
                            grid: { color: '#363a45' }
                        }
                    }
                }
            });
        }
    
        // График количества сделок по валютам
        const currencyTradesCtx = document.getElementById('currencyTradesChart')?.getContext('2d');
        if (currencyTradesCtx) {
            this.charts.currencyTrades = new Chart(currencyTradesCtx, {
                type: 'pie',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: []
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { color: '#d1d4dc' }
                        }
                    }
                }
            });
        }
    
        // График активности по часам
        const hourlyActivityCtx = document.getElementById('hourlyActivityChart')?.getContext('2d');
        if (hourlyActivityCtx) {
            this.charts.hourlyActivity = new Chart(hourlyActivityCtx, {
                type: 'radar',
                data: {
                    labels: Array.from({length: 24}, (_, i) => `${i}:00`),
                    datasets: [{
                        label: 'Сделки',
                        data: Array(24).fill(0),
                        borderColor: '#2196f3',
                        backgroundColor: 'rgba(33, 150, 243, 0.1)'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        r: {
                            ticks: { color: '#787b86' },
                            grid: { color: '#363a45' }
                        }
                    }
                }
            });
        }
    }
    
    async loadDetailedAnalytics() {
        try {
            const response = await fetch('/api/analytics/detailed');
            const data = await response.json();
            
            if (data.success) {
                this.updateCurrencyPerformanceTable(data.currencies);
                this.updateCurrencyCharts(data.currencies);
                this.updateTimeAnalysis(data.time_analysis);
            }
        } catch (error) {
            console.error('Ошибка загрузки детальной аналитики:', error);
        }
    }
    
    updateCurrencyPerformanceTable(currencies) {
        const tbody = document.getElementById('currency-performance-table');
        if (!tbody || !currencies) return;
        
        // Сортируем по прибыли
        const sorted = currencies.sort((a, b) => b.profit - a.profit);
        
        tbody.innerHTML = sorted.map(curr => {
            const profitClass = curr.profit >= 0 ? 'text-success' : 'text-danger';
            const winRate = curr.trades > 0 ? (curr.wins / curr.trades * 100) : 0;
            
            return `
                <tr>
                    <td><strong>${curr.symbol}</strong></td>
                    <td>${curr.trades}</td>
                    <td class="${profitClass}">$${curr.profit.toFixed(2)}</td>
                    <td class="${profitClass}">${curr.avg_profit_percent.toFixed(2)}%</td>
                    <td>${winRate.toFixed(1)}%</td>
                    <td class="text-success">$${(curr.best_trade || 0).toFixed(2)}</td>
                    <td class="text-danger">$${(curr.worst_trade || 0).toFixed(2)}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="analyticsManager.showCurrencyDetails('${curr.symbol}')">
                            <i class="fas fa-chart-line"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }
    
    updateCurrencyCharts(currencies) {
        if (!currencies || currencies.length === 0) return;
        
        // Топ-10 по прибыли для барного графика
        const topByProfit = currencies
            .sort((a, b) => b.profit - a.profit)
            .slice(0, 10);
        
        if (this.charts.currencyProfit) {
            this.charts.currencyProfit.data.labels = topByProfit.map(c => c.symbol.replace('USDT', ''));
            this.charts.currencyProfit.data.datasets[0].data = topByProfit.map(c => c.profit);
            this.charts.currencyProfit.data.datasets[0].backgroundColor = topByProfit.map(c => 
                c.profit >= 0 ? 'rgba(38, 166, 154, 0.6)' : 'rgba(239, 83, 80, 0.6)'
            );
            this.charts.currencyProfit.data.datasets[0].borderColor = topByProfit.map(c => 
                c.profit >= 0 ? 'rgba(38, 166, 154, 1)' : 'rgba(239, 83, 80, 1)'
            );
            this.charts.currencyProfit.update();
        }
        
        // Топ по количеству сделок для pie chart
        const topByTrades = currencies
            .sort((a, b) => b.trades - a.trades)
            .slice(0, 8);
        
        if (this.charts.currencyTrades) {
            this.charts.currencyTrades.data.labels = topByTrades.map(c => c.symbol.replace('USDT', ''));
            this.charts.currencyTrades.data.datasets[0].data = topByTrades.map(c => c.trades);
            this.charts.currencyTrades.data.datasets[0].backgroundColor = [
                '#26a69a', '#ef5350', '#ffb74d', '#2196f3', 
                '#7e57c2', '#66bb6a', '#ff7043', '#29b6f6'
            ];
            this.charts.currencyTrades.update();
        }
    }
    
    showCurrencyDetails(symbol) {
        // Открываем модальное окно с детальной информацией
        // или переходим на страницу с фильтром по валюте
        window.location.href = `/charts?symbol=${symbol}`;
    }
    
    

    /**
     * Настройка обработчиков событий (фильтры, даты)
     */
    setupEventHandlers() {
        document.getElementById('dateRange')?.addEventListener('change', (e) => {
            this.currentDays = parseInt(e.target.value, 10);
            this.loadAnalyticsData();
        });

        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const currentActive = document.querySelector('.filter-btn.active');
                if(currentActive) currentActive.classList.remove('active');
                e.target.classList.add('active');
                this.loadAnalyticsData();
            });
        });
    }

    /**
     * Загрузка данных с бэкенда
     */
    async loadAnalyticsData() {
        this.setLoadingState(true);
        try {
            const response = await fetch(`/api/analytics/performance?days=${this.currentDays}`);
            if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
            
            const data = await response.json();
            if (data.success) {
                // ИСПРАВЛЕНО: Раньше было data.data, что приводило к ошибке, т.к. данные в корне ответа.
                this.updateUI(data);
            } else {
                throw new Error(data.error || 'Не удалось получить данные');
            }
        } catch (error) {
            console.error('Ошибка загрузки аналитики:', error);
            this.showErrorState(error.message);
        } finally {
            this.setLoadingState(false);
        }
    }
    
    /**
     * Обновление всего UI на основе полученных данных
     */
    updateUI(data) {
        if (!data) {
            this.showErrorState('Получены пустые данные от сервера.');
            return;
        }
        this.updateMetrics(data.summary);
        this.updateCharts(data);
        this.updateTables(data);
    }

    /**
     * Обновление карточек с основными метриками
     */
    updateMetrics(summary) {
        const formatCurrency = (value) => (value != null ? (value >= 0 ? '$' : '-$') + Math.abs(value).toFixed(2) : '-');
        
        document.getElementById('totalProfit').textContent = summary ? formatCurrency(summary.total_profit) : '-';
        document.getElementById('winRate').textContent = summary && summary.win_rate != null ? `${(summary.win_rate * 100).toFixed(1)}%` : '-';
        document.getElementById('profitFactor').textContent = summary && summary.profit_factor != null ? summary.profit_factor.toFixed(2) : '-';
        document.getElementById('sharpeRatio').textContent = summary && summary.sharpe_ratio != null ? summary.sharpe_ratio.toFixed(2) : '-';
    }
    
    /**
     * Обновление всех графиков
     */
    updateCharts(data) {
        // P&L
        if (this.charts.pnl && data.daily_pnl) {
            let cumulativeProfit = 0;
            const labels = data.daily_pnl.map(d => new Date(d.date).toLocaleDateString());
            const profits = data.daily_pnl.map(d => {
                cumulativeProfit += d.profit;
                return cumulativeProfit;
            });
            this.charts.pnl.data.labels = labels;
            this.charts.pnl.data.datasets[0].data = profits;
            this.charts.pnl.update();
        }

        // Strategy Distribution
        if (this.charts.strategy && data.strategy_performance) {
            this.charts.strategy.data.labels = data.strategy_performance.map(s => s.strategy);
            this.charts.strategy.data.datasets[0].data = data.strategy_performance.map(s => s.total_profit);
            this.charts.strategy.update();
        }

        // ML Accuracy
        if (this.charts.mlAccuracy && data.ml_metrics?.accuracy) {
            this.charts.mlAccuracy.data.labels = Object.keys(data.ml_metrics.accuracy);
            this.charts.mlAccuracy.data.datasets[0].data = Object.values(data.ml_metrics.accuracy);
            this.charts.mlAccuracy.update();
        }

        // Feature Importance
        if (this.charts.featureImportance && data.ml_metrics?.feature_importance) {
            const sortedFeatures = Object.entries(data.ml_metrics.feature_importance).sort(([,a],[,b]) => a-b);
            this.charts.featureImportance.data.labels = sortedFeatures.map(([key]) => key);
            this.charts.featureImportance.data.datasets[0].data = sortedFeatures.map(([,value]) => value);
            this.charts.featureImportance.update();
        }
    }

    /**
     * Обновление таблиц
     */
    updateTables(data) {
        this.updateStrategyTable(data.strategy_performance);
        this.updateTopPairsTable(data.top_pairs);
        this.updateMLSignalsTable(data.ml_signals);
    }
    
    updateStrategyTable(strategies) {
        const tbody = document.getElementById('strategyTableBody');
        if (!tbody) return;
        if (!strategies || strategies.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center">Нет данных по стратегиям</td></tr>`;
            return;
        }
        tbody.innerHTML = strategies.map(s => `
            <tr>
                <td>${s.strategy || '-'}</td>
                <td>${s.trades != null ? s.trades : '-'}</td>
                <td>${s.win_rate != null ? (s.win_rate * 100).toFixed(1) + '%' : '-'}</td>
                <td class="${s.avg_profit_percent >= 0 ? 'text-success' : 'text-danger'}">${s.avg_profit_percent != null ? s.avg_profit_percent.toFixed(2) + '%' : '-'}</td>
                <td>${s.max_drawdown != null ? s.max_drawdown.toFixed(2) + '%' : '-'}</td>
                <td><span class="ml-score ${this.getMLScoreClass(s.ml_score)}">${s.ml_score != null ? s.ml_score.toFixed(0) : '-'}</span></td>
                <td><span class="badge bg-${s.is_active ? 'success' : 'secondary'}">${s.is_active ? 'Активна' : 'Выключена'}</span></td>
                <td><button class="btn btn-sm btn-outline-primary"><i class="fas fa-chart-line"></i></button></td>
            </tr>
        `).join('');
    }

    updateTopPairsTable(pairs) {
         const tbody = document.getElementById('topPairsBody');
         if (!tbody) return;
         if (!pairs || pairs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center">Нет данных по парам</td></tr>`;
            return;
        }
        tbody.innerHTML = pairs.map(p => `
            <tr>
                <td>${p.pair || '-'}</td>
                <td>${p.trades != null ? p.trades : '-'}</td>
                <td class="text-success">${p.profit != null ? '$' + p.profit.toFixed(2) : '-'}</td>
                <td>${p.win_rate != null ? (p.win_rate * 100).toFixed(1) + '%' : '-'}</td>
            </tr>
        `).join('');
    }
    
    updateMLSignalsTable(signals) {
        const tbody = document.getElementById('mlSignalsBody');
        if (!tbody) return;
        if (!signals || signals.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center">Нет данных по сигналам</td></tr>`;
            return;
        }
        tbody.innerHTML = signals.map(s => {
            const signalClass = s.signal === 'LONG' ? 'text-success' : s.signal === 'SHORT' ? 'text-danger' : '';
            return `
                <tr>
                    <td>${s.time ? new Date(s.time).toLocaleTimeString() : '-'}</td>
                    <td>${s.pair || '-'}</td>
                    <td class="${signalClass}">${s.signal || '-'}</td>
                    <td><span class="ml-score ${this.getMLScoreClass(s.confidence * 100)}">${s.confidence != null ? (s.confidence * 100).toFixed(0) + '%' : '-'}</span></td>
                </tr>`;
        }).join('');
    }
    
    /**
     * Вспомогательные функции
     */
    setLoadingState(isLoading) {
        document.querySelectorAll('.chart-container, .card > .table-responsive').forEach(el => {
            el.style.opacity = isLoading ? '0.5' : '1';
        });
    }
    
    showErrorState(message) {
        const container = document.querySelector('.container-fluid');
        let errorDiv = document.getElementById('analytics-error');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger';
            errorDiv.id = 'analytics-error';
            container.prepend(errorDiv);
        }
        errorDiv.textContent = `Ошибка загрузки аналитики: ${message}`;
    }

    getMLScoreClass(score) {
        if (score == null) return 'low';
        if (score >= 80) return 'high';
        if (score >= 60) return 'medium';
        return 'low';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new AnalyticsManager();
});

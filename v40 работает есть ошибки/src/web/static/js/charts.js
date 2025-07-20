/**
 * ChartsManager - Управляет страницей графиков
 * Файл: src/web/static/js/charts.js
 */
class ChartsManager {
    constructor() {
        this.currentSymbol = 'BTCUSDT';
        this.timeframe = '5m';
        this.indicators = {};
        this.updateInterval = 5000;
        this.tradingViewWidget = null;
        
        console.log('📈 ChartsManager инициализирован');
        this.init();
    }

    async init() {
        try {
            this.setupEventHandlers();
            this.initTradingView();
            await this.loadIndicators();
            this.startAutoUpdate();
        } catch (error) {
            console.error('Ошибка инициализации ChartsManager:', error);
        }
    }

    setupEventHandlers() {
        // Селектор символа
        const symbolSelector = document.getElementById('symbolSelector');
        if (symbolSelector) {
            symbolSelector.addEventListener('change', (e) => {
                this.currentSymbol = e.target.value;
                this.updateMainChart();
                this.loadIndicators();
            });
        }

        // Кнопка обновления
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                await this.refreshAllData();
            });
        }
    }

    initTradingView() {
        // Инициализация TradingView Widget
        const container = document.getElementById('tradingview-widget');
        if (!container) return;

        // Проверяем доступность TradingView
        if (typeof TradingView === 'undefined') {
            console.warn('TradingView library not loaded');
            // Используем fallback на Chart.js
            this.initChartJsFallback();
            return;
        }

        try {
            this.tradingViewWidget = new TradingView.widget({
                width: '100%',
                height: 600,
                symbol: `BYBIT:${this.currentSymbol}`,
                interval: this.timeframe,
                timezone: 'Etc/UTC',
                theme: 'dark',
                style: '1',
                locale: 'ru',
                toolbar_bg: '#f1f3f6',
                enable_publishing: false,
                allow_symbol_change: true,
                container_id: 'tradingview-widget',
                studies: [
                    'RSI@tv-basicstudies',
                    'MACD@tv-basicstudies',
                    'BB@tv-basicstudies'
                ]
            });
        } catch (error) {
            console.error('Ошибка инициализации TradingView:', error);
            this.initChartJsFallback();
        }
    }

    initChartJsFallback() {
        // Fallback на Chart.js если TradingView недоступен
        const container = document.getElementById('tradingview-widget');
        if (!container) return;

        container.innerHTML = '<canvas id="main-chart" style="width: 100%; height: 600px;"></canvas>';
        
        const ctx = document.getElementById('main-chart').getContext('2d');
        this.mainChart = new Chart(ctx, {
            type: 'candlestick',
            data: {
                datasets: [{
                    label: this.currentSymbol,
                    data: []
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });

        // Загружаем данные свечей
        this.loadCandleData();
    }

    async loadCandleData() {
        try {
            const response = await fetch(`/api/charts/candles/${this.currentSymbol}?interval=${this.timeframe}&limit=100`);
            const data = await response.json();

            if (data.success && this.mainChart) {
                const candleData = data.candles.map(candle => ({
                    x: new Date(candle.time),
                    o: candle.open,
                    h: candle.high,
                    l: candle.low,
                    c: candle.close
                }));

                this.mainChart.data.datasets[0].data = candleData;
                this.mainChart.update();
            }
        } catch (error) {
            console.error('Ошибка загрузки данных свечей:', error);
        }
    }

    async loadIndicators() {
        try {
            const response = await fetch(`/api/charts/indicators/${this.currentSymbol}`);
            const data = await response.json();

            if (data.success) {
                this.updateIndicators(data.indicators);
            }
        } catch (error) {
            console.error('Ошибка загрузки индикаторов:', error);
        }
    }

    updateIndicators(indicators) {
        // Обновляем значения индикаторов на странице
        const updates = [
            { id: 'currentPrice', value: indicators.price, format: 'price' },
            { id: 'change24h', value: indicators.change_24h, format: 'percent', colorize: true },
            { id: 'volume24h', value: indicators.volume_24h, format: 'volume' },
            { id: 'rsiValue', value: indicators.rsi, format: 'number' },
            { id: 'macdValue', value: indicators.macd_signal, format: 'signal' }
        ];

        updates.forEach(update => {
            const element = document.getElementById(update.id);
            if (!element) return;

            let displayValue = update.value;
            
            switch (update.format) {
                case 'price':
                    displayValue = `$${parseFloat(displayValue || 0).toFixed(2)}`;
                    break;
                case 'percent':
                    const sign = displayValue >= 0 ? '+' : '';
                    displayValue = `${sign}${parseFloat(displayValue || 0).toFixed(2)}%`;
                    if (update.colorize) {
                        element.className = displayValue >= 0 ? 'text-success' : 'text-danger';
                    }
                    break;
                case 'volume':
                    displayValue = `${(parseFloat(displayValue || 0) / 1000000).toFixed(2)}M`;
                    break;
                case 'number':
                    displayValue = parseFloat(displayValue || 0).toFixed(1);
                    break;
                case 'signal':
                    element.className = displayValue === 'Bullish' ? 'text-success' : 'text-danger';
                    break;
            }

            element.textContent = displayValue || '-';
        });

        // Обновляем индикаторы RSI с цветовой индикацией
        const rsiValue = parseFloat(indicators.rsi || 50);
        const rsiElement = document.getElementById('rsiValue');
        if (rsiElement) {
            if (rsiValue > 70) {
                rsiElement.className = 'indicator-value text-danger';
                rsiElement.title = 'Перекупленность';
            } else if (rsiValue < 30) {
                rsiElement.className = 'indicator-value text-success';
                rsiElement.title = 'Перепроданность';
            } else {
                rsiElement.className = 'indicator-value';
                rsiElement.title = 'Нейтрально';
            }
        }

        // Обновляем время последнего обновления
        const updateTime = document.getElementById('lastUpdate');
        if (updateTime) {
            updateTime.textContent = new Date().toLocaleTimeString();
        }
    }

    updateMainChart() {
        if (this.tradingViewWidget) {
            // TradingView не поддерживает прямое обновление символа
            // Нужно пересоздать виджет
            this.initTradingView();
        } else if (this.mainChart) {
            // Обновляем Chart.js
            this.loadCandleData();
        }
    }

    async refreshAllData() {
        const btn = document.getElementById('refreshBtn');
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Обновление...';
        btn.disabled = true;

        try {
            await Promise.all([
                this.loadIndicators(),
                this.loadCandleData(),
                this.loadRecentTrades()
            ]);
            
            this.showNotification('Данные обновлены', 'success');
        } catch (error) {
            console.error('Ошибка обновления данных:', error);
            this.showNotification('Ошибка обновления данных', 'error');
        } finally {
            btn.innerHTML = originalHtml;
            btn.disabled = false;
        }
    }

    async loadRecentTrades() {
        try {
            const response = await fetch(`/api/dashboard/recent-trades?limit=20`);
            const data = await response.json();

            if (data.success) {
                this.updateTradesTable(data.trades.filter(t => t.symbol === this.currentSymbol));
            }
        } catch (error) {
            console.error('Ошибка загрузки сделок:', error);
        }
    }

    updateTradesTable(trades) {
        const tbody = document.getElementById('tradesTableBody');
        if (!tbody) return;

        if (!trades || trades.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">Нет сделок по выбранной паре</td></tr>';
            return;
        }

        tbody.innerHTML = trades.slice(0, 10).map(trade => {
            const time = new Date(trade.created_at).toLocaleTimeString();
            const sideClass = trade.side === 'BUY' ? 'text-success' : 'text-danger';
            const pnlClass = trade.profit_loss >= 0 ? 'text-success' : 'text-danger';
            const pnlSign = trade.profit_loss >= 0 ? '+' : '';

            return `
                <tr>
                    <td>${time}</td>
                    <td class="${sideClass}">${trade.side}</td>
                    <td>$${trade.price.toFixed(2)}</td>
                    <td class="${pnlClass}">
                        ${pnlSign}${trade.profit_loss_percent?.toFixed(2) || '0.00'}%
                    </td>
                </tr>
            `;
        }).join('');
    }

    startAutoUpdate() {
        // Автообновление каждые 5 секунд
        this.updateTimer = setInterval(() => {
            this.loadIndicators();
        }, this.updateInterval);
    }

    showNotification(message, type = 'info') {
        if (typeof toastr !== 'undefined') {
            toastr[type](message);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }

    destroy() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
        }
    }
}

// Инициализация
let chartsManager;
document.addEventListener('DOMContentLoaded', () => {
    chartsManager = new ChartsManager();
});

// Очистка при выходе
window.addEventListener('beforeunload', () => {
    if (chartsManager) {
        chartsManager.destroy();
    }
});
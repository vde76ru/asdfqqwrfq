/**
 * MultiCurrencyCharts - Класс для управления мультивалютными графиками
 * Файл: src/web/static/js/multi_charts.js
 */

class MultiCurrencyCharts {
    constructor() {
        this.activeSymbols = [];
        this.charts = {};
        this.updateInterval = 5000; // 5 секунд
        this.updateTimer = null;
        
        console.log('📊 MultiCurrencyCharts инициализирован');
    }

    init() {
        // Получаем начальный список символов из конфигурации
        this.loadActiveSymbols();
        this.createChartContainers();
        this.initializeCharts();
        this.startUpdates();
    }

    async loadActiveSymbols() {
        try {
            const response = await fetch('/api/config/pairs');
            const data = await response.json();
            
            if (data.success) {
                // Берем первые 4 основные валюты для начала
                this.activeSymbols = data.pairs
                    .filter(p => p.category === 'primary' && p.active)
                    .slice(0, 4)
                    .map(p => p.symbol);
            }
        } catch (error) {
            console.error('Ошибка загрузки активных символов:', error);
            // Fallback
            this.activeSymbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT'];
        }
    }

    createChartContainers() {
        const container = document.getElementById('multi-charts-container');
        if (!container) return;

        container.innerHTML = '';
        
        this.activeSymbols.forEach(symbol => {
            const chartHtml = `
                <div class="col-lg-6 mb-4" id="container-${symbol}">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="mb-0">${symbol}</h6>
                                <small class="text-muted">
                                    <span id="volume-${symbol}">Vol: -</span>
                                </small>
                            </div>
                            <div class="text-end">
                                <div class="price-info">
                                    <span class="current-price h5 mb-0" id="price-${symbol}">-</span>
                                </div>
                                <div>
                                    <span class="price-change small" id="change-${symbol}">-</span>
                                </div>
                            </div>
                        </div>
                        <div class="card-body p-2">
                            <canvas id="multi-chart-${symbol}" height="300"></canvas>
                        </div>
                        <div class="card-footer p-2">
                            <div class="row text-center small">
                                <div class="col">
                                    <div class="text-muted">24h High</div>
                                    <div id="high-${symbol}">-</div>
                                </div>
                                <div class="col">
                                    <div class="text-muted">24h Low</div>
                                    <div id="low-${symbol}">-</div>
                                </div>
                                <div class="col">
                                    <div class="text-muted">RSI</div>
                                    <div id="rsi-${symbol}">-</div>
                                </div>
                                <div class="col">
                                    <div class="text-muted">MACD</div>
                                    <div id="macd-${symbol}">-</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            container.innerHTML += chartHtml;
        });
    }

    initializeCharts() {
        this.activeSymbols.forEach(symbol => {
            const ctx = document.getElementById(`multi-chart-${symbol}`);
            if (!ctx) return;

            const chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'Price',
                            data: [],
                            borderColor: this.getColorForSymbol(symbol),
                            backgroundColor: this.getColorForSymbol(symbol, 0.1),
                            borderWidth: 2,
                            pointRadius: 0,
                            tension: 0.1,
                            yAxisID: 'y-price'
                        },
                        {
                            label: 'Volume',
                            data: [],
                            type: 'bar',
                            backgroundColor: 'rgba(150, 150, 150, 0.3)',
                            yAxisID: 'y-volume',
                            hidden: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    if (context.dataset.label === 'Price') {
                                        return `Price: $${context.parsed.y.toFixed(2)}`;
                                    } else if (context.dataset.label === 'Volume') {
                                        return `Volume: ${(context.parsed.y / 1000000).toFixed(2)}M`;
                                    }
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            grid: {
                                display: false
                            },
                            ticks: {
                                maxTicksLimit: 8,
                                maxRotation: 0
                            }
                        },
                        'y-price': {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            ticks: {
                                callback: function(value) {
                                    return '$' + value.toFixed(0);
                                }
                            }
                        },
                        'y-volume': {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            grid: {
                                display: false
                            },
                            ticks: {
                                callback: function(value) {
                                    return (value / 1000000).toFixed(0) + 'M';
                                }
                            }
                        }
                    }
                }
            });

            this.charts[symbol] = {
                chart: chart,
                maxDataPoints: 50,
                data: []
            };
        });
    }

    getColorForSymbol(symbol, alpha = 1) {
        const colors = {
            'BTCUSDT': `rgba(247, 147, 26, ${alpha})`,    // Bitcoin Orange
            'ETHUSDT': `rgba(98, 126, 234, ${alpha})`,    // Ethereum Blue
            'BNBUSDT': `rgba(243, 186, 47, ${alpha})`,    // Binance Yellow
            'SOLUSDT': `rgba(133, 94, 255, ${alpha})`,    // Solana Purple
            'ADAUSDT': `rgba(0, 122, 255, ${alpha})`,     // Cardano Blue
            'XRPUSDT': `rgba(0, 170, 144, ${alpha})`,     // XRP Green
            'DOGEUSDT': `rgba(204, 172, 63, ${alpha})`,   // Dogecoin Gold
            'MATICUSDT': `rgba(130, 71, 229, ${alpha})`   // Polygon Purple
        };
        
        return colors[symbol] || `rgba(75, 192, 192, ${alpha})`;
    }

    async updateAllCharts() {
        try {
            const symbolsToFetch = this.activeSymbols;
            if (!symbolsToFetch || symbolsToFetch.length === 0) {
                return; // Нечего обновлять
            }
    
            const symbolsParam = symbolsToFetch.join(',');
            const response = await fetch(`/api/charts/multi/${symbolsParam}`);
    
            if (!response.ok) {
                // Если ответ сервера не 2xx (например, 404, 500)
                throw new Error(`Ошибка сети: ${response.status} ${response.statusText}`);
            }
            
            const result = await response.json();
    
            if (result.success && result.data) {
                // Проходим по всем символам, которые должны быть на странице
                symbolsToFetch.forEach(symbol => {
                    const tickerData = result.data[symbol]; // Получаем данные для конкретного символа
                    
                    // Проверяем, пришли ли данные для этого символа
                    if (tickerData && tickerData.length > 0) {
                        // Данные пришли, берем последнюю свечу
                        const lastCandle = tickerData[tickerData.length - 1];
                        const chartInfo = {
                            price: lastCandle.close,
                            volume: lastCandle.volume,
                            // Если API не возвращает 24h данные, ставим заглушки
                            change_24h: 0, 
                            high_24h: Math.max(...tickerData.map(c => c.high)),
                            low_24h: Math.min(...tickerData.map(c => c.low))
                        };
                        
                        this.updateChart(symbol, tickerData); // Передаем все свечи
                        this.updatePriceDisplay(symbol, chartInfo);
                        this.updateIndicators(symbol, chartInfo);
    
                    } else {
                        // Данных для этого символа нет
                        console.warn(`Данные для символа ${symbol} не получены.`);
                        // Можно показать заглушку на графике
                        const priceEl = document.getElementById(`price-${symbol}`);
                        if (priceEl) priceEl.textContent = 'N/A';
                    }
                });
            } else {
                 // Если success: false
                 throw new Error(result.error || "Не удалось получить данные с сервера.");
            }
        } catch (error) {
            console.error('Ошибка обновления мультивалютных графиков:', error);
            // Можно отобразить сообщение об ошибке для всех графиков
            this.activeSymbols.forEach(symbol => {
                const priceEl = document.getElementById(`price-${symbol}`);
                if (priceEl) priceEl.textContent = 'Error';
            });
        }
    }

    updateChart(symbol, data) {
        const chartData = this.charts[symbol];
        if (!chartData) return;

        const timestamp = new Date().toLocaleTimeString();
        
        // Добавляем новые данные
        chartData.chart.data.labels.push(timestamp);
        chartData.chart.data.datasets[0].data.push(data.price);
        chartData.chart.data.datasets[1].data.push(data.volume);
        
        // Ограничиваем количество точек
        if (chartData.chart.data.labels.length > chartData.maxDataPoints) {
            chartData.chart.data.labels.shift();
            chartData.chart.data.datasets[0].data.shift();
            chartData.chart.data.datasets[1].data.shift();
        }
        
        chartData.chart.update('none');
    }

    updatePriceDisplay(symbol, data) {
        if (!data || data.price === undefined) {
            console.warn(`В updatePriceDisplay нет данных для ${symbol}`);
            return; 
        }
        
        // Безопасный доступ к данным с помощью "||" для установки значений по умолчанию
        const price = data.price || 0;
        const change = data.change_24h || 0;
        const volume = data.volume || 0;
        const high = data.high_24h || 0;
        const low = data.low_24h || 0;
    
        // Обновляем элементы DOM
        const priceEl = document.getElementById(`price-${symbol}`);
        if (priceEl) priceEl.textContent = `$${price.toFixed(2)}`;
        
        const changeEl = document.getElementById(`change-${symbol}`);
        if (changeEl) {
            const changeClass = change >= 0 ? 'text-success' : 'text-danger';
            const changeSign = change >= 0 ? '↑' : '↓';
            changeEl.textContent = `${changeSign} ${Math.abs(change).toFixed(2)}%`;
            changeEl.className = `price-change small ${changeClass}`;
        }
        
        const volumeEl = document.getElementById(`volume-${symbol}`);
        if (volumeEl) {
            const volumeInM = (volume / 1000000).toFixed(2);
            volumeEl.textContent = `Vol: ${volumeInM}M`;
        }
        
        const highEl = document.getElementById(`high-${symbol}`);
        if (highEl) highEl.textContent = `$${high.toFixed(2)}`;
        
        const lowEl = document.getElementById(`low-${symbol}`);
        if (lowEl) lowEl.textContent = `$${low.toFixed(2)}`;
    }


    async updateIndicators(symbol, data) {
        // Здесь можно добавить реальный расчет индикаторов
        // Пока используем демо значения
        const rsi = 50 + Math.random() * 30 - 15;
        const macd = Math.random() > 0.5 ? 'Bullish' : 'Bearish';
        
        document.getElementById(`rsi-${symbol}`).textContent = rsi.toFixed(1);
        
        const macdEl = document.getElementById(`macd-${symbol}`);
        macdEl.textContent = macd;
        macdEl.className = macd === 'Bullish' ? 'text-success' : 'text-danger';
    }

    startUpdates() {
        this.updateAllCharts();
        this.updateTimer = setInterval(() => {
            this.updateAllCharts();
        }, this.updateInterval);
    }

    stopUpdates() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
            this.updateTimer = null;
        }
    }

    setUpdateInterval(interval) {
        this.updateInterval = interval;
        this.stopUpdates();
        this.startUpdates();
    }

    addSymbol(symbol) {
        if (this.activeSymbols.includes(symbol)) return;
        
        this.activeSymbols.push(symbol);
        this.createChartContainers();
        this.initializeCharts();
        this.updateAllCharts();
    }

    removeSymbol(symbol) {
        const index = this.activeSymbols.indexOf(symbol);
        if (index === -1) return;
        
        this.activeSymbols.splice(index, 1);
        delete this.charts[symbol];
        
        // Удаляем контейнер
        const container = document.getElementById(`container-${symbol}`);
        if (container) {
            container.remove();
        }
    }
}

// Глобальная переменная для доступа из HTML
let multiCharts;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('multi-charts-container')) {
        multiCharts = new MultiCurrencyCharts();
        multiCharts.init();
    }
});
/**
 * DashboardManager - Управляет всеми функциями дашборда
 * Файл: src/web/static/js/dashboard.js
 */
class DashboardManager {
    constructor() {
        this.updateInterval = 5000; // 5 секунд
        this.charts = {};
        this.socket = null;
        this.activePairs = [];
        this.isUpdating = false;
        
        console.log('🚀 DashboardManager инициализирован');
        this.init();
    }

    async init() {
        try {
            this.setupWebSocket();
            this.setupEventHandlers();
            this.initCharts();
            await this.loadInitialData();
            this.startAutoUpdate();
        } catch (error) {
            console.error('Ошибка инициализации:', error);
            this.showNotification('Ошибка инициализации дашборда', 'error');
        }
    }

    setupWebSocket() {
        // Подключение к WebSocket для real-time обновлений
        if (typeof io !== 'undefined') {
            try {
                this.socket = io();
                
                this.socket.on('connect', () => {
                    console.log('✅ WebSocket подключен');
                    this.showNotification('Подключено к серверу', 'success');
                });

                this.socket.on('disconnect', () => {
                    console.log('❌ WebSocket отключен');
                    this.showNotification('Соединение потеряно', 'warning');
                });

                this.socket.on('bot_status', (data) => {
                    this.updateBotStatus(data);
                });

                this.socket.on('balance_update', (data) => {
                    this.updateBalance(data);
                });

                this.socket.on('new_trade', (data) => {
                    this.addNewTrade(data);
                    this.showNotification(`Новая сделка: ${data.symbol} ${data.side}`, 'info');
                });

                this.socket.on('position_update', (data) => {
                    this.updatePositions(data);
                });
            } catch (error) {
                console.error('Ошибка инициализации WebSocket:', error);
            }
        }
    }

    setupEventHandlers() {
        // Кнопка запуска бота
        const btnStart = document.getElementById('btn-start');
        if (btnStart) {
            btnStart.addEventListener('click', async () => {
                await this.startBot();
            });
        }

        // Кнопка остановки бота
        const btnStop = document.getElementById('btn-stop');
        if (btnStop) {
            btnStop.addEventListener('click', async () => {
                await this.stopBot();
            });
        }

        // Кнопка обновления позиций
        const btnRefresh = document.querySelector('[onclick="dashboardManager.refreshPositions()"]');
        if (btnRefresh) {
            btnRefresh.onclick = async () => {
                await this.refreshPositions();
            };
        }
    }

    initCharts() {
        // График баланса
        const ctx = document.getElementById('balance-chart')?.getContext('2d');
        if (ctx) {
            this.charts.balance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Баланс USDT',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: false,
                            ticks: {
                                callback: function(value) {
                                    return '$' + value.toFixed(2);
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    async loadInitialData() {
        try {
            console.log('📊 Загрузка начальных данных...');
            
            // Загружаем все данные параллельно
            const [botStatus, balance, positions, statistics, trades] = await Promise.all([
                this.loadBotStatus(),
                this.loadBalance(),
                this.loadPositions(),
                this.loadStatistics(),
                this.loadRecentTrades()
            ]);

            console.log('✅ Начальные данные загружены');
        } catch (error) {
            console.error('Ошибка загрузки начальных данных:', error);
            this.showNotification('Ошибка загрузки данных', 'error');
        }
    }

    async loadBotStatus() {
        try {
            const response = await fetch('/api/bot/status');
            const data = await response.json();

            if (data.success) {
                this.updateBotStatus(data);
                return data;
            }
        } catch (error) {
            console.error('Ошибка загрузки статуса бота:', error);
        }
        return null;
    }

    updateBotStatus(data) {
        // Обновляем индикатор статуса
        const statusIndicator = document.getElementById('bot-status-indicator');
        const statusText = document.getElementById('bot-status-text');
        const btnStart = document.getElementById('btn-start');
        const btnStop = document.getElementById('btn-stop');

        if (data.is_running) {
            statusIndicator.innerHTML = '<i class="fas fa-circle text-success"></i>';
            statusText.textContent = 'Активен';
            btnStart.disabled = true;
            btnStop.disabled = false;
        } else {
            statusIndicator.innerHTML = '<i class="fas fa-circle text-danger"></i>';
            statusText.textContent = 'Остановлен';
            btnStart.disabled = false;
            btnStop.disabled = true;
        }

        // Обновляем системную информацию
        document.getElementById('active-pairs-count').textContent = data.active_pairs?.length || 0;
        document.getElementById('open-positions-count').textContent = data.open_positions_count || 0;
        document.getElementById('cycles-count').textContent = data.cycles_count || 0;

        // Обновляем статус в навбаре
        if (typeof updateNavbarBotStatus === 'function') {
            updateNavbarBotStatus(data.is_running);
        }
    }

    async loadBalance() {
        try {
            const response = await fetch('/api/dashboard/balance');
            const data = await response.json();

            if (data.success) {
                this.updateBalance(data);
                return data;
            }
        } catch (error) {
            console.error('Ошибка загрузки баланса:', error);
        }
        return null;
    }

    updateBalance(data) {
        const balanceTotal = document.getElementById('balance-total');
        const balanceAvailable = document.getElementById('balance-available');

        if (balanceTotal) {
            balanceTotal.textContent = `$${data.total_usdt?.toFixed(2) || '0.00'}`;
        }
        if (balanceAvailable) {
            balanceAvailable.textContent = `$${data.free_usdt?.toFixed(2) || '0.00'}`;
        }

        // Обновляем график баланса
        if (this.charts.balance) {
            const chart = this.charts.balance;
            const now = new Date().toLocaleTimeString();
            
            chart.data.labels.push(now);
            chart.data.datasets[0].data.push(data.total_usdt || 0);
            
            // Ограничиваем количество точек на графике
            if (chart.data.labels.length > 20) {
                chart.data.labels.shift();
                chart.data.datasets[0].data.shift();
            }
            
            chart.update('none');
        }
    }

    async loadPositions() {
        try {
            const response = await fetch('/api/dashboard/positions');
            const data = await response.json();

            if (data.success) {
                this.updatePositions(data.positions);
                return data;
            }
        } catch (error) {
            console.error('Ошибка загрузки позиций:', error);
        }
        return null;
    }

    updatePositions(positions) {
        const tbody = document.getElementById('positions-table');
        if (!tbody) return;

        if (!positions || positions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center">Нет активных позиций</td></tr>';
            return;
        }

        tbody.innerHTML = positions.map(pos => {
            const pnlClass = pos.unrealized_pnl >= 0 ? 'text-success' : 'text-danger';
            const pnlSign = pos.unrealized_pnl >= 0 ? '+' : '';
            const time = new Date(pos.created_at).toLocaleTimeString();

            return `
                <tr>
                    <td>${pos.symbol}</td>
                    <td>
                        <span class="badge bg-${pos.side === 'BUY' ? 'success' : 'danger'}">
                            ${pos.side}
                        </span>
                    </td>
                    <td>${pos.quantity.toFixed(4)}</td>
                    <td>$${pos.entry_price.toFixed(2)}</td>
                    <td>$${pos.current_price?.toFixed(2) || '-'}</td>
                    <td class="${pnlClass}">
                        ${pnlSign}$${Math.abs(pos.unrealized_pnl).toFixed(2)}
                    </td>
                    <td class="${pnlClass}">
                        ${pnlSign}${pos.pnl_percent.toFixed(2)}%
                    </td>
                    <td>${pos.strategy || 'unknown'}</td>
                    <td>${time}</td>
                </tr>
            `;
        }).join('');
    }

    async loadStatistics() {
        try {
            const response = await fetch('/api/dashboard/statistics');
            const data = await response.json();

            if (data.success) {
                this.updateStatistics(data);
                return data;
            }
        } catch (error) {
            console.error('Ошибка загрузки статистики:', error);
        }
        return null;
    }

    updateStatistics(data) {
        // Обновляем метрики
        const metrics = [
            { id: 'metric-profit-today', value: data.today_profit, prefix: '$', isProfit: true },
            { id: 'metric-trades-today', value: data.today_trades },
            { id: 'metric-win-rate', value: data.today_win_rate, suffix: '%' },
            { id: 'metric-total-profit', value: data.total_profit, prefix: '$', isProfit: true }
        ];

        metrics.forEach(metric => {
            const element = document.getElementById(metric.id);
            if (element) {
                let displayValue = metric.value;
                
                if (metric.isProfit) {
                    const sign = displayValue >= 0 ? '+' : '';
                    const colorClass = displayValue >= 0 ? 'text-success' : 'text-danger';
                    element.className = `metric-value ${colorClass}`;
                    displayValue = `${sign}${metric.prefix || ''}${Math.abs(displayValue).toFixed(2)}${metric.suffix || ''}`;
                } else {
                    displayValue = `${metric.prefix || ''}${displayValue}${metric.suffix || ''}`;
                }
                
                element.textContent = displayValue;
            }
        });
    }

    async loadRecentTrades() {
        try {
            const response = await fetch('/api/dashboard/recent-trades?limit=10');
            const data = await response.json();

            if (data.success) {
                this.updateRecentTrades(data.trades);
                return data;
            }
        } catch (error) {
            console.error('Ошибка загрузки последних сделок:', error);
        }
        return null;
    }

    updateRecentTrades(trades) {
        const tbody = document.getElementById('recent-trades-table');
        if (!tbody) return;

        if (!trades || trades.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center">Нет сделок</td></tr>';
            return;
        }

        tbody.innerHTML = trades.map(trade => {
            const time = new Date(trade.created_at).toLocaleTimeString();
            const profitClass = trade.profit_loss >= 0 ? 'text-success' : 'text-danger';
            const profitSign = trade.profit_loss >= 0 ? '+' : '';
            const statusClass = trade.status === 'CLOSED' ? 'secondary' : 'primary';

            return `
                <tr>
                    <td>${time}</td>
                    <td>${trade.symbol}</td>
                    <td>
                        <span class="badge bg-${trade.side === 'BUY' ? 'success' : 'danger'}">
                            ${trade.side}
                        </span>
                    </td>
                    <td>$${trade.price.toFixed(2)}</td>
                    <td>${trade.quantity.toFixed(4)}</td>
                    <td class="${profitClass}">
                        ${profitSign}$${Math.abs(trade.profit_loss).toFixed(2)}
                    </td>
                    <td>
                        <span class="badge bg-${statusClass}">
                            ${trade.status}
                        </span>
                    </td>
                    <td>${trade.strategy}</td>
                </tr>
            `;
        }).join('');
    }

    addNewTrade(trade) {
        // Добавляем новую сделку в начало таблицы
        const tbody = document.getElementById('recent-trades-table');
        if (!tbody) return;

        const firstRow = tbody.querySelector('tr:first-child');
        if (firstRow && firstRow.textContent.includes('Нет сделок')) {
            tbody.innerHTML = '';
        }

        const time = new Date().toLocaleTimeString();
        const profitClass = trade.profit_loss >= 0 ? 'text-success' : 'text-danger';
        const profitSign = trade.profit_loss >= 0 ? '+' : '';
        const statusClass = trade.status === 'CLOSED' ? 'secondary' : 'primary';

        const newRow = `
            <tr class="table-success" style="animation: fadeIn 0.5s">
                <td>${time}</td>
                <td>${trade.symbol}</td>
                <td>
                    <span class="badge bg-${trade.side === 'BUY' ? 'success' : 'danger'}">
                        ${trade.side}
                    </span>
                </td>
                <td>$${trade.price.toFixed(2)}</td>
                <td>${trade.quantity.toFixed(4)}</td>
                <td class="${profitClass}">
                    ${profitSign}$${Math.abs(trade.profit_loss || 0).toFixed(2)}
                </td>
                <td>
                    <span class="badge bg-${statusClass}">
                        ${trade.status}
                    </span>
                </td>
                <td>${trade.strategy}</td>
            </tr>
        `;

        tbody.insertAdjacentHTML('afterbegin', newRow);

        // Удаляем подсветку через 3 секунды
        setTimeout(() => {
            const row = tbody.querySelector('tr:first-child');
            if (row) row.classList.remove('table-success');
        }, 3000);

        // Ограничиваем количество строк
        const rows = tbody.querySelectorAll('tr');
        if (rows.length > 10) {
            rows[rows.length - 1].remove();
        }
    }

    async startBot() {
        const btn = document.getElementById('btn-start');
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Запуск...';
        
        try {
            const response = await fetch('/api/bot/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification('Бот успешно запущен', 'success');
                // Статус обновится через WebSocket
            } else {
                throw new Error(data.message || 'Ошибка запуска');
            }
        } catch (error) {
            this.showNotification(`Ошибка: ${error.message}`, 'error');
        } finally {
            btn.innerHTML = '<i class="fas fa-play"></i> Запустить бота';
            await this.loadBotStatus();
        }
    }

    async stopBot() {
        const btn = document.getElementById('btn-stop');
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Остановка...';
        
        try {
            const response = await fetch('/api/bot/stop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification('Бот остановлен', 'success');
            } else {
                throw new Error(data.message || 'Ошибка остановки');
            }
        } catch (error) {
            this.showNotification(`Ошибка: ${error.message}`, 'error');
        } finally {
            btn.innerHTML = '<i class="fas fa-stop"></i> Остановить бота';
            await this.loadBotStatus();
        }
    }

    showNotification(message, type = 'info') {
        // Используем toastr если доступен
        if (typeof toastr !== 'undefined') {
            toastr[type](message);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
            
            // Fallback: создаем простое уведомление
            const alertClass = {
                'success': 'alert-success',
                'error': 'alert-danger',
                'warning': 'alert-warning',
                'info': 'alert-info'
            }[type] || 'alert-info';
            
            const alert = document.createElement('div');
            alert.className = `alert ${alertClass} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
            alert.style.zIndex = '9999';
            alert.innerHTML = `
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            
            document.body.appendChild(alert);
            
            setTimeout(() => {
                alert.remove();
            }, 5000);
        }
    }

    startAutoUpdate() {
        // Обновляем данные каждые 5 секунд
        this.updateTimer = setInterval(async () => {
            if (!this.isUpdating) {
                this.isUpdating = true;
                try {
                    await Promise.all([
                        this.loadBalance(),
                        this.loadPositions(),
                        this.loadStatistics()
                    ]);
                } catch (error) {
                    console.error('Ошибка автообновления:', error);
                } finally {
                    this.isUpdating = false;
                }
            }
        }, this.updateInterval);
    }

    async refreshPositions() {
        const btn = event.target;
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        btn.disabled = true;
        
        try {
            await this.loadPositions();
            this.showNotification('Позиции обновлены', 'info');
        } catch (error) {
            this.showNotification('Ошибка обновления позиций', 'error');
        } finally {
            btn.innerHTML = originalHtml;
            btn.disabled = false;
        }
    }

    destroy() {
        // Очистка при уничтожении
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
        }
        
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

// Стили для анимации
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
`;
document.head.appendChild(style);

// Инициализация при загрузке страницы
let dashboardManager;
document.addEventListener('DOMContentLoaded', () => {
    dashboardManager = new DashboardManager();
});

// Очистка при выходе
window.addEventListener('beforeunload', () => {
    if (dashboardManager) {
        dashboardManager.destroy();
    }
});
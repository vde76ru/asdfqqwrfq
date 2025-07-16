/**
 * Управление страницей торговых сигналов
 * Файл: src/web/static/js/signals.js
 */

class SignalsManager {
    constructor() {
        this.signals = [];
        this.ws = null;
        this.updateInterval = null;
        this.filters = {
            symbol: '',
            strategy: '',
            hours: 24
        };
        
        this.init();
    }
    
    /**
     * Инициализация менеджера сигналов
     */
    init() {
        this.setupEventListeners();
        this.loadSignals();
        this.setupAutoUpdate();
        this.connectWebSocket();
    }
    
    /**
     * Настройка обработчиков событий
     */
    setupEventListeners() {
        // Фильтры
        document.getElementById('symbolFilter')?.addEventListener('change', (e) => {
            this.filters.symbol = e.target.value;
            this.loadSignals();
        });
        
        document.getElementById('moduleFilter')?.addEventListener('change', (e) => {
            this.filters.strategy = e.target.value;
            this.loadSignals();
        });
        
        document.getElementById('timeFilter')?.addEventListener('change', (e) => {
            this.filters.hours = parseInt(e.target.value);
            this.loadSignals();
        });
        
        // Кнопка обновления
        window.refreshSignals = () => this.loadSignals();
        
        // Закрытие модального окна
        document.querySelector('#detailModal .btn-close')?.addEventListener('click', () => {
            this.hideModal();
        });
        
        // Клик вне модального окна
        document.getElementById('detailModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'detailModal') {
                this.hideModal();
            }
        });
    }
    
    /**
     * Загрузка сигналов с API
     */
    async loadSignals() {
        try {
            const response = await fetch('/api/signals/latest', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.symbols) {
                this.signals = data.symbols;
                this.updateSignalsTable(data.symbols);
                this.updateStats(data);
            }
        } catch (error) {
            console.error('Ошибка загрузки сигналов:', error);
            this.showError('Не удалось загрузить сигналы. Проверьте подключение.');
        }
    }
    
    /**
     * Обновление таблицы сигналов
     */
    updateSignalsTable(signals) {
        const tbody = document.getElementById('signalsBody');
        if (!tbody) {
            // Если нет таблицы, обновляем карточки
            this.updateSignalCards(signals);
            return;
        }
        
        // Очищаем таблицу
        tbody.innerHTML = '';
        
        // Фильтруем сигналы
        const filteredSignals = this.filterSignals(signals);
        
        if (filteredSignals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center">Нет сигналов по выбранным критериям</td></tr>';
            return;
        }
        
        // Создаем строки для каждого сигнала
        filteredSignals.forEach(signal => {
            const row = this.createSignalRow(signal);
            tbody.appendChild(row);
        });
    }
    
    /**
     * Создание строки таблицы для сигнала
     */
    createSignalRow(signal) {
        const tr = document.createElement('tr');
        tr.className = 'signal-row';
        tr.style.cursor = 'pointer';
        
        // Определяем классы для стилизации
        const sentimentClass = signal.sentiment === 'bullish' ? 'text-success' : 'text-danger';
        const signalTypeClass = this.getSignalTypeClass(signal);
        const strengthPercentage = this.calculateStrengthPercentage(signal);
        
        tr.innerHTML = `
            <td>${signal.symbol}</td>
            <td>
                <span class="badge ${signalTypeClass}">
                    ${this.getSignalTypeText(signal)}
                </span>
            </td>
            <td>
                <div class="strength-indicator">
                    <div class="strength-bar">
                        <div class="strength-fill" style="width: ${strengthPercentage}%"></div>
                    </div>
                    <span class="strength-text">${strengthPercentage}%</span>
                </div>
            </td>
            <td>${signal.buySignals || 0}</td>
            <td>${signal.sellSignals || 0}</td>
            <td>${signal.neutralSignals || 0}</td>
            <td>${this.formatStrategies(signal.strategies || [])}</td>
            <td class="${sentimentClass}">
                <i class="fas fa-arrow-${signal.sentiment === 'bullish' ? 'up' : 'down'}"></i>
                ${signal.sentiment}
            </td>
        `;
        
        // Добавляем обработчик клика
        tr.addEventListener('click', () => {
            this.showSignalDetails(signal.symbol);
        });
        
        return tr;
    }
    
    /**
     * Обновление карточек сигналов (альтернативный вид)
     */
    updateSignalCards(signals) {
        const aggregatedContainer = document.getElementById('aggregatedSignals');
        const allSignalsContainer = document.getElementById('allSignals');
        
        if (aggregatedContainer) {
            // Топ сигналы с высокой уверенностью
            const topSignals = signals
                .filter(s => this.calculateStrengthPercentage(s) >= 70)
                .slice(0, 6);
            
            aggregatedContainer.innerHTML = topSignals.map(signal => 
                this.createSignalCard(signal, true)
            ).join('');
        }
        
        if (allSignalsContainer) {
            // Все остальные сигналы
            const filteredSignals = this.filterSignals(signals);
            
            allSignalsContainer.innerHTML = filteredSignals.map(signal => 
                this.createSignalCard(signal, false)
            ).join('');
        }
    }
    
    /**
     * Создание карточки сигнала
     */
    createSignalCard(signal, isAggregated = false) {
        const strengthPercentage = this.calculateStrengthPercentage(signal);
        const signalClass = signal.sentiment === 'bullish' ? 'signal-bullish' : 'signal-bearish';
        const confidenceClass = strengthPercentage >= 80 ? 'confidence-high' : 
                               strengthPercentage >= 50 ? 'confidence-medium' : 'confidence-low';
        
        return `
            <div class="col-md-${isAggregated ? '4' : '3'} mb-3">
                <div class="card signal-card ${signalClass}" onclick="signalsManager.showSignalDetails('${signal.symbol}')">
                    <div class="card-body">
                        <h5 class="card-title">${signal.symbol}</h5>
                        <p class="card-text">
                            <span class="${confidenceClass}">
                                <i class="bi bi-graph-up"></i> ${strengthPercentage}%
                            </span>
                        </p>
                        <div class="signal-stats">
                            <span class="badge bg-success">Buy: ${signal.buySignals || 0}</span>
                            <span class="badge bg-danger">Sell: ${signal.sellSignals || 0}</span>
                        </div>
                        ${isAggregated ? `
                            <div class="mt-2">
                                <small class="text-muted">
                                    ${this.formatStrategies(signal.strategies || [])}
                                </small>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }
    
    /**
     * Показать детальную информацию о сигнале
     */
    async showSignalDetails(symbol) {
        try {
            const response = await fetch(`/api/signals/details/${symbol}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Показываем модальное окно
            this.showModal(data);
            
        } catch (error) {
            console.error('Ошибка загрузки деталей сигнала:', error);
            this.showError('Не удалось загрузить детали сигнала');
        }
    }
    
    /**
     * Показать модальное окно с деталями
     */
    showModal(data) {
        const modal = document.getElementById('detailModal');
        const modalContent = document.getElementById('modalContent');
        
        if (!modal || !modalContent) {
            // Создаем модальное окно, если его нет
            this.createModal();
            return this.showModal(data);
        }
        
        // Заполняем содержимое
        modalContent.innerHTML = this.formatSignalDetails(data);
        
        // Показываем модальное окно
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
        
        // Анимация появления
        setTimeout(() => {
            modal.classList.add('show');
        }, 10);
    }
    
    /**
     * Скрыть модальное окно
     */
    hideModal() {
        const modal = document.getElementById('detailModal');
        if (modal) {
            modal.classList.remove('show');
            setTimeout(() => {
                modal.style.display = 'none';
                document.body.style.overflow = '';
            }, 300);
        }
    }
    
    /**
     * Создание модального окна
     */
    createModal() {
        const modalHtml = `
            <div id="detailModal" class="modal fade" tabindex="-1" style="display: none;">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Детали сигнала</h5>
                            <button type="button" class="btn-close" aria-label="Close"></button>
                        </div>
                        <div class="modal-body" id="modalContent">
                            <!-- Содержимое загружается динамически -->
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Добавляем обработчики
        document.querySelector('#detailModal .btn-close').addEventListener('click', () => {
            this.hideModal();
        });
    }
    
    /**
     * Форматирование деталей сигнала
     */
    formatSignalDetails(data) {
        const aggregated = data.aggregated;
        const rawSignals = data.rawSignals || [];
        const priceHistory = data.priceHistory || [];
        
        let html = `
            <div class="signal-details">
                <h4>${data.symbol}</h4>
        `;
        
        if (aggregated) {
            const confidencePercent = (aggregated.confidenceScore * 100).toFixed(1);
            const signalClass = aggregated.finalSignal.toLowerCase().includes('buy') ? 'success' : 'danger';
            
            html += `
                <div class="aggregated-info mb-4">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="info-card">
                                <h6>Итоговый сигнал</h6>
                                <span class="badge bg-${signalClass} fs-5">
                                    ${aggregated.finalSignal}
                                </span>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="info-card">
                                <h6>Уверенность</h6>
                                <div class="progress" style="height: 25px;">
                                    <div class="progress-bar bg-${this.getConfidenceColor(confidencePercent)}" 
                                         style="width: ${confidencePercent}%">
                                        ${confidencePercent}%
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row mt-3">
                        <div class="col-md-4">
                            <div class="stat-card text-center">
                                <h3 class="text-success">${aggregated.totalBuySignals}</h3>
                                <small>Buy сигналов</small>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="stat-card text-center">
                                <h3 class="text-danger">${aggregated.totalSellSignals}</h3>
                                <small>Sell сигналов</small>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="stat-card text-center">
                                <h3 class="text-secondary">${aggregated.neutralSignals}</h3>
                                <small>Neutral сигналов</small>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // История сигналов
        if (rawSignals.length > 0) {
            html += `
                <div class="raw-signals mt-4">
                    <h6>История сигналов</h6>
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>Время</th>
                                    <th>Тип</th>
                                    <th>Сила</th>
                                    <th>Стратегия</th>
                                </tr>
                            </thead>
                            <tbody>
            `;
            
            rawSignals.slice(0, 10).forEach(signal => {
                const time = new Date(signal.createdAt).toLocaleTimeString();
                const typeClass = signal.signalType === 'buy' ? 'success' : 
                                 signal.signalType === 'sell' ? 'danger' : 'secondary';
                
                html += `
                    <tr>
                        <td>${time}</td>
                        <td><span class="badge bg-${typeClass}">${signal.signalType}</span></td>
                        <td>${(signal.strength * 100).toFixed(1)}%</td>
                        <td>${signal.strategy}</td>
                    </tr>
                `;
            });
            
            html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
        
        return html;
    }
    
    /**
     * Обновление статистики
     */
    updateStats(data) {
        // Обновляем карточки статистики
        this.updateElement('totalSignals', data.totalSignals24h || 0);
        this.updateElement('totalSymbols', data.symbols?.length || 0);
        
        // Подсчитываем сигналы с высокой уверенностью
        const highConfidenceCount = data.symbols?.filter(s => 
            this.calculateStrengthPercentage(s) >= 70
        ).length || 0;
        this.updateElement('highConfidence', highConfidenceCount);
        
        // Активные пары
        this.updateElement('activePairs', data.symbols?.length || 0);
        
        // Лучшая пара
        const bestPair = this.findBestPair(data.symbols);
        this.updateElement('bestPair', bestPair || '-');
        
        // Обновляем статистику по сигналам
        const stats = this.calculateStats(data.symbols);
        this.updateElement('buySignals', stats.totalBuy);
        this.updateElement('sellSignals', stats.totalSell);
        this.updateElement('neutralSignals', stats.totalNeutral);
    }
    
    /**
     * Настройка автоматического обновления
     */
    setupAutoUpdate() {
        // Обновляем каждые 30 секунд
        this.updateInterval = setInterval(() => {
            this.loadSignals();
        }, 30000);
    }
    
    /**
     * Подключение к WebSocket
     */
    connectWebSocket() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket подключен');
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    
                    if (message.type === 'update' || message.type === 'signal_update') {
                        // Немедленное обновление при получении нового сигнала
                        this.loadSignals();
                    }
                } catch (error) {
                    console.error('Ошибка обработки WebSocket сообщения:', error);
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket ошибка:', error);
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket отключен, переподключение через 5 секунд...');
                setTimeout(() => this.connectWebSocket(), 5000);
            };
            
        } catch (error) {
            console.error('Ошибка создания WebSocket:', error);
        }
    }
    
    /**
     * Вспомогательные функции
     */
    
    filterSignals(signals) {
        return signals.filter(signal => {
            // Фильтр по символу
            if (this.filters.symbol && signal.symbol !== this.filters.symbol) {
                return false;
            }
            
            // Фильтр по стратегии
            if (this.filters.strategy && signal.strategies) {
                const hasStrategy = signal.strategies.some(s => 
                    s.toLowerCase().includes(this.filters.strategy.toLowerCase())
                );
                if (!hasStrategy) return false;
            }
            
            return true;
        });
    }
    
    calculateStrengthPercentage(signal) {
        // Рассчитываем силу сигнала на основе соотношения buy/sell
        const total = (signal.buySignals || 0) + (signal.sellSignals || 0) + (signal.neutralSignals || 0);
        if (total === 0) return 0;
        
        const dominant = Math.max(signal.buySignals || 0, signal.sellSignals || 0);
        return Math.round((dominant / total) * 100);
    }
    
    getSignalTypeClass(signal) {
        if (signal.sentiment === 'bullish' || (signal.buySignals > signal.sellSignals)) {
            return 'bg-success';
        } else if (signal.sentiment === 'bearish' || (signal.sellSignals > signal.buySignals)) {
            return 'bg-danger';
        }
        return 'bg-secondary';
    }
    
    getSignalTypeText(signal) {
        if (signal.sentiment === 'bullish' || (signal.buySignals > signal.sellSignals)) {
            return 'BUY';
        } else if (signal.sentiment === 'bearish' || (signal.sellSignals > signal.buySignals)) {
            return 'SELL';
        }
        return 'NEUTRAL';
    }
    
    formatStrategies(strategies) {
        if (!strategies || strategies.length === 0) {
            return '<span class="text-muted">-</span>';
        }
        
        // Сокращаем названия стратегий
        const shortNames = strategies.map(s => {
            if (s.includes('whale') || s.includes('Whale')) return 'Киты';
            if (s.includes('sleep') || s.includes('Sleep')) return 'Спящие';
            if (s.includes('order') || s.includes('Order')) return 'Стакан';
            return s.substring(0, 10) + '...';
        });
        
        return shortNames.join(', ');
    }
    
    getConfidenceColor(percentage) {
        if (percentage >= 80) return 'success';
        if (percentage >= 50) return 'warning';
        return 'danger';
    }
    
    findBestPair(signals) {
        if (!signals || signals.length === 0) return null;
        
        // Находим пару с наибольшей силой сигнала
        let bestPair = signals[0];
        let bestStrength = this.calculateStrengthPercentage(signals[0]);
        
        signals.forEach(signal => {
            const strength = this.calculateStrengthPercentage(signal);
            if (strength > bestStrength) {
                bestStrength = strength;
                bestPair = signal;
            }
        });
        
        return bestPair.symbol;
    }
    
    calculateStats(signals) {
        const stats = {
            totalBuy: 0,
            totalSell: 0,
            totalNeutral: 0
        };
        
        if (signals) {
            signals.forEach(signal => {
                stats.totalBuy += signal.buySignals || 0;
                stats.totalSell += signal.sellSignals || 0;
                stats.totalNeutral += signal.neutralSignals || 0;
            });
        }
        
        return stats;
    }
    
    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }
    
    showError(message) {
        console.error(message);
        // Можно добавить визуальное отображение ошибки
        const alertHtml = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        const container = document.querySelector('.container-fluid');
        if (container) {
            container.insertAdjacentHTML('afterbegin', alertHtml);
        }
    }
    
    /**
     * Очистка ресурсов
     */
    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Создаем экземпляр менеджера при загрузке страницы
let signalsManager;

document.addEventListener('DOMContentLoaded', () => {
    signalsManager = new SignalsManager();
});

// Экспортируем для использования в других скриптах
window.signalsManager = signalsManager;

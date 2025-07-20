
/**
 * SettingsManager - Управляет страницей настроек.
 * Загружает и сохраняет различные конфигурации системы.
 * /src/web/static/js/settings.js


 */
class SettingsManager {
    constructor() {
        console.log('⚙️ SettingsManager создан');
        this.initialize();
    }

    initialize() {
        this.setupEventListeners();
        this.loadAllSettings();
    }

    setupEventListeners() {
        document.getElementById('general-settings-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveForm('general-settings-form', '/api/settings/general', 'Основные настройки сохранены');
        });

        document.getElementById('risk-settings-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveForm('risk-settings-form', '/api/settings/risk', 'Настройки риска сохранены');
        });

        document.getElementById('add-pair-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.addTradingPair();
        });
        
        document.getElementById('test-telegram')?.addEventListener('click', () => this.testTelegram());

        // Event delegation for dynamic buttons
        const pairsTableBody = document.querySelector('#trading-pairs-table tbody');
        pairsTableBody?.addEventListener('click', (e) => {
            const deleteButton = e.target.closest('.delete-pair');
            if (deleteButton) {
                 this.deleteTradingPair(deleteButton.dataset.id);
            }
        });

        pairsTableBody?.addEventListener('change', (e) => {
             const toggleSwitch = e.target.closest('.form-check-input');
             if(toggleSwitch) {
                this.togglePairActive(toggleSwitch.dataset.id, e.target.checked);
             }
        });
        
        this.setupCurrencyHandlers();
    }

    async loadAllSettings() {
        try {
            await this.loadMainSettings();
            await this.loadTradingPairs();
            await this.loadCurrencyConfiguration(); // Добавьте эту строку
            await this.checkApiStatus();
        } catch (error) {
            this.showAlert('danger', 'Не удалось загрузить все настройки.');
            console.error("Ошибка загрузки настроек:", error);
        }
    }

    async loadMainSettings() {
        try {
            const response = await fetch('/api/settings');
            const data = await response.json();
            if (data.success) {
                this.populateForms(data.settings);
            }
        } catch (error) {
            console.error('Ошибка загрузки основных настроек:', error);
        }
    }
    
    populateForms(settings) {
        for (const key in settings) {
            const element = document.getElementById(key);
            if (element) {
                element.value = settings[key];
            }
        }
    }
    
    async loadTradingPairs() {
        try {
            const response = await fetch('/api/trading-pairs');
            const data = await response.json();
            const tbody = document.querySelector('#trading-pairs-table tbody');
            if (!tbody) return;

            if (data.success && data.pairs.length > 0) {
                tbody.innerHTML = data.pairs.map(pair => `
                    <tr>
                        <td>${pair.symbol}</td>
                        <td>
                             <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" role="switch" 
                                       id="pair-toggle-${pair.id}" data-id="${pair.id}" ${pair.is_active ? 'checked' : ''}>
                            </div>
                        </td>
                        <td>${pair.strategy}</td>
                        <td>${pair.stop_loss_percent}%</td>
                        <td>${pair.take_profit_percent}%</td>
                        <td>
                            <button class="btn btn-sm btn-danger delete-pair" data-id="${pair.id}">
                                <i class="fas fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center">Торговые пары не добавлены</td></tr>';
            }
        } catch (error) {
             console.error('Ошибка загрузки торговых пар:', error);
             const tbody = document.querySelector('#trading-pairs-table tbody');
             if(tbody) tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Ошибка загрузки</td></tr>';
        }
    }

    async checkApiStatus() {
         try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            const bybitStatus = document.getElementById('bybit-status');
            if (data.exchange?.connected) {
                bybitStatus.className = 'badge bg-success';
                bybitStatus.textContent = 'Подключено';
            } else {
                 bybitStatus.className = 'badge bg-danger';
                 bybitStatus.textContent = 'Отключено';
            }
            document.getElementById('bybit-mode').textContent = data.config?.mode || 'N/A';

         } catch (error) {
             console.error('Ошибка проверки статуса API:', error);
         }
    }

    async saveForm(formId, url, successMessage) {
        const form = document.getElementById(formId);
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await response.json();
            if (result.success) {
                this.showAlert('success', successMessage);
            } else {
                throw new Error(result.error || 'Неизвестная ошибка');
            }
        } catch (error) {
            this.showAlert('danger', `Ошибка сохранения: ${error.message}`);
        }
    }

    async addTradingPair() {
        const symbolInput = document.getElementById('pair-symbol');
        const strategyInput = document.getElementById('pair-strategy');
        const symbol = symbolInput.value.toUpperCase();
        const strategy = strategyInput.value;

        if (!symbol) {
            this.showAlert('warning', 'Необходимо указать символ пары.');
            return;
        }

        try {
            const response = await fetch('/api/trading-pairs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, strategy, is_active: true }),
            });
            const result = await response.json();
            if (result.success) {
                this.showAlert('success', 'Торговая пара добавлена.');
                this.loadTradingPairs();
                const modal = bootstrap.Modal.getInstance(document.getElementById('addPairModal'));
                if (modal) modal.hide();
                symbolInput.value = '';
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            this.showAlert('danger', `Ошибка добавления пары: ${error.message}`);
        }
    }

    async deleteTradingPair(pairId) {
        if (!confirm('Вы уверены, что хотите удалить эту торговую пару?')) return;

        try {
            const response = await fetch(`/api/trading-pairs/${pairId}`, { method: 'DELETE' });
            if (!response.ok) throw new Error('Failed to delete');
            this.showAlert('success', 'Торговая пара удалена.');
            this.loadTradingPairs();
        } catch (error) {
            this.showAlert('danger', 'Ошибка удаления пары.');
        }
    }
    
    async togglePairActive(pairId, isActive) {
        try {
            const response = await fetch(`/api/trading-pairs/${pairId}/toggle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: isActive }),
            });
            if (!response.ok) throw new Error('Failed to toggle');
             this.showAlert('success', `Статус пары обновлен.`);
        } catch (error) {
            this.showAlert('danger', 'Ошибка обновления статуса пары.');
            this.loadTradingPairs(); // Revert UI on failure
        }
    }

    async testTelegram() {
        try {
            const response = await fetch('/api/test/telegram', { method: 'POST' });
            if (!response.ok) throw new Error('Failed to send');
            this.showAlert('success', 'Тестовое сообщение отправлено в Telegram.');
        } catch (error) {
            this.showAlert('danger', 'Ошибка отправки тестового сообщения.');
        }
    }

    showAlert(type, message) {
        const container = document.getElementById('settings-alerts');
        if (!container) return;
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        container.innerHTML = alertHtml;
    }
    
    async loadCurrencyConfiguration() {
        try {
            const response = await fetch('/api/config/pairs');
            const data = await response.json();
            
            if (data.success) {
                this.renderCurrencyCategories(data.pairs);
            }
        } catch (error) {
            console.error('Ошибка загрузки конфигурации валют:', error);
        }
    }
    
    renderCurrencyCategories(pairs) {
        const container = document.getElementById('currency-categories');
        if (!container) return;
        
        const categories = {
            primary: { name: 'Основные', pairs: [] },
            secondary: { name: 'Вторичные', pairs: [] },
            additional: { name: 'Дополнительные', pairs: [] },
            volatile: { name: 'Волатильные', pairs: [] }
        };
        
        // Группируем пары по категориям
        pairs.forEach(pair => {
            if (categories[pair.category]) {
                categories[pair.category].pairs.push(pair);
            }
        });
        
        // Рендерим категории
        container.innerHTML = Object.entries(categories).map(([key, category]) => `
            <div class="col-md-3 mb-3">
                <h6>${category.name} (${category.pairs.length})</h6>
                <div class="list-group list-group-flush" style="max-height: 300px; overflow-y: auto;">
                    ${category.pairs.map(pair => `
                        <div class="list-group-item d-flex justify-content-between align-items-center p-2">
                            <span>${pair.symbol}</span>
                            <button class="btn btn-sm btn-outline-danger" 
                                    onclick="settingsManager.removeCurrency('${pair.symbol}')">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    }
    
    setupCurrencyHandlers() {
        document.getElementById('add-currency-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const symbol = document.getElementById('new-currency-symbol').value.toUpperCase();
            const category = document.getElementById('new-currency-category').value;
            
            await this.addCurrency(symbol, category);
        });
    }
    
    async addCurrency(symbol, category) {
        try {
            const response = await fetch('/api/config/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: 'trading_pairs',
                    action: 'add',
                    symbol: symbol,
                    category: category
                })
            });
            
            const result = await response.json();
            if (result.success) {
                this.showAlert('success', `Валюта ${symbol} добавлена`);
                await this.loadCurrencyConfiguration();
                document.getElementById('new-currency-symbol').value = '';
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            this.showAlert('danger', `Ошибка добавления валюты: ${error.message}`);
        }
    }
    
    async removeCurrency(symbol) {
        if (!confirm(`Удалить ${symbol} из списка торговых пар?`)) return;
        
        try {
            const response = await fetch('/api/config/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: 'trading_pairs',
                    action: 'remove',
                    symbol: symbol
                })
            });
            
            const result = await response.json();
            if (result.success) {
                this.showAlert('success', `Валюта ${symbol} удалена`);
                await this.loadCurrencyConfiguration();
            }
        } catch (error) {
            this.showAlert('danger', `Ошибка удаления валюты: ${error.message}`);
        }
    }
    
    async enableAllPairs() {
        try {
            const response = await fetch('/api/config/bulk-update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'enable_all'
                })
            });
            
            if (response.ok) {
                this.showAlert('success', 'Все пары включены');
                await this.loadTradingPairs();
            }
        } catch (error) {
            this.showAlert('danger', 'Ошибка при включении пар');
        }
    }
    
    async disableAllPairs() {
        if (!confirm('Вы уверены? Это отключит торговлю по всем парам!')) return;
        
        try {
            const response = await fetch('/api/config/bulk-update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'disable_all'
                })
            });
            
            if (response.ok) {
                this.showAlert('warning', 'Все пары отключены');
                await this.loadTradingPairs();
            }
        } catch (error) {
            this.showAlert('danger', 'Ошибка при отключении пар');
        }
    }
    
    async resetToDefault() {
        if (!confirm('Сбросить конфигурацию к настройкам по умолчанию?')) return;
        
        try {
            const response = await fetch('/api/config/reset', {
                method: 'POST'
            });
            
            if (response.ok) {
                this.showAlert('info', 'Конфигурация сброшена');
                await this.loadAllSettings();
            }
        } catch (error) {
            this.showAlert('danger', 'Ошибка сброса конфигурации');
        }
    }
    
    async exportConfig() {
        try {
            const response = await fetch('/api/config/export');
            const config = await response.json();
            
            // Создаем файл для скачивания
            const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `crypto-bot-config-${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            window.URL.revokeObjectURL(url);
            
            this.showAlert('success', 'Конфигурация экспортирована');
        } catch (error) {
            this.showAlert('danger', 'Ошибка экспорта конфигурации');
        }
    }
    
    async importConfig() {
        const fileInput = document.getElementById('config-file');
        const file = fileInput.files[0];
        
        if (!file) {
            this.showAlert('warning', 'Выберите файл конфигурации');
            return;
        }
        
        try {
            const text = await file.text();
            const config = JSON.parse(text);
            
            const response = await fetch('/api/config/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            if (response.ok) {
                this.showAlert('success', 'Конфигурация импортирована');
                await this.loadAllSettings();
            } else {
                throw new Error('Ошибка импорта');
            }
        } catch (error) {
            this.showAlert('danger', 'Ошибка импорта конфигурации: неверный формат файла');
        }
    }

}

let settingsManager;
document.addEventListener('DOMContentLoaded', () => {
    settingsManager = new SettingsManager();
});

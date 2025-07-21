/**
 * NewsManager - Управляет страницей новостей и социальных сигналов
 * Файл: src/web/static/js/news.js
 */
class NewsManager {
    constructor() {
        this.newsContainer = document.getElementById('news-container');
        this.socialContainer = document.getElementById('social-container');
        this.newsLoading = document.getElementById('news-loading');
        this.socialLoading = document.getElementById('social-loading');
        this.refreshInterval = 60000; // 1 минута
        this.socket = null;

        console.log('📰 NewsManager инициализирован');
        this.initialize();
    }

    async initialize() {
        try {
            await this.loadInitialData();
            this.initWebSocket();
            this.startAutoRefresh();
        } catch (error) {
            console.error('Ошибка инициализации NewsManager:', error);
        }
    }

    initWebSocket() {
        if (typeof io === 'undefined') return;
        
        try {
            this.socket = io();
            
            this.socket.on('connect', () => {
                console.log('🔌 WebSocket на странице новостей подключен');
            });
            
            this.socket.on('news_update', (data) => {
                this.prependNewsItem(data.data);
            });
            
            this.socket.on('social_signal', (data) => {
                this.prependSocialItem(data.data);
            });
        } catch (error) {
            console.error('Ошибка инициализации WebSocket:', error);
        }
    }

    async loadInitialData() {
        this.setLoading(true);
        
        try {
            const [newsResponse, socialResponse] = await Promise.all([
                fetch('/api/news/latest'),
                fetch('/api/social/signals')
            ]);
            
            const newsData = await newsResponse.json();
            const socialData = await socialResponse.json();
            
            if (newsData.success) {
                this.renderNews(newsData.news || []);
            } else {
                this.showError('news', 'Не удалось загрузить новости');
            }
            
            if (socialData.success) {
                this.renderSocialSignals(socialData.signals || []);
            } else {
                this.showError('social', 'Не удалось загрузить социальные сигналы');
            }

        } catch (error) {
            console.error('Ошибка загрузки начальных данных:', error);
            this.showError('news', 'Ошибка загрузки новостей');
            this.showError('social', 'Ошибка загрузки сигналов');
        } finally {
            this.setLoading(false);
        }
    }

    setLoading(isLoading) {
        if (isLoading) {
            this.newsLoading.style.display = 'block';
            this.socialLoading.style.display = 'block';
            this.newsContainer.style.display = 'none';
            this.socialContainer.style.display = 'none';
        } else {
            this.newsLoading.style.display = 'none';
            this.socialLoading.style.display = 'none';
            this.newsContainer.style.display = 'block';
            this.socialContainer.style.display = 'block';
        }
    }

    showError(type, message) {
        const container = type === 'news' ? this.newsContainer : this.socialContainer;
        container.innerHTML = `<div class="alert alert-danger">${message}</div>`;
    }

    renderNews(newsItems) {
        if (!newsItems || newsItems.length === 0) {
            this.newsContainer.innerHTML = '<div class="text-center text-muted p-5">Нет доступных новостей</div>';
            return;
        }
        
        this.newsContainer.innerHTML = newsItems.map(item => this.createNewsItemHtml(item)).join('');
    }

    renderSocialSignals(signals) {
        if (!signals || signals.length === 0) {
            this.socialContainer.innerHTML = '<div class="text-center text-muted p-5">Нет доступных социальных сигналов</div>';
            return;
        }
        
        this.socialContainer.innerHTML = signals.map(signal => this.createSocialItemHtml(signal)).join('');
    }

    createNewsItemHtml(item) {
        const sentimentClass = this.getSentimentClass(item.sentiment);
        const impactBadge = this.getImpactBadge(item.impact);
        const timeAgo = this.getTimeAgo(item.published_at);
        const coinsHtml = item.coins ? item.coins.map(coin => 
            `<span class="badge bg-primary me-1">${coin}</span>`
        ).join('') : '';

        return `
            <div class="news-item mb-3 p-3 border rounded">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">
                            <a href="${item.url}" target="_blank" class="text-decoration-none">
                                ${item.title}
                            </a>
                        </h6>
                        <div class="text-muted small mb-2">
                            <i class="fas fa-clock"></i> ${timeAgo} • 
                            <i class="fas fa-globe"></i> ${item.source}
                        </div>
                        <p class="mb-2 small">${item.content}</p>
                        <div class="d-flex align-items-center">
                            ${coinsHtml}
                            ${impactBadge}
                            <span class="ms-auto ${sentimentClass}">
                                Sentiment: ${(item.sentiment * 100).toFixed(0)}%
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    createSocialItemHtml(signal) {
        const sentimentClass = this.getSentimentClass(signal.sentiment);
        const confidenceBadge = this.getConfidenceBadge(signal.confidence);
        const timeAgo = this.getTimeAgo(signal.timestamp);
        const platformIcon = this.getPlatformIcon(signal.source);
        const coinsHtml = signal.coins ? signal.coins.map(coin => 
            `<span class="badge bg-info me-1">$${coin}</span>`
        ).join('') : '';

        return `
            <div class="social-item mb-3 p-3 border rounded">
                <div class="d-flex align-items-start">
                    <div class="me-3 text-muted">
                        <i class="${platformIcon} fa-2x"></i>
                    </div>
                    <div class="flex-grow-1">
                        <div class="d-flex justify-content-between">
                            <h6 class="mb-1">${signal.author}</h6>
                            <small class="text-muted">${timeAgo}</small>
                        </div>
                        <p class="mb-2 small">${signal.content}</p>
                        <div class="d-flex align-items-center">
                            ${coinsHtml}
                            ${confidenceBadge}
                            <span class="ms-2 ${sentimentClass}">
                                Sentiment: ${(signal.sentiment * 100).toFixed(0)}%
                            </span>
                            <span class="ms-auto text-muted small">
                                <i class="fas fa-heart"></i> ${signal.engagement || 0}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    prependNewsItem(item) {
        const html = this.createNewsItemHtml(item);
        this.newsContainer.insertAdjacentHTML('afterbegin', html);
        
        // Анимация появления
        const newItem = this.newsContainer.firstElementChild;
        newItem.style.opacity = '0';
        newItem.style.transform = 'translateY(-20px)';
        requestAnimationFrame(() => {
            newItem.style.transition = 'all 0.3s ease';
            newItem.style.opacity = '1';
            newItem.style.transform = 'translateY(0)';
        });
        
        // Ограничиваем количество элементов
        const items = this.newsContainer.querySelectorAll('.news-item');
        if (items.length > 20) {
            items[items.length - 1].remove();
        }
    }

    prependSocialItem(signal) {
        const html = this.createSocialItemHtml(signal);
        this.socialContainer.insertAdjacentHTML('afterbegin', html);
        
        // Анимация появления
        const newItem = this.socialContainer.firstElementChild;
        newItem.style.opacity = '0';
        newItem.style.transform = 'translateY(-20px)';
        requestAnimationFrame(() => {
            newItem.style.transition = 'all 0.3s ease';
            newItem.style.opacity = '1';
            newItem.style.transform = 'translateY(0)';
        });
        
        // Ограничиваем количество элементов
        const items = this.socialContainer.querySelectorAll('.social-item');
        if (items.length > 20) {
            items[items.length - 1].remove();
        }
    }

    getSentimentClass(sentiment) {
        if (sentiment >= 0.7) return 'text-success';
        if (sentiment <= 0.3) return 'text-danger';
        return 'text-warning';
    }

    getImpactBadge(impact) {
        const impactColors = {
            'high': 'danger',
            'medium': 'warning',
            'low': 'secondary'
        };
        const color = impactColors[impact] || 'secondary';
        return `<span class="badge bg-${color} ms-2">Impact: ${impact}</span>`;
    }

    getConfidenceBadge(confidence) {
        const level = confidence >= 0.8 ? 'High' : confidence >= 0.5 ? 'Medium' : 'Low';
        const color = confidence >= 0.8 ? 'success' : confidence >= 0.5 ? 'warning' : 'secondary';
        return `<span class="badge bg-${color}">Confidence: ${level}</span>`;
    }

    getPlatformIcon(platform) {
        const icons = {
            'Twitter': 'fab fa-twitter',
            'Reddit': 'fab fa-reddit',
            'Telegram': 'fab fa-telegram',
            'Discord': 'fab fa-discord',
            'YouTube': 'fab fa-youtube'
        };
        return icons[platform] || 'fas fa-globe';
    }

    getTimeAgo(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);
        
        if (seconds < 60) return 'только что';
        if (seconds < 3600) return `${Math.floor(seconds / 60)} мин. назад`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)} ч. назад`;
        return `${Math.floor(seconds / 86400)} д. назад`;
    }

    startAutoRefresh() {
        setInterval(() => {
            this.loadInitialData();
        }, this.refreshInterval);
    }

    destroy() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

// Инициализация
let newsManager;
document.addEventListener('DOMContentLoaded', () => {
    newsManager = new NewsManager();
});

// Очистка при выходе
window.addEventListener('beforeunload', () => {
    if (newsManager) {
        newsManager.destroy();
    }
});
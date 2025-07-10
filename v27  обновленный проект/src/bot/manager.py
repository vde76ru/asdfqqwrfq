#!/usr/bin/env python3
"""
НОВЫЙ ГЛАВНЫЙ ФАЙЛ BOTMANAGER - Дирижер оркестра
Файл: src/bot/manager.py

🎯 ПРИНЦИП РАБОТЫ:
- Этот файл - ТОЛЬКО интерфейс и делегирование
- Вся логика вынесена в internal/ модули
- Полная обратная совместимость с существующим кодом
- Никаких изменений импортов в других частях проекта

📁 СТРУКТУРА:
manager.py (этот файл) - дирижер
├── internal/
│   ├── __init__.py           # Инициализация модулей
│   ├── types.py             # Типы данных и Enums
│   ├── initialization.py    # Инициализация компонентов
│   ├── lifecycle.py         # Жизненный цикл бота
│   ├── trading_pairs.py     # Работа с торговыми парами
│   ├── trading_loops.py     # Торговые циклы
│   ├── market_analysis.py   # Анализ рынка
│   ├── trade_execution.py   # Исполнение сделок
│   ├── position_management.py # Управление позициями
│   ├── monitoring.py        # Мониторинг и здоровье
│   ├── utilities.py         # Утилиты и статус
│   └── compatibility.py     # Совместимость
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# Импорт всех внутренних модулей
from .internal.types import (
    BotStatus, ComponentStatus, MarketPhase, RiskLevel, TradeDecision,
    TradingOpportunity, MarketState, ComponentInfo, PerformanceMetrics, TradingStatistics
)

from .internal.initialization import get_initialization
from .internal.lifecycle import get_lifecycle
from .internal.trading_pairs import get_trading_pairs
from .internal.trading_loops import get_trading_loops
from .internal.market_analysis import get_market_analysis
from .internal.trade_execution import get_trade_execution
from .internal.position_management import get_position_management
from .internal.monitoring import get_monitoring
from .internal.utilities import get_utilities
from .internal.compatibility import get_compatibility

# Конфигурация
from ..core.unified_config import unified_config as config

logger = logging.getLogger(__name__)

class BotManager:
    """
    🤖 ГЛАВНЫЙ МЕНЕДЖЕР ТОРГОВОГО БОТА - ДИРИЖЕР ОРКЕСТРА
    
    Этот класс НЕ содержит бизнес-логику!
    Он только делегирует вызовы в соответствующие внутренние модули.
    
    Вся реальная логика находится в src/bot/internal/ модулях.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Паттерн Singleton"""
        if cls._instance is None:
            cls._instance = super(BotManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Инициализация менеджера бота - только создание делегатов"""
        if BotManager._initialized:
            return
            
        BotManager._initialized = True
        logger.info("🚀 Инициализация ГЛАВНОГО BotManager (дирижер оркестра)...")
        
        # === ОСНОВНЫЕ АТРИБУТЫ (минимальные для совместимости) ===
        self.status = BotStatus.STOPPED
        self.start_time = None
        self.stop_time = None
        self.pause_time = None
        self.is_running = False
        
        # Торговые пары и позиции
        self.all_trading_pairs = []
        self.active_pairs = []
        self.inactive_pairs = []
        self.blacklisted_pairs = set()
        self.watchlist_pairs = []
        self.trending_pairs = []
        self.high_volume_pairs = []
        self.positions = {}
        self.pending_orders = {}
        
        # Счетчики
        self.cycles_count = 0
        self.trades_today = 0
        self.daily_profit = 0.0
        self.weekly_profit = 0.0
        self.monthly_profit = 0.0
        
        # Компоненты системы
        self.components = {}
        self.tasks = {}
        self.task_health = {}
        
        # Exchange и другие ключевые компоненты
        self.exchange_client = None
        self.enhanced_exchange_client = None
        self.exchange = None
        self.market_analyzer = None
        self.trader = None
        self.risk_manager = None
        self.portfolio_manager = None
        self.notifier = None
        self.data_collector = None
        self.strategy_factory = None
        
        # Стратегии
        self.available_strategies = config.ENABLED_STRATEGIES if hasattr(config, 'ENABLED_STRATEGIES') else {}
        self.strategy_instances = {}
        self.strategy_performance = {}
        
        # Баланс и торговля
        self.balance = 0.0
        self.available_balance = 0.0
        self.locked_balance = 0.0
        
        # Кэширование данных
        self.market_data_cache = {}
        self.price_history = {}
        self.volume_history = {}
        self.indicator_cache = {}
        self.candle_cache = {}
        
        # ML и анализ
        self.ml_models = {}
        self.ml_predictions = {}
        self.feature_cache = {}
        self.news_cache = []
        self.social_signals = []
        
        # Конфигурация
        self.config = config
        self.trading_pairs = config.get_active_trading_pairs() if hasattr(config, 'get_active_trading_pairs') else []
        
        # Создаем делегатов для всех внутренних модулей
        self._initialization = get_initialization(self)
        self._lifecycle = get_lifecycle(self)
        self._trading_pairs = get_trading_pairs(self)
        self._trading_loops = get_trading_loops(self)
        self._market_analysis = get_market_analysis(self)
        self._trade_execution = get_trade_execution(self)
        self._position_management = get_position_management(self)
        self._monitoring = get_monitoring(self)
        self._utilities = get_utilities(self)
        self._compatibility = get_compatibility(self)
        
        # Дополнительные атрибуты для совместимости
        self.datetime = datetime  # Для совместимости с compatibility.py
        self.BotStatus = BotStatus  # Для совместимости
        
        logger.info("✅ BotManager (дирижер) инициализирован успешно")
    
    # =================================================================
    # ИНИЦИАЛИЗАЦИЯ - делегирование в initialization.py
    # =================================================================
    
    async def initialize(self):
        """Инициализация с улучшенной обработкой ошибок"""
        return await self._initialization.initialize()
    
    async def _initialize_all_components(self):
        """Инициализация всех компонентов системы"""
        return await self._initialization._initialize_all_components()
    
    async def _init_database(self):
        """Инициализация подключения к базе данных"""
        return await self._initialization._init_database()
    
    async def _init_config_validator(self):
        """Инициализация валидатора конфигурации"""
        return await self._initialization._init_config_validator()
    
    async def _init_exchange_client(self):
        """Инициализация exchange клиента"""
        return await self._initialization._init_exchange_client()
    
    async def _init_data_collector(self):
        """Инициализация сборщика данных"""
        return await self._initialization._init_data_collector()
    
    async def _init_market_analyzer(self):
        """Инициализация анализатора рынка"""
        return await self._initialization._init_market_analyzer()
    
    async def _init_risk_manager(self):
        """Инициализация менеджера рисков"""
        return await self._initialization._init_risk_manager()
    
    async def _init_portfolio_manager(self):
        """Инициализация менеджера портфеля"""
        return await self._initialization._init_portfolio_manager()
    
    async def _init_strategy_factory(self):
        """Инициализация фабрики стратегий"""
        return await self._initialization._init_strategy_factory()
    
    async def _init_trader(self):
        """Инициализация исполнителя сделок"""
        return await self._initialization._init_trader()
    
    async def _init_execution_engine(self):
        """Инициализация движка исполнения ордеров"""
        return await self._initialization._init_execution_engine()
    
    async def _init_notifier(self):
        """Инициализация системы уведомлений"""
        return await self._initialization._init_notifier()
    
    async def _init_ml_system(self):
        """Инициализация системы машинного обучения"""
        return await self._initialization._init_ml_system()
    
    async def _init_news_analyzer(self):
        """Инициализация анализатора новостей"""
        return await self._initialization._init_news_analyzer()
    
    async def _init_websocket_manager(self):
        """Инициализация менеджера WebSocket"""
        return await self._initialization._init_websocket_manager()
    
    async def _init_export_manager(self):
        """Инициализация менеджера экспорта"""
        return await self._initialization._init_export_manager()
    
    async def _init_health_monitor(self):
        """Инициализация монитора здоровья"""
        return await self._initialization._init_health_monitor()
    
    async def initialize_enhanced_exchange(self):
        """Инициализация enhanced exchange клиента"""
        return await self._initialization.initialize_enhanced_exchange()
    
    async def _display_account_info(self):
        """Отображение информации об аккаунте и балансе"""
        return await self._initialization._display_account_info()
    
    async def _process_balance_info(self, balance_info: dict):
        """Обработка и отображение информации о балансе"""
        return await self._initialization._process_balance_info(balance_info)
    
    # =================================================================
    # ЖИЗНЕННЫЙ ЦИКЛ - делегирование в lifecycle.py
    # =================================================================
    
    async def start_async(self):
        """Асинхронный запуск торгового бота"""
        return await self._lifecycle.start_async()
    
    async def pause(self):
        """Приостановка торгового бота"""
        return await self._lifecycle.pause()
    
    async def resume(self):
        """Возобновление работы торгового бота"""
        return await self._lifecycle.resume()
    
    async def emergency_stop(self):
        """Экстренная остановка с закрытием всех позиций"""
        return await self._lifecycle.emergency_stop()
    
    async def _start_all_trading_loops(self):
        """Запуск всех торговых циклов"""
        return await self._lifecycle._start_all_trading_loops()
    
    # =================================================================
    # ТОРГОВЫЕ ПАРЫ - делегирование в trading_pairs.py
    # =================================================================
    
    async def _discover_all_trading_pairs(self):
        """Автоматическое обнаружение всех торговых пар"""
        return await self._trading_pairs._discover_all_trading_pairs()
    
    async def _load_historical_data_for_pairs(self):
        """Загрузка исторических данных для активных торговых пар"""
        return await self._trading_pairs._load_historical_data_for_pairs()
    
    def _load_pairs_from_config(self):
        """Загрузка торговых пар из конфигурации"""
        return self._trading_pairs._load_pairs_from_config()
    
    async def update_pairs(self, pairs: List[str]) -> None:
        """Обновление торговых пар (для совместимости)"""
        return await self._trading_pairs.update_pairs(pairs)
    
    # =================================================================
    # ТОРГОВЫЕ ЦИКЛЫ - делегирование в trading_loops.py
    # =================================================================
    
    async def _main_trading_loop(self):
        """Главный торговый цикл"""
        return await self._trading_loops._main_trading_loop()
    
    async def _market_monitoring_loop(self):
        """Цикл мониторинга рынка"""
        return await self._trading_loops._market_monitoring_loop()
    
    async def _pair_discovery_loop(self):
        """Цикл обновления торговых пар"""
        return await self._trading_loops._pair_discovery_loop()
    
    async def _position_management_loop(self):
        """Цикл управления позициями"""
        return await self._trading_loops._position_management_loop()
    
    async def _risk_monitoring_loop(self):
        """Цикл мониторинга рисков"""
        return await self._trading_loops._risk_monitoring_loop()
    
    async def _health_monitoring_loop(self):
        """Цикл мониторинга здоровья"""
        return await self._trading_loops._health_monitoring_loop()
    
    async def _performance_monitoring_loop(self):
        """Цикл мониторинга производительности"""
        return await self._trading_loops._performance_monitoring_loop()
    
    async def _data_export_loop(self):
        """Цикл экспорта данных"""
        return await self._trading_loops._data_export_loop()
    
    async def _ml_training_loop(self):
        """Цикл обучения ML моделей"""
        return await self._trading_loops._ml_training_loop()
    
    async def _ml_prediction_loop(self):
        """Цикл ML предсказаний"""
        return await self._trading_loops._ml_prediction_loop()
    
    async def _news_collection_loop(self):
        """Цикл сбора новостей"""
        return await self._trading_loops._news_collection_loop()
    
    async def _sentiment_analysis_loop(self):
        """Цикл анализа настроений"""
        return await self._trading_loops._sentiment_analysis_loop()
    
    async def _event_processing_loop(self):
        """Цикл обработки событий"""
        return await self._trading_loops._event_processing_loop()
    
    # =================================================================
    # АНАЛИЗ РЫНКА - делегирование в market_analysis.py
    # =================================================================
    
    async def _update_market_data(self):
        """Обновление рыночных данных для всех торговых пар"""
        return await self._market_analysis._update_market_data()
    
    async def _update_market_data_for_symbol(self, symbol: str):
        """Обновление данных для одного символа"""
        return await self._market_analysis._update_market_data_for_symbol(symbol)
    
    async def _find_all_trading_opportunities(self):
        """Поиск торговых возможностей по всем парам и стратегиям"""
        return await self._market_analysis._find_all_trading_opportunities()
    
    async def _analyze_with_ml(self, symbol: str, df):
        """Анализ с использованием ML моделей"""
        return await self._market_analysis._analyze_with_ml(symbol, df)
    
    def _prepare_market_data(self, symbol: str):
        """Подготовка рыночных данных для анализа"""
        return self._market_analysis._prepare_market_data(symbol)
    
    # =================================================================
    # ИСПОЛНЕНИЕ СДЕЛОК - делегирование в trade_execution.py
    # =================================================================
    
    async def _execute_best_trades(self, opportunities):
        """Исполнение лучших торговых возможностей"""
        return await self._trade_execution._execute_best_trades(opportunities)
    
    async def _execute_trade(self, opportunity: Dict[str, Any]) -> bool:
        """Единый метод для выполнения сделки"""
        return await self._trade_execution._execute_trade(opportunity)
    
    async def _simulate_trade(self, symbol: str, signal: str, position_size: float,
                             price: float, trade_data: Dict[str, Any]) -> bool:
        """Симуляция торговой операции для режима Paper Trading"""
        return await self._trade_execution._simulate_trade(symbol, signal, position_size, price, trade_data)
    
    def _calculate_position_size(self, symbol: str, price: float) -> float:
        """Рассчитывает размер позиции на основе риск-менеджмента"""
        return self._trade_execution._calculate_position_size(symbol, price)
    
    # =================================================================
    # УПРАВЛЕНИЕ ПОЗИЦИЯМИ - делегирование в position_management.py
    # =================================================================
    
    async def _manage_all_positions(self):
        """Управление всеми открытыми позициями"""
        return await self._position_management._manage_all_positions()
    
    async def _initialize_strategies(self):
        """Инициализация стратегий"""
        return await self._position_management._initialize_strategies()
    
    # =================================================================
    # МОНИТОРИНГ - делегирование в monitoring.py
    # =================================================================
    
    async def _perform_health_check(self):
        """Проверка здоровья всей системы"""
        return await self._monitoring._perform_health_check()
    
    async def get_market_data_enhanced(self, symbol: str):
        """Получение рыночных данных через enhanced API"""
        return await self._monitoring.get_market_data_enhanced(symbol)
    
    async def get_account_balance_enhanced(self):
        """Получение баланса через enhanced API"""
        return await self._monitoring.get_account_balance_enhanced()
    
    async def monitor_enhanced_health(self):
        """Мониторинг состояния enhanced системы"""
        return await self._monitoring.monitor_enhanced_health()
    
    # =================================================================
    # УТИЛИТЫ - делегирование в utilities.py
    # =================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса бота"""
        return self._utilities.get_status()
    
    def get_full_status(self) -> Dict[str, Any]:
        """Возвращает полный статус бота, безопасный для JSON-сериализации"""
        return self._utilities.get_full_status()
    
    def _sanitize_for_json(self, data: Any) -> Any:
        """Рекурсивно преобразует данные для безопасной JSON-сериализации"""
        return self._utilities._sanitize_for_json(data)
    
    def _sanitize_value(self, value):
        """Преобразует сложные типы в простые для JSON"""
        return self._utilities._sanitize_value(value)
    
    def emit_status_update(self):
        """Отправка обновления статуса через WebSocket"""
        return self._utilities.emit_status_update()
    
    def get_balance_info(self) -> Dict[str, Any]:
        """Получение информации о балансе"""
        return self._utilities.get_balance_info()
    
    def get_positions_info(self) -> Dict[str, Any]:
        """Получение информации о позициях"""
        return self._utilities.get_positions_info()
    
    # =================================================================
    # СОВМЕСТИМОСТЬ - делегирование в compatibility.py
    # =================================================================
    
    def start(self) -> Tuple[bool, str]:
        """Синхронная обертка для запуска бота"""
        return self._compatibility.start()
    
    def stop(self) -> Tuple[bool, str]:
        """Синхронная обертка для остановки бота"""
        return self._compatibility.stop()
    
    def __repr__(self) -> str:
        """Строковое представление для отладки"""
        return self._compatibility.__repr__()
    
    def set_socketio(self, socketio_instance):
        """Установка SocketIO для WebSocket коммуникаций"""
        return self._compatibility.set_socketio(socketio_instance)
    
    # =================================================================
    # ПРЯМЫЕ АТРИБУТЫ (для совместимости с существующим кодом)
    # =================================================================
    
    @property
    def lifecycle(self):
        """Доступ к модулю lifecycle"""
        return self._lifecycle
    
    @property
    def position_manager(self):
        """Прямой доступ к position_manager для совместимости"""
        # Если есть реальный position_manager в компонентах, возвращаем его
        if hasattr(self, '_real_position_manager'):
            return self._real_position_manager
        # Иначе создаем заглушку для совместимости
        return None

# =========================================================================
# === СОЗДАНИЕ ГЛОБАЛЬНОГО ЭКЗЕМПЛЯРА ===
# =========================================================================

# Создаем единственный экземпляр менеджера бота (Singleton)
bot_manager = BotManager()

# Экспорт для полной совместимости
__all__ = [
    'BotManager', 
    'bot_manager',
    # Экспортируем типы для внешнего использования
    'BotStatus', 
    'ComponentStatus', 
    'MarketPhase', 
    'RiskLevel', 
    'TradeDecision',
    'TradingOpportunity', 
    'MarketState', 
    'ComponentInfo', 
    'PerformanceMetrics', 
    'TradingStatistics'
]

# Дополнительная проверка для отладки
if __name__ == "__main__":
    # Этот блок выполняется только при прямом запуске файла
    print("🤖 НОВЫЙ BotManager (дирижер) загружен успешно")
    print(f"📊 Manager instance: {bot_manager}")
    print(f"🔧 Configuration loaded: {hasattr(config, 'BYBIT_API_KEY') if config else 'No config'}")
    print("🎼 Все внутренние модули подключены как оркестр!")
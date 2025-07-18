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
│   ├── types.py              # Типы данных и Enums
│   ├── initialization.py     # Инициализация компонентов
│   ├── lifecycle.py          # Жизненный цикл бота
│   ├── trading_pairs.py      # Работа с торговыми парами
│   ├── trading_loops.py      # Торговые циклы
│   ├── market_analysis.py    # Анализ рынка
│   ├── trade_execution.py    # Исполнение сделок
│   ├── position_management.py # Управление позициями
│   ├── monitoring.py         # Мониторинг и здоровье
│   ├── utilities.py          # Утилиты и статус
│   └── compatibility.py      # Совместимость
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# =================================================================
# 🎯 ИСПРАВЛЕНИЕ: Оставляем только те импорты, которые не создают цикл.
# Остальные будут импортированы внутри метода __init__.
# =================================================================
from .internal.types import (
    BotStatus, ComponentStatus, MarketPhase, RiskLevel, TradeDecision,
    TradingOpportunity, MarketState, ComponentInfo, PerformanceMetrics, TradingStatistics
)
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
        self.paper_balance = None
        self.paper_positions = {}
        self.paper_trades_history = []
        self.paper_stats = {}
        
        # Кэширование данных
        self.market_data_cache = {}
        self.price_history = {}
        self.volume_history = {}
        self.indicator_cache = {}
        self.candle_cache = {}
        
        # События и синхронизация
        self._stop_event = None
        self._pause_event = None
        
        # Конфигурация
        self.config = config
        self.bot_config = config
        self.testnet = getattr(config, 'USE_TESTNET', False)
        self._exchange_initialized = False
        
        self.signals_matrix_cache = {}
        self.matrix_cache_ttl = 30 # секунды
        self.last_matrix_update = None
        
        from ..risk.risk_calculator import RiskCalculator
        self.risk_calculator = RiskCalculator()
        
        # Инициализация компонентов для сигналов
        logger.info("🔧 Инициализация компонентов системы сигналов...")
        self._init_signal_components()
        
        # =================================================================
        # 🎯 ИСПРАВЛЕНИЕ: Импортируем внутренние модули здесь, внутри __init__,
        # чтобы разорвать циклическую зависимость.
        # =================================================================
        logger.info("🎼 Создание делегатов для внутренних модулей (отложенный импорт)...")
        
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

        # === СОЗДАНИЕ ДЕЛЕГАТОВ ===
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
        
        logger.info("✅ BotManager успешно инициализирован как дирижер")
    
    def _init_signal_components(self):
        """Инициализация компонентов системы сигналов"""
        try:
            logger.info("Инициализация компонентов системы сигналов...")
            
            # Инициализация продюсеров данных
            from ..api_clients.onchain_data_producer import OnchainDataProducer
            self.onchain_producer = OnchainDataProducer()
            
            from ..api_clients.bybit_data_producer import BybitDataProducer
            self.bybit_producer = BybitDataProducer(testnet=self.testnet)
    
            # Инициализация стратегий анализа
            from ..strategies.whale_hunting import WhaleHuntingStrategy
            self.whale_hunting_strategy = WhaleHuntingStrategy()
            
            from ..strategies.sleeping_giants import SleepingGiantsStrategy
            self.sleeping_giants_strategy = SleepingGiantsStrategy()
            
            from ..strategies.order_book_analysis import OrderBookAnalysisStrategy
            self.order_book_analysis = OrderBookAnalysisStrategy()
            
            from ..strategies.signal_aggregator import SignalAggregator
            self.signal_aggregator = SignalAggregator()
            
            # Инициализация NotificationManager
            if hasattr(config, "TELEGRAM_BOT_TOKEN") and hasattr(config, "TELEGRAM_CHAT_ID"):
                from ..notifications import NotificationManager
                from ..core.database import SessionLocal
                notification_config = {
                    'telegram_token': getattr(config, 'TELEGRAM_BOT_TOKEN', None),
                    'telegram_chat_id': getattr(config, 'TELEGRAM_CHAT_ID', None),
                    'min_signal_strength': 0.7,
                    'cooldown_minutes': 60,
                    'check_interval': 60
                }
                self.notification_manager = NotificationManager()
                
                logger.info("Notification Manager инициализирован")
            else:
                self.notification_manager = None
                logger.warning("NotificationManager не инициализирован: отсутствуют настройки Telegram.")
    
        except Exception as e:
            logger.error(f"Критическая ошибка при инициализации компонентов сигналов: {e}", exc_info=True)
            
            
    def get_signals_matrix_data(self) -> Optional[List[Dict]]:
        """Получение данных матрицы сигналов из кэша"""
        logger.debug(f"Запрос матрицы сигналов. Кэш: {len(self.signals_matrix_cache)} элементов")
        
        if not self.signals_matrix_cache:
            logger.warning("Матрица сигналов пуста!")
            # ✅ ИЗМЕНЕНО: Возвращаем пустой список вместо None
            return []
            
        # Проверяем актуальность кэша
        if self.last_matrix_update:
            cache_age = (datetime.utcnow() - self.last_matrix_update).seconds
            if cache_age > self.matrix_cache_ttl:
                logger.warning(f"Кэш матрицы устарел: {cache_age}с > {self.matrix_cache_ttl}с")
                # ✅ ИЗМЕНЕНО: Возвращаем устаревшие данные с пометкой
                data = list(self.signals_matrix_cache.values())
                for item in data:
                    item['cache_expired'] = True
                return data
                
        return list(self.signals_matrix_cache.values())
    
    def get_symbol_details(self, symbol: str) -> Optional[Dict]:
        """Получение детальной информации по символу"""
        if symbol not in self.signals_matrix_cache:
            return None
            
        # Добавляем дополнительные данные
        details = self.signals_matrix_cache[symbol].copy()
        
        # Получаем данные из whale_transactions
        from ..core.database import SessionLocal  # ✅ ДОБАВЛЕНО: импорт SessionLocal
        from datetime import timedelta  # ✅ ДОБАВЛЕНО: импорт timedelta
        
        db = SessionLocal()
        try:
            from ..core.models import WhaleTransaction, OrderBookSnapshot
            
            # Последние транзакции китов
            whale_txs = db.query(WhaleTransaction).filter(
                WhaleTransaction.symbol == symbol,
                WhaleTransaction.timestamp > datetime.utcnow() - timedelta(hours=24)
            ).order_by(WhaleTransaction.timestamp.desc()).limit(10).all()
            
            details['whale_transactions'] = [
                {
                    'type': tx.transaction_type.value,
                    'amount': float(tx.amount),
                    'usd_value': float(tx.usd_value),
                    'from_address': tx.from_address[:8] + '...',
                    'to_address': tx.to_address[:8] + '...',
                    'timestamp': tx.timestamp.isoformat()
                }
                for tx in whale_txs
            ]
            
            # Последний снимок стакана
            orderbook = db.query(OrderBookSnapshot).filter(
                OrderBookSnapshot.symbol == symbol
            ).order_by(OrderBookSnapshot.timestamp.desc()).first()
            
            if orderbook:
                details['orderbook'] = {
                    'bids': orderbook.bids[:10],
                    'asks': orderbook.asks[:10],
                    'spread': float(orderbook.spread) if orderbook.spread else None,
                    'imbalance': float(orderbook.imbalance) if orderbook.imbalance else None,
                    'ofi': float(orderbook.ofi) if orderbook.ofi else None
                }
                
        finally:
            db.close()
            
        return details
    
    async def update_signals_matrix(self):
        """Обновление матрицы сигналов для всех пар"""
        logger.info("🔄 Обновление матрицы сигналов...")
        
        # ✅ ДОБАВЛЕНО: Проверка активных пар
        if not self.active_pairs:
            logger.warning("❌ Нет активных торговых пар для анализа!")
            return
        
        logger.info(f"📊 Анализ {len(self.active_pairs)} пар: {self.active_pairs}")
        
        matrix_data = {}
        
        for symbol in self.active_pairs:
            try:
                logger.debug(f"🔍 Анализ пары {symbol}...")
                
                # Собираем сигналы от всех стратегий
                strategies_data = []
                
                # Whale Hunting
                if self.whale_hunting_strategy:
                    try:
                        signal = await self.whale_hunting_strategy.analyze(symbol)
                        if signal:
                            strategies_data.append({
                                'name': 'whale_hunting',
                                'status': getattr(signal, 'action', 'NEUTRAL'),
                                'confidence': getattr(signal, 'confidence', 0),
                                'price_target': getattr(signal, 'take_profit', None),
                                'reason': getattr(signal, 'reason', '')
                            })
                            logger.debug(f"✅ Whale hunting сигнал для {symbol}: {getattr(signal, 'action', 'NEUTRAL')}")
                    except Exception as e:
                        logger.debug(f"Ошибка в whale_hunting для {symbol}: {e}")
                
                # Sleeping Giants
                if self.sleeping_giants_strategy:
                    try:
                        signal = await self.sleeping_giants_strategy.analyze(symbol)
                        if signal:
                            strategies_data.append({
                                'name': 'sleeping_giants',
                                'status': getattr(signal, 'action', 'NEUTRAL'),
                                'confidence': getattr(signal, 'confidence', 0),
                                'price_target': getattr(signal, 'take_profit', None),
                                'reason': getattr(signal, 'reason', '')
                            })
                    except Exception as e:
                        logger.debug(f"Ошибка в sleeping_giants для {symbol}: {e}")
                
                # Order Book Analysis
                if self.order_book_analysis:
                    try:
                        signal = await self.order_book_analysis.analyze(symbol)
                        if signal:
                            strategies_data.append({
                                'name': 'order_book_analysis',
                                'status': getattr(signal, 'action', 'NEUTRAL'),
                                'confidence': getattr(signal, 'confidence', 0),
                                'price_target': getattr(signal, 'take_profit', None),
                                'reason': getattr(signal, 'reason', '')
                            })
                    except Exception as e:
                        logger.debug(f"Ошибка в order_book_analysis для {symbol}: {e}")
                
                # Multi Indicator
                if hasattr(self, '_market_analysis'):
                    try:
                        signal = await self._market_analysis.analyze_multi_indicator(symbol)
                        if signal:
                            strategies_data.append({
                                'name': 'multi_indicator',
                                'status': getattr(signal, 'action', 'NEUTRAL'),
                                'confidence': getattr(signal, 'confidence', 0),
                                'price_target': getattr(signal, 'take_profit', None),
                                'reason': getattr(signal, 'reason', '')
                            })
                    except Exception as e:
                        logger.debug(f"Ошибка в multi_indicator для {symbol}: {e}")
                
                # ✅ ДОБАВЛЕНО: Если нет сигналов от стратегий, создаем базовый
                if not strategies_data:
                    strategies_data.append({
                        'name': 'default',
                        'status': 'NEUTRAL',
                        'confidence': 0.5,
                        'price_target': None,
                        'reason': 'Недостаточно данных для анализа'
                    })
                
                # Получаем текущую цену
                current_price = 0
                if self.exchange_client:
                    try:
                        ticker = await self.exchange_client.fetch_ticker(symbol)
                        current_price = ticker.get('last', 0)
                    except Exception as e:
                        logger.error(f"Ошибка получения цены для {symbol}: {e}")
                
                # Расчет рисков
                risk_assessment = {'level': 'MEDIUM', 'score': 0.5, 'details': 'Стандартный риск'}
                if hasattr(self, 'risk_calculator') and self.risk_calculator:
                    try:
                        risk_assessment = self.risk_calculator.assess_symbol_risk(symbol, strategies_data)
                    except Exception as e:
                        logger.debug(f"Ошибка оценки риска для {symbol}: {e}")
                
                # Агрегированный сигнал
                aggregated = {'action': 'NEUTRAL', 'confidence': 0.5}
                if self.signal_aggregator and hasattr(self.signal_aggregator, 'aggregate_signals_sync'):
                    try:
                        aggregated = self.signal_aggregator.aggregate_signals_sync(symbol, strategies_data)
                    except Exception as e:
                        logger.debug(f"Ошибка агрегации сигналов для {symbol}: {e}")
                
                matrix_data[symbol] = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'last_update': datetime.utcnow().isoformat(),
                    'risk_assessment': risk_assessment,
                    'strategies': strategies_data,
                    'aggregated_signal': aggregated
                }
                
                logger.debug(f"✅ Данные для {symbol} добавлены в матрицу")
                
            except Exception as e:
                logger.error(f"Ошибка обновления матрицы для {symbol}: {e}")
                # ✅ ДОБАВЛЕНО: Создаем базовую запись даже при ошибке
                matrix_data[symbol] = {
                    'symbol': symbol,
                    'current_price': 0,
                    'last_update': datetime.utcnow().isoformat(),
                    'risk_assessment': {'level': 'UNKNOWN', 'score': 0, 'details': 'Ошибка анализа'},
                    'strategies': [],
                    'aggregated_signal': {'action': 'NEUTRAL', 'confidence': 0}
                }
                
        self.signals_matrix_cache = matrix_data
        self.last_matrix_update = datetime.utcnow()
        logger.info(f"✅ Матрица сигналов обновлена для {len(matrix_data)} пар")
    
    # =================================================================
    # ИНИЦИАЛИЗАЦИЯ - делегирование в initialization.py
    # =================================================================
    
    async def initialize_all_components(self) -> bool:
        """Инициализация всех компонентов системы"""
        return await self._initialization.initialize_all_components()
    
    async def init_exchange_client(self):
        """Инициализация клиента биржи"""
        return await self._initialization.init_exchange_client()
    
    async def initialize_enhanced_exchange(self):
        """Инициализация расширенного exchange клиента"""
        return await self._initialization.initialize_enhanced_exchange()
    
    async def init_market_analyzer(self):
        """Инициализация анализатора рынка"""
        return await self._initialization.init_market_analyzer()
    
    async def init_trader(self):
        """Инициализация трейдера"""
        return await self._initialization.init_trader()
    
    async def init_risk_manager(self):
        """Инициализация менеджера рисков"""
        return await self._initialization.init_risk_manager()
    
    async def init_portfolio_manager(self):
        """Инициализация портфельного менеджера"""
        return await self._initialization.init_portfolio_manager()
    
    async def init_notifier(self):
        """Инициализация уведомлений"""
        return await self._initialization.init_notifier()
    
    async def init_data_collector(self):
        """Инициализация сборщика данных"""
        return await self._initialization.init_data_collector()
    
    async def init_strategy_factory(self):
        """Инициализация фабрики стратегий"""
        return await self._initialization.init_strategy_factory()
    
    async def display_account_info(self):
        """Отображение информации об аккаунте"""
        return await self._initialization.display_account_info()
    
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
        """Цикл обнаружения новых торговых пар"""
        return await self._trading_loops._pair_discovery_loop()
    
    async def _position_management_loop(self):
        """Цикл управления позициями"""
        return await self._trading_loops._position_management_loop()
    
    async def _risk_monitoring_loop(self):
        """Цикл мониторинга рисков"""
        return await self._trading_loops._risk_monitoring_loop()
    
    async def _health_monitoring_loop(self):
        """Цикл мониторинга здоровья системы"""
        return await self._trading_loops._health_monitoring_loop()
    
    async def _performance_tracking_loop(self):
        """Цикл отслеживания производительности"""
        return await self._trading_loops._performance_tracking_loop()
    
    async def _cleanup_loop(self):
        """Цикл очистки устаревших данных"""
        return await self._trading_loops._cleanup_loop()
    
    async def _balance_monitoring_loop(self):
        """Цикл мониторинга баланса"""
        return await self._trading_loops._balance_monitoring_loop()
    
    async def _strategy_evaluation_loop(self):
        """Цикл оценки стратегий"""
        return await self._trading_loops._strategy_evaluation_loop()
    
    async def _data_collection_loop(self):
        """Цикл сбора данных"""
        return await self._trading_loops._data_collection_loop()
    
    async def _sentiment_analysis_loop(self):
        """Цикл анализа настроений"""
        return await self._trading_loops._sentiment_analysis_loop()
    
    async def _event_processing_loop(self):
        """Цикл обработки событий"""
        return await self._trading_loops._event_processing_loop()
    
    async def start_signal_system_loops(self):
        """Запуск циклов системы сигналов"""
        return await self._trading_loops.start_signal_system_loops()
    
    # =================================================================
    # АНАЛИЗ РЫНКА - делегирование в market_analysis.py
    # =================================================================
    
    async def _analyze_market_conditions(self):
        """Анализ текущих рыночных условий"""
        return await self._market_analysis._analyze_market_conditions()
    
    async def _analyze_single_pair(self, symbol: str) -> Optional[MarketState]:
        """Анализ одной торговой пары"""
        return await self._market_analysis._analyze_single_pair(symbol)
    
    async def _detect_market_phase(self, symbol: str, klines: List[Dict]) -> MarketPhase:
        """Определение фазы рынка"""
        return await self._market_analysis._detect_market_phase(symbol, klines)
    
    async def _calculate_volatility_metrics(self, symbol: str, klines: List[Dict]) -> Dict[str, float]:
        """Расчет метрик волатильности"""
        return await self._market_analysis._calculate_volatility_metrics(symbol, klines)
    
    async def _analyze_volume_profile(self, symbol: str, klines: List[Dict]) -> Dict[str, Any]:
        """Анализ профиля объемов"""
        return await self._market_analysis._analyze_volume_profile(symbol, klines)
    
    async def _calculate_trend_strength(self, symbol: str, klines: List[Dict]) -> float:
        """Расчет силы тренда"""
        return await self._market_analysis._calculate_trend_strength(symbol, klines)
    
    async def _analyze_support_resistance(self, symbol: str, klines: List[Dict]) -> Dict[str, List[float]]:
        """Анализ уровней поддержки и сопротивления"""
        return await self._market_analysis._analyze_support_resistance(symbol, klines)
    
    async def _find_all_trading_opportunities(self) -> List[TradingOpportunity]:
        """Поиск всех торговых возможностей"""
        return await self._market_analysis._find_all_trading_opportunities()
    
    async def _evaluate_opportunity(self, symbol: str, market_state: MarketState) -> Optional[TradingOpportunity]:
        """Оценка торговой возможности"""
        return await self._market_analysis._evaluate_opportunity(symbol, market_state)
    
    async def _calculate_entry_exit_points(self, symbol: str, decision: TradeDecision) -> Tuple[float, float, float]:
        """Расчет точек входа и выхода"""
        return await self._market_analysis._calculate_entry_exit_points(symbol, decision)
    
    # =================================================================
    # ИСПОЛНЕНИЕ СДЕЛОК - делегирование в trade_execution.py
    # =================================================================
    
    async def _execute_best_trades(self, opportunities: List[TradingOpportunity]) -> int:
        """Исполнение лучших сделок"""
        return await self._trade_execution._execute_best_trades(opportunities)
    
    async def _execute_single_trade(self, opportunity: TradingOpportunity) -> bool:
        """Исполнение одной сделки"""
        return await self._trade_execution._execute_single_trade(opportunity)
    
    async def _validate_trade_opportunity(self, opportunity: TradingOpportunity) -> bool:
        """Валидация торговой возможности"""
        return await self._trade_execution._validate_trade_opportunity(opportunity)
    
    async def _calculate_position_size(self, opportunity: TradingOpportunity) -> float:
        """Расчет размера позиции"""
        return await self._trade_execution._calculate_position_size(opportunity)
    
    async def _place_trade_order(self, opportunity: TradingOpportunity, position_size: float) -> Optional[dict]:
        """Размещение торгового ордера"""
        return await self._trade_execution._place_trade_order(opportunity, position_size)
    
    async def _monitor_order_execution(self, order: dict) -> bool:
        """Мониторинг исполнения ордера"""
        return await self._trade_execution._monitor_order_execution(order)
    
    async def _place_protective_orders(self, order: dict, opportunity: TradingOpportunity) -> bool:
        """Размещение защитных ордеров"""
        return await self._trade_execution._place_protective_orders(order, opportunity)
    
    # =================================================================
    # УПРАВЛЕНИЕ ПОЗИЦИЯМИ - делегирование в position_management.py
    # =================================================================
    
    async def _update_all_positions(self):
        """Обновление всех позиций"""
        return await self._position_management._update_all_positions()
    
    async def _check_position_exits(self):
        """Проверка условий выхода из позиций"""
        return await self._position_management._check_position_exits()
    
    async def _update_stop_losses(self):
        """Обновление стоп-лоссов"""
        return await self._position_management._update_stop_losses()
    
    async def _manage_position_risk(self, position: dict):
        """Управление риском позиции"""
        return await self._position_management._manage_position_risk(position)
    
    async def _close_position(self, position: dict, reason: str) -> bool:
        """Закрытие позиции"""
        return await self._position_management._close_position(position, reason)
    
    async def _calculate_position_pnl(self, position: dict) -> float:
        """Расчет PnL позиции"""
        return await self._position_management._calculate_position_pnl(position)
    
    # =================================================================
    # МОНИТОРИНГ - делегирование в monitoring.py
    # =================================================================
    
    async def _check_system_health(self):
        """Проверка здоровья системы"""
        return await self._monitoring._check_system_health()
    
    async def _monitor_component_health(self) -> Dict[str, ComponentStatus]:
        """Мониторинг здоровья компонентов"""
        return await self._monitoring._monitor_component_health()
    
    async def _check_exchange_connectivity(self) -> bool:
        """Проверка соединения с биржей"""
        return await self._monitoring._check_exchange_connectivity()
    
    async def _monitor_memory_usage(self) -> Dict[str, float]:
        """Мониторинг использования памяти"""
        return await self._monitoring._monitor_memory_usage()
    
    async def _monitor_task_health(self) -> Dict[str, str]:
        """Мониторинг здоровья задач"""
        return await self._monitoring._monitor_task_health()
    
    async def _check_rate_limits(self) -> Dict[str, Any]:
        """Проверка лимитов запросов"""
        return await self._monitoring._check_rate_limits()
    
    async def _track_performance_metrics(self):
        """Отслеживание метрик производительности"""
        return await self._monitoring._track_performance_metrics()
    
    async def _calculate_current_metrics(self) -> PerformanceMetrics:
        """Расчет текущих метрик"""
        return await self._monitoring._calculate_current_metrics()
    
    async def _update_trading_statistics(self):
        """Обновление торговой статистики"""
        return await self._monitoring._update_trading_statistics()
    
    # =================================================================
    # УТИЛИТЫ - делегирование в utilities.py
    # =================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Получение полного статуса системы"""
        return self._utilities.get_status()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Получение статистики производительности"""
        return self._utilities.get_performance_stats()
    
    def get_active_strategies(self) -> List[str]:
        """Получение списка активных стратегий"""
        return self._utilities.get_active_strategies()
    
    async def cleanup_old_data(self):
        """Очистка устаревших данных"""
        return await self._utilities.cleanup_old_data()
    
    def format_balance_info(self, balance_info: dict) -> str:
        """Форматирование информации о балансе"""
        return self._utilities.format_balance_info(balance_info)
    
    def log_trade_result(self, trade_result: dict):
        """Логирование результата сделки"""
        return self._utilities.log_trade_result(trade_result)
    
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
        if hasattr(self, '_real_position_manager'):
            return self._real_position_manager
        return None

# =========================================================================
# === СОЗДАНИЕ ГЛОБАЛЬНОГО ЭКЗЕМПЛЯРА ===
# =========================================================================

# Создаем единственный экземпляр менеджера бота (Singleton)
bot_manager = BotManager()

def get_bot_manager():
    """Возвращает глобальный экземпляр BotManager."""
    return bot_manager

# Экспорт для полной совместимости
__all__ = [
    'BotManager', 
    'bot_manager',
    'get_bot_manager',
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

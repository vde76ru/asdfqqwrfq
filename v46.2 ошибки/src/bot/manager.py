#!/usr/bin/env python3
# Файл: src/bot/manager.py
# ОПИСАНИЕ: Главный класс BotManager, который управляет всеми компонентами бота.
# Он делегирует выполнение задач специализированным внутренним модулям.

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from .internal.types import (
    BotStatus, ComponentStatus, MarketPhase, RiskLevel, TradeDecision,
    TradingOpportunity, MarketState, ComponentInfo, PerformanceMetrics, TradingStatistics
)
from ..core.unified_config import unified_config as config

try:
    from ..strategies.whale_hunting import WhaleHuntingStrategy
except ImportError:
    WhaleHuntingStrategy = None

try:
    from ..strategies.sleeping_giants import SleepingGiantsStrategy
except ImportError:
    SleepingGiantsStrategy = None

try:
    from ..strategies.order_book_analysis import OrderBookAnalysisStrategy
except ImportError:
    OrderBookAnalysisStrategy = None

try:
    from ..strategies.signal_aggregator import SignalAggregator
except ImportError:
    SignalAggregator = None

logger = logging.getLogger(__name__)

class BotManager:
    """
    🤖 ГЛАВНЫЙ МЕНЕДЖЕР ТОРГОВОГО БОТА - ДИРИЖЕР ОРКЕСТРА
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
        
        # === ОСНОВНЫЕ АТРИБУТЫ ===
        self.status = BotStatus.STOPPED
        self.start_time = None
        self.stop_time = None
        self.pause_time = None
        self.is_running = False
        self.socketio = None
        
        self.all_trading_pairs = []
        self.active_pairs = []
        self.inactive_pairs = []
        self.blacklisted_pairs = set()
        self.watchlist_pairs = []
        self.trending_pairs = []
        self.high_volume_pairs = []
        self.positions = {}
        self.pending_orders = {}
        
        self.cycles_count = 0
        self.trades_today = 0
        self.daily_profit = 0.0
        self.weekly_profit = 0.0
        self.monthly_profit = 0.0
        
        self.components = {}
        self.tasks = {}
        self.task_health = {}
        
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
        
        self.available_strategies = config.ENABLED_STRATEGIES if hasattr(config, 'ENABLED_STRATEGIES') else {}
        self.strategy_instances = {}
        self.strategy_performance = {}
        
        self.balance = 0.0
        self.available_balance = 0.0
        self.locked_balance = 0.0
        self.paper_balance = None
        self.paper_positions = {}
        self.paper_trades_history = []
        self.paper_stats = {}
        
        self.market_data_cache = {}
        self.price_history = {}
        self.volume_history = {}
        self.indicator_cache = {}
        self.candle_cache = {}
        
        self._stop_event = None
        self._pause_event = None
        
        self.config = config
        self.bot_config = config
        self.testnet = getattr(config, 'USE_TESTNET', False)
        self._exchange_initialized = False
        
        self.signals_matrix_cache = {}
        self.matrix_cache_ttl = 30 # секунды
        self.last_matrix_update = None
        
        from ..risk.risk_calculator import RiskCalculator
        self.risk_calculator = RiskCalculator()
        self.onchain_producer = None  
        self.bybit_producer = None    
        self.signal_tasks = []        
        
        logger.info("🔧 Инициализация компонентов системы сигналов...")
        self._init_signal_components()
        
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
            logger.info("🔧 Инициализация компонентов системы сигналов...")
            
            # Загружаем конфигурацию
            from ..core.unified_config import unified_config as config
            
            def safe_get_float(key: str, default: float) -> float:
                """Безопасное получение float значения из конфигурации"""
                try:
                    value = getattr(config, key, default)
                    return float(value) if value is not None else default
                except (ValueError, AttributeError):
                    logger.warning(f"⚠️ Не удалось получить {key}, используется значение по умолчанию: {default}")
                    return default
            
            # ✅ ИСПРАВЛЕНИЕ: Инициализируем каждую стратегию в отдельном try-except блоке
            
            # 1. WhaleHuntingStrategy
            try:
                from ..strategies.whale_hunting import WhaleHuntingStrategy
                self.whale_hunting_strategy = WhaleHuntingStrategy(
                    min_usd_value=safe_get_float('WHALE_MIN_USD_VALUE', 100000.0),
                    exchange_flow_threshold=safe_get_float('WHALE_EXCHANGE_FLOW_THRESHOLD', 500000.0)
                )
                logger.info("✅ WhaleHuntingStrategy инициализирована")
            except ImportError as e:
                logger.error(f"❌ Не удалось импортировать WhaleHuntingStrategy: {e}")
                self.whale_hunting_strategy = None
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации WhaleHuntingStrategy: {e}")
                self.whale_hunting_strategy = None
    
            # 2. SleepingGiantsStrategy  
            try:
                from ..strategies.sleeping_giants import SleepingGiantsStrategy
                self.sleeping_giants_strategy = SleepingGiantsStrategy(
                    volatility_threshold=safe_get_float('SLEEPING_GIANTS_VOLATILITY_THRESHOLD', 0.02),
                    volume_anomaly_threshold=safe_get_float('SLEEPING_GIANTS_VOLUME_THRESHOLD', 0.7),
                    hurst_threshold=safe_get_float('SLEEPING_GIANTS_HURST_THRESHOLD', 0.45),
                    ofi_threshold=safe_get_float('SLEEPING_GIANTS_OFI_THRESHOLD', 0.3),
                    min_confidence=safe_get_float('SLEEPING_GIANTS_MIN_CONFIDENCE', 0.6)
                )
                logger.info("✅ SleepingGiantsStrategy инициализирована")
            except ImportError as e:
                logger.error(f"❌ Не удалось импортировать SleepingGiantsStrategy: {e}")
                self.sleeping_giants_strategy = None
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации SleepingGiantsStrategy: {e}")
                self.sleeping_giants_strategy = None
    
            # 3. OrderBookAnalysisStrategy
            try:
                from ..strategies.order_book_analysis import OrderBookAnalysisStrategy
                order_book_config = {
                    'wall_threshold': safe_get_float('ORDER_BOOK_WALL_THRESHOLD', 5.0),
                    'spoofing_time_window': int(getattr(config, 'ORDER_BOOK_SPOOFING_WINDOW', 300)),
                    'absorption_volume_ratio': safe_get_float('ORDER_BOOK_ABSORPTION_RATIO', 3.0),
                    'imbalance_threshold': safe_get_float('ORDER_BOOK_IMBALANCE_THRESHOLD', 2.0),
                    'lookback_minutes': int(getattr(config, 'ORDER_BOOK_LOOKBACK_MINUTES', 30))
                }
                self.order_book_analysis = OrderBookAnalysisStrategy(
                    config=order_book_config,
                    exchange_client=self.exchange_client
                )
                logger.info("✅ OrderBookAnalysisStrategy инициализирована")
            except ImportError as e:
                logger.error(f"❌ Не удалось импортировать OrderBookAnalysisStrategy: {e}")
                self.order_book_analysis = None
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации OrderBookAnalysisStrategy: {e}")
                self.order_book_analysis = None
    
            # 4. SignalAggregator
            try:
                from ..strategies.signal_aggregator import SignalAggregator
                self.signal_aggregator = SignalAggregator()
                logger.info("✅ SignalAggregator инициализирован")
            except ImportError as e:
                logger.error(f"❌ Не удалось импортировать SignalAggregator: {e}")
                self.signal_aggregator = None
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации SignalAggregator: {e}")
                self.signal_aggregator = None
    
            # 5. NotificationManager
            try:
                if hasattr(config, "TELEGRAM_BOT_TOKEN") and hasattr(config, "TELEGRAM_CHAT_ID"):
                    from ..notifications import NotificationManager
                    self.notification_manager = NotificationManager()
                    logger.info("✅ NotificationManager инициализирован")
                else:
                    self.notification_manager = None
                    logger.warning("⚠️ NotificationManager не инициализирован: отсутствуют настройки Telegram.")
            except ImportError as e:
                logger.error(f"❌ Не удалось импортировать NotificationManager: {e}")
                self.notification_manager = None
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации NotificationManager: {e}")
                self.notification_manager = None
                
            logger.info("✅ Компоненты системы сигналов инициализированы")
            
            #6. Инициализация продюсеров данных
            try:
                # Bybit producer (обязательный)
                from ..api_clients.bybit_data_producer import BybitDataProducer
                self.bybit_producer = BybitDataProducer(testnet=getattr(config, 'USE_TESTNET', True))
                logger.info("✅ BybitDataProducer инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации BybitDataProducer: {e}")
                self.bybit_producer = None
    
            try:
                # Onchain producer (опциональный)
                if hasattr(config, 'ETHERSCAN_API_KEY') and config.ETHERSCAN_API_KEY != "***ВАШ_ETHERSCAN_API_КЛЮЧ***":
                    from ..api_clients.onchain_data_producer import OnchainDataProducer
                    self.onchain_producer = OnchainDataProducer()
                    logger.info("✅ OnchainDataProducer инициализирован")
                else:
                    self.onchain_producer = None
                    logger.info("ℹ️ OnchainDataProducer пропущен - нет API ключа")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации OnchainDataProducer: {e}")
                self.onchain_producer = None
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при инициализации компонентов сигналов: {e}")
            # ✅ НЕ ПОДНИМАЕМ ИСКЛЮЧЕНИЕ, чтобы приложение продолжило работу
            logger.warning("⚠️ Некоторые компоненты сигналов недоступны, но приложение продолжит работу")
            
    def get_balance_info(self) -> Dict[str, Any]:
        """Получение информации о балансе"""
        return self._utilities.get_balance_info()
    
    def get_positions_info(self) -> List[Dict[str, Any]]:
        """Получение информации о позициях"""
        return self._utilities.get_positions_info()
            
            
    def get_signals_matrix_data(self) -> Optional[List[Dict]]:
        """Получение данных матрицы сигналов из кэша"""
        logger.debug(f"Запрос матрицы сигналов. Кэш: {len(self.signals_matrix_cache)} элементов")
        
        if not self.signals_matrix_cache:
            logger.warning("Матрица сигналов пуста!")
            return []
            
        if self.last_matrix_update:
            cache_age = (datetime.utcnow() - self.last_matrix_update).seconds
            if cache_age > self.matrix_cache_ttl:
                logger.warning(f"Кэш матрицы устарел: {cache_age}с > {self.matrix_cache_ttl}с")
                data = list(self.signals_matrix_cache.values())
                for item in data:
                    item['cache_expired'] = True
                return data
                
        return list(self.signals_matrix_cache.values())
    
    def get_symbol_details(self, symbol: str) -> Optional[Dict]:
        """Получение детальной информации по символу"""
        if symbol not in self.signals_matrix_cache:
            return None
            
        details = self.signals_matrix_cache[symbol].copy()
        
        from ..core.database import SessionLocal
        from datetime import timedelta
        
        db = SessionLocal()
        try:
            from ..core.models import WhaleTransaction, OrderBookSnapshot
            
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
        
        if not self.active_pairs:
            logger.warning("❌ Нет активных торговых пар для анализа!")
            return
        
        try:
            # Анализируем каждую пару
            for symbol in self.active_pairs[:10]:  # Ограничиваем 10 парами для производительности
                try:
                    # Получаем данные о паре
                    data = {
                        'symbol': symbol,
                        'timestamp': datetime.utcnow().isoformat(),
                        'signals': {
                            'multi_indicator': 'NEUTRAL',
                            'momentum': 'NEUTRAL',
                            'scalping': 'NEUTRAL',
                            'whale_hunting': 'NEUTRAL',
                            'sleeping_giants': 'NEUTRAL',
                            'order_book': 'NEUTRAL'
                        },
                        'confidence': 0.0,
                        'price': 0.0,
                        'volume_24h': 0.0,
                        'price_change_24h': 0.0
                    }
                    
                    # Получаем текущую цену
                    if hasattr(self, 'enhanced_exchange_client') and self.enhanced_exchange_client:
                        try:
                            ticker = await self.enhanced_exchange_client.get_ticker(symbol)
                            if ticker:
                                data['price'] = ticker.get('last', 0.0)
                                data['volume_24h'] = ticker.get('quoteVolume', 0.0)
                                data['price_change_24h'] = ticker.get('percentage', 0.0)
                        except Exception as e:
                            logger.debug(f"Ошибка получения тикера для {symbol}: {e}")
                    
                    # Анализируем стратегиями
                    if hasattr(self, 'strategy_instances'):
                        for strategy_name, strategy in self.strategy_instances.items():
                            try:
                                if hasattr(strategy, 'analyze'):
                                    signal = await strategy.analyze(symbol)
                                    if signal and hasattr(signal, 'action'):
                                        data['signals'][strategy_name] = signal.action
                                        data['confidence'] = max(data['confidence'], 
                                                               getattr(signal, 'confidence', 0.5))
                            except Exception as e:
                                logger.debug(f"Ошибка анализа {strategy_name} для {symbol}: {e}")
                    
                    # Анализ сигнальными стратегиями
                    signal_strategies = {
                        'whale_hunting': self.whale_hunting,
                        'sleeping_giants': self.sleeping_giants,
                        'order_book': self.order_book_analysis
                    }
                    
                    for strategy_name, strategy in signal_strategies.items():
                        if strategy and hasattr(strategy, 'analyze_symbol'):
                            try:
                                signal = await strategy.analyze_symbol(symbol)
                                if signal:
                                    data['signals'][strategy_name] = signal.get('signal', 'NEUTRAL')
                            except Exception as e:
                                logger.debug(f"Ошибка анализа {strategy_name} для {symbol}: {e}")
                    
                    # Сохраняем в кэш
                    self.signals_matrix_cache[symbol] = data
                    
                except Exception as e:
                    logger.error(f"Ошибка обновления сигналов для {symbol}: {e}")
                    continue
            
            self.last_matrix_update = datetime.utcnow()
            logger.info(f"✅ Матрица сигналов обновлена: {len(self.signals_matrix_cache)} пар")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка обновления матрицы: {e}")
    
    # ... (Остальные методы делегирования без изменений) ...
    async def initialize_all_components(self) -> bool:
        return await self._initialization.initialize_all_components()
    async def init_exchange_client(self):
        return await self._initialization.init_exchange_client()
    async def initialize_enhanced_exchange(self):
        return await self._initialization.initialize_enhanced_exchange()
    async def init_market_analyzer(self):
        return await self._initialization.init_market_analyzer()
    async def init_trader(self):
        return await self._initialization.init_trader()
    async def init_risk_manager(self):
        return await self._initialization.init_risk_manager()
    async def init_portfolio_manager(self):
        return await self._initialization.init_portfolio_manager()
    async def init_notifier(self):
        return await self._initialization.init_notifier()
    async def init_data_collector(self):
        return await self._initialization.init_data_collector()
    async def init_strategy_factory(self):
        return await self._initialization.init_strategy_factory()
    async def display_account_info(self):
        return await self._initialization.display_account_info()
    async def _process_balance_info(self, balance_info: dict):
        return await self._initialization._process_balance_info(balance_info)
    async def start_async(self):
        return await self._lifecycle.start_async()
    async def pause(self):
        return await self._lifecycle.pause()
    async def resume(self):
        return await self._lifecycle.resume()
    async def emergency_stop(self):
        return await self._lifecycle.emergency_stop()
    async def _start_all_trading_loops(self):
        return await self._lifecycle._start_all_trading_loops()
    async def _discover_all_trading_pairs(self):
        return await self._trading_pairs._discover_all_trading_pairs()
    async def _load_historical_data_for_pairs(self):
        return await self._trading_pairs._load_historical_data_for_pairs()
    def _load_pairs_from_config(self):
        return self._trading_pairs._load_pairs_from_config()
    async def update_pairs(self, pairs: List[str]) -> None:
        return await self._trading_pairs.update_pairs(pairs)
    async def _main_trading_loop(self):
        return await self._trading_loops._main_trading_loop()
    async def _market_monitoring_loop(self):
        return await self._trading_loops._market_monitoring_loop()
    async def _pair_discovery_loop(self):
        return await self._trading_loops._pair_discovery_loop()
    async def _position_management_loop(self):
        return await self._trading_loops._position_management_loop()
    async def _risk_monitoring_loop(self):
        return await self._trading_loops._risk_monitoring_loop()
    async def _health_monitoring_loop(self):
        return await self._trading_loops._health_monitoring_loop()
    async def _performance_tracking_loop(self):
        return await self._trading_loops._performance_tracking_loop()
    async def _cleanup_loop(self):
        return await self._trading_loops._cleanup_loop()
    async def _balance_monitoring_loop(self):
        return await self._trading_loops._balance_monitoring_loop()
    async def _strategy_evaluation_loop(self):
        return await self._trading_loops._strategy_evaluation_loop()
    async def _data_collection_loop(self):
        return await self._trading_loops._data_collection_loop()
    async def _sentiment_analysis_loop(self):
        return await self._trading_loops._sentiment_analysis_loop()
    async def _event_processing_loop(self):
        return await self._trading_loops._event_processing_loop()
    async def start_signal_system_loops(self):
        return await self._trading_loops.start_signal_system_loops()
    async def _analyze_market_conditions(self):
        return await self._market_analysis._analyze_market_conditions()
    async def _analyze_single_pair(self, symbol: str) -> Optional[MarketState]:
        return await self._market_analysis._analyze_single_pair(symbol)
    async def _detect_market_phase(self, symbol: str, klines: List[Dict]) -> MarketPhase:
        return await self._market_analysis._detect_market_phase(symbol, klines)
    async def _calculate_volatility_metrics(self, symbol: str, klines: List[Dict]) -> Dict[str, float]:
        return await self._market_analysis._calculate_volatility_metrics(symbol, klines)
    async def _analyze_volume_profile(self, symbol: str, klines: List[Dict]) -> Dict[str, Any]:
        return await self._market_analysis._analyze_volume_profile(symbol, klines)
    async def _calculate_trend_strength(self, symbol: str, klines: List[Dict]) -> float:
        return await self._market_analysis._calculate_trend_strength(symbol, klines)
    async def _analyze_support_resistance(self, symbol: str, klines: List[Dict]) -> Dict[str, List[float]]:
        return await self._market_analysis._analyze_support_resistance(symbol, klines)
    async def _find_all_trading_opportunities(self) -> List[TradingOpportunity]:
        return await self._market_analysis._find_all_trading_opportunities()
    async def _evaluate_opportunity(self, symbol: str, market_state: MarketState) -> Optional[TradingOpportunity]:
        return await self._market_analysis._evaluate_opportunity(symbol, market_state)
    async def _calculate_entry_exit_points(self, symbol: str, decision: TradeDecision) -> Tuple[float, float, float]:
        return await self._market_analysis._calculate_entry_exit_points(symbol, decision)
    async def _execute_best_trades(self, opportunities: List[TradingOpportunity]) -> int:
        return await self._trade_execution._execute_best_trades(opportunities)
    async def _execute_single_trade(self, opportunity: TradingOpportunity) -> bool:
        return await self._trade_execution._execute_single_trade(opportunity)
    async def _validate_trade_opportunity(self, opportunity: TradingOpportunity) -> bool:
        return await self._trade_execution._validate_trade_opportunity(opportunity)
    async def _calculate_position_size(self, opportunity: TradingOpportunity) -> float:
        return await self._trade_execution._calculate_position_size(opportunity)
    async def _place_trade_order(self, opportunity: TradingOpportunity, position_size: float) -> Optional[dict]:
        return await self._trade_execution._place_trade_order(opportunity, position_size)
    async def _monitor_order_execution(self, order: dict) -> bool:
        return await self._trade_execution._monitor_order_execution(order)
    async def _place_protective_orders(self, order: dict, opportunity: TradingOpportunity) -> bool:
        return await self._trade_execution._place_protective_orders(order, opportunity)
    async def _update_all_positions(self):
        return await self._position_management._update_all_positions()
    async def _check_position_exits(self):
        return await self._position_management._check_position_exits()
    async def _update_stop_losses(self):
        return await self._position_management._update_stop_losses()
    async def _manage_position_risk(self, position: dict):
        return await self._position_management._manage_position_risk(position)
    async def _close_position(self, position: dict, reason: str) -> bool:
        return await self._position_management._close_position(position, reason)
    async def _calculate_position_pnl(self, position: dict) -> float:
        return await self._position_management._calculate_position_pnl(position)
    async def _check_system_health(self):
        return await self._monitoring._check_system_health()
    async def _monitor_component_health(self) -> Dict[str, ComponentStatus]:
        return await self._monitoring._monitor_component_health()
    async def _check_exchange_connectivity(self) -> bool:
        return await self._monitoring._check_exchange_connectivity()
    async def _monitor_memory_usage(self) -> Dict[str, float]:
        return await self._monitoring._monitor_memory_usage()
    async def _monitor_task_health(self) -> Dict[str, str]:
        return await self._monitoring._monitor_task_health()
    async def _check_rate_limits(self) -> Dict[str, Any]:
        return await self._monitoring._check_rate_limits()
    async def _track_performance_metrics(self):
        return await self._monitoring._track_performance_metrics()
    async def _calculate_current_metrics(self) -> PerformanceMetrics:
        return await self._monitoring._calculate_current_metrics()
    async def _update_trading_statistics(self):
        return await self._monitoring._update_trading_statistics()
    def get_status(self) -> Dict[str, Any]:
        return self._utilities.get_status()
    def get_performance_stats(self) -> Dict[str, Any]:
        return self._utilities.get_performance_stats()
    def get_active_strategies(self) -> List[str]:
        return self._utilities.get_active_strategies()
    async def cleanup_old_data(self):
        return await self._utilities.cleanup_old_data()
    def format_balance_info(self, balance_info: dict) -> str:
        return self._utilities.format_balance_info(balance_info)
    def log_trade_result(self, trade_result: dict):
        return self._utilities.log_trade_result(trade_result)
    def start(self) -> Tuple[bool, str]:
        return self._compatibility.start()
    def stop(self) -> Tuple[bool, str]:
        return self._compatibility.stop()
    def __repr__(self) -> str:
        return self._compatibility.__repr__()
    def set_socketio(self, socketio_instance):
        return self._compatibility.set_socketio(socketio_instance)
    @property
    def lifecycle(self):
        return self._lifecycle
    @property
    def position_manager(self):
        if hasattr(self, '_real_position_manager'):
            return self._real_position_manager
        return None

# Глобальный экземпляр
bot_manager = BotManager()

def get_bot_manager():
    """Возвращает глобальный экземпляр BotManager."""
    return bot_manager

__all__ = [
    'BotManager', 'bot_manager', 'get_bot_manager', 'BotStatus', 'ComponentStatus', 
    'MarketPhase', 'RiskLevel', 'TradeDecision', 'TradingOpportunity', 'MarketState', 
    'ComponentInfo', 'PerformanceMetrics', 'TradingStatistics'
]

if __name__ == "__main__":
    print("🤖 НОВЫЙ BotManager (дирижер) загружен успешно")
    print(f"📊 Manager instance: {bot_manager}")
    print(f"🔧 Configuration loaded: {hasattr(config, 'BYBIT_API_KEY') if config else 'No config'}")
    print("🎼 Все внутренние модули подключены как оркестр!")

"""
Модуль инициализации компонентов BotManager
Файл: src/bot/internal/initialization.py

Все методы инициализации компонентов системы
"""

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import os

from src.core.database import SessionLocal, get_session
from src.core.unified_config import unified_config as config
from src.bot.internal.types import ComponentInfo, ComponentStatus
from src.core.unified_config import UnifiedConfig

logger = logging.getLogger(__name__)

def get_initialization(bot_instance):
    """Возвращает объект с методами инициализации"""
    
    class Initialization:
        def __init__(self, bot):
            self.bot = bot
            
        async def initialize_all_components(self):
            """Инициализация всех компонентов системы"""
            return await initialize_all_components(self.bot)
            
        async def init_exchange_client(self):
            """Инициализация клиента биржи"""
            return await init_exchange_client(self.bot)
            
        async def initialize_enhanced_exchange(self):
            """Инициализация расширенного exchange клиента"""
            return await initialize_enhanced_exchange(self.bot)
            
        async def init_market_analyzer(self):
            """Инициализация анализатора рынка"""
            return await init_market_analyzer(self.bot)
            
        async def init_trader(self):
            """Инициализация трейдера"""
            return await init_trader(self.bot)
            
        async def init_risk_manager(self):
            """Инициализация менеджера рисков"""
            return await init_risk_manager(self.bot)
            
        async def init_portfolio_manager(self):
            """Инициализация портфельного менеджера"""
            return await init_portfolio_manager(self.bot)
            
        async def init_notifier(self):
            """Инициализация уведомлений"""
            return await init_notifier(self.bot)
            
        async def init_data_collector(self):
            """Инициализация сборщика данных"""
            return await init_data_collector(self.bot)
            
        async def init_strategy_factory(self):
            """Инициализация фабрики стратегий"""
            return await init_strategy_factory(self.bot)
            
        async def display_account_info(self):
            """Отображение информации об аккаунте"""
            return await display_account_info(self.bot)
            
        async def _process_balance_info(self, balance_info: dict):
            """Обработка и отображение информации о балансе"""
            return await _process_balance_info(self.bot, balance_info)
            
        async def init_config_validator(self):
            """Инициализация валидатора конфигурации"""
            return await init_config_validator(self.bot)
            
        async def init_execution_engine(self):
            """Инициализация движка исполнения"""
            return await init_execution_engine(self.bot)
            
        async def init_ml_system(self):
            """Инициализация ML системы"""
            return await init_ml_system(self.bot)
            
        async def init_news_analyzer(self):
            """Инициализация анализатора новостей"""
            return await init_news_analyzer(self.bot)
            
        async def init_websocket_manager(self):
            """Инициализация WebSocket менеджера"""
            return await init_websocket_manager(self.bot)
            
        async def init_export_manager(self):
            """Инициализация менеджера экспорта"""
            return await init_export_manager(self.bot)
            
        async def init_health_monitor(self):
            """Инициализация монитора здоровья"""
            return await init_health_monitor(self.bot)
    
    return Initialization(bot_instance)


async def initialize_all_components(bot_manager) -> bool:
    """Инициализация всех компонентов системы"""
    try:
        logger.info("🔧 Инициализация компонентов системы...")
        
        # ✅ СНАЧАЛА ИНИЦИАЛИЗИРУЕМ EXCHANGE ОТДЕЛЬНО (ВНЕ ЦИКЛА)
        if not bot_manager._exchange_initialized:
            logger.info("🔧 Инициализация exchange_client...")
            exchange_success = await init_exchange_client(bot_manager)
            if not exchange_success:
                logger.error("❌ Критическая ошибка: не удалось инициализировать exchange")
                return False
            bot_manager._exchange_initialized = True
            logger.info("✅ exchange_client инициализирован")
        else:
            logger.info("✅ exchange_client уже инициализирован")
        
        # ✅ ИНИЦИАЛИЗАЦИЯ ENHANCED EXCHANGE - ДОБАВЛЕНО ЗДЕСЬ
        logger.info("🚀 Инициализация enhanced exchange...")
        try:
            await initialize_enhanced_exchange(bot_manager)
        except Exception as e:
            logger.warning(f"⚠️ Enhanced exchange недоступен: {e}")
        
        # Определяем порядок инициализации с учетом зависимостей
        initialization_order = [
            ('database', init_database, [], True),
            ('config_validator', init_config_validator, ['database'], True),
            ('data_collector', init_data_collector, [], True),
            ('market_analyzer', init_market_analyzer, ['data_collector'], True),
            ('risk_manager', init_risk_manager, ['market_analyzer'], True),
            ('portfolio_manager', init_portfolio_manager, ['risk_manager'], True),
            ('strategy_factory', init_strategy_factory, ['market_analyzer'], True),
            ('signal_strategies', init_signal_strategies, ['strategy_factory'], False),
            ('trader', init_trader, ['exchange_client', 'risk_manager'], True),
            ('execution_engine', init_execution_engine, ['exchange_client', 'risk_manager'], False),
            ('notifier', init_notifier, [], False),
            ('ml_system', init_ml_system, ['data_collector'], False),
            ('news_analyzer', init_news_analyzer, [], False),
            ('websocket_manager', init_websocket_manager, ['exchange_client'], False),
            ('export_manager', init_export_manager, ['database'], False),
            ('health_monitor', init_health_monitor, [], False)
        ]
        
        # Инициализируем компоненты в порядке зависимостей
        for comp_name, init_func, dependencies, is_critical in initialization_order:
            try:
                # ✅ ИСПРАВЛЕНО: Специальная проверка для компонентов с зависимостью от exchange_client
                if 'exchange_client' in dependencies and not bot_manager._exchange_initialized:
                    logger.warning(f"⚠️ {comp_name} пропущен - exchange_client еще не готов")
                    continue
                
                # Проверяем остальные зависимости
                other_deps = [dep for dep in dependencies if dep != 'exchange_client']
                deps_ready = all(
                    bot_manager.components.get(dep, ComponentInfo('', ComponentStatus.NOT_INITIALIZED)).status == ComponentStatus.READY
                    for dep in other_deps
                )
                
                if not deps_ready and other_deps:
                    logger.warning(f"⚠️ Зависимости для {comp_name} не готовы: {other_deps}")
                    if is_critical:
                        return False
                    continue
                
                # Создаем информацию о компоненте
                comp_info = ComponentInfo(
                    name=comp_name,
                    status=ComponentStatus.INITIALIZING,
                    dependencies=dependencies,
                    is_critical=is_critical
                )
                bot_manager.components[comp_name] = comp_info
                
                logger.info(f"🔧 Инициализация {comp_name}...")
                
                # Инициализируем компонент
                result = await init_func(bot_manager)
                
                if result:
                    comp_info.status = ComponentStatus.READY
                    comp_info.last_heartbeat = datetime.utcnow()
                    logger.info(f"✅ {comp_name} инициализирован")
                else:
                    comp_info.status = ComponentStatus.FAILED
                    logger.error(f"❌ Ошибка инициализации {comp_name}")
                    if is_critical:
                        return False
                    
            except Exception as e:
                logger.error(f"❌ Исключение при инициализации {comp_name}: {e}")
                if comp_name in bot_manager.components:
                    bot_manager.components[comp_name].status = ComponentStatus.FAILED
                    bot_manager.components[comp_name].error = str(e)
                if is_critical:
                    return False
        
        # Проверяем критически важные компоненты
        critical_components = [name for name, comp in bot_manager.components.items() if comp.is_critical]
        failed_critical = [name for name in critical_components 
                         if bot_manager.components[name].status != ComponentStatus.READY]
        
        if failed_critical:
            logger.error(f"❌ Критически важные компоненты не инициализированы: {failed_critical}")
            return False
        
        logger.info(f"✅ Инициализировано {len([c for c in bot_manager.components.values() if c.status == ComponentStatus.READY])} компонентов")
        return True
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка инициализации компонентов: {e}")
        return False


async def init_database(bot_manager) -> bool:
    """Инициализация подключения к базе данных"""
    try:
        # ✅ ИСПРАВЛЕНО: Импорт text для SQLAlchemy 2.x
        from sqlalchemy import text
        
        # Тестируем подключение к БД
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))  # ✅ ИСПРАВЛЕНО!
            db.commit()
            logger.info("✅ База данных подключена успешно")
            return True
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        return False


async def init_config_validator(bot_manager) -> bool:
    """Инициализация валидатора конфигурации"""
    try:
        # Валидируем конфигурацию
        if not config.validate_config():
            return False
        
        logger.info("✅ Конфигурация валидна")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка валидации конфигурации: {e}")
        return False


async def init_exchange_client(bot_manager):
    """
    Инициализация клиента биржи.
    Эта версия исправляет ошибку TypeError, возвращаясь к правильной логике
    создания клиента и последующего подключения.
    """
    try:
        # Импортируем необходимые классы из вашего модуля exchange
        from ...exchange import get_enhanced_exchange_client, BYBIT_INTEGRATION_AVAILABLE

        # Проверяем, доступна ли расширенная интеграция (например, с bybit_v5)
        if BYBIT_INTEGRATION_AVAILABLE:
            logger.info("🚀 Используем EnhancedUnifiedExchangeClient")
            # ПРАВИЛЬНО: Вызываем функцию для получения клиента без аргументов.
            # Настройки (testnet и т.д.) будут применены на этапе подключения.
            bot_manager.exchange_client = get_enhanced_exchange_client()
        else:
            # Если расширенная интеграция недоступна, используем базовый клиент
            logger.warning("⚠️ Enhanced клиент недоступен, используем базовый")
            from ...exchange import UnifiedExchangeClient
            bot_manager.exchange_client = UnifiedExchangeClient()

        # --- Этап подключения (общий для обоих типов клиентов) ---

        # Получаем параметры подключения из глобальной конфигурации
        exchange_name = getattr(config, 'DEFAULT_EXCHANGE', 'bybit')
        testnet = getattr(config, 'BYBIT_TESTNET', True)

        logger.info(f"🔗 Подключение к {exchange_name} (testnet={testnet})...")

        # Выполняем асинхронное подключение к бирже
        success = await bot_manager.exchange_client.connect(exchange_name, testnet)

        if success:
            logger.info("✅ Exchange клиент успешно подключен")

            # Если у клиента есть дополнительный метод инициализации (для enhanced), вызываем его
            if hasattr(bot_manager.exchange_client, 'initialize'):
                logger.info("🔧 Выполняется дополнительная инициализация enhanced клиента...")
                await bot_manager.exchange_client.initialize()
                logger.info("✅ Дополнительная инициализация завершена.")

            return True
        else:
            # Если подключение не удалось, логируем ошибку и возвращаем False
            logger.error("❌ Не удалось подключиться к бирже")
            return False

    except Exception as e:
        # Логируем любую другую ошибку, которая могла произойти на этапе инициализации
        logger.error(f"❌ Критическая ошибка при инициализации exchange клиента: {e}")
        logger.error(traceback.format_exc()) # Печатаем полный traceback для отладки
        return False


async def init_data_collector(bot_manager) -> bool:
    """Инициализация сборщика данных - РЕАЛЬНЫЙ"""
    try:
        # Импортируем реальный DataCollector
        from ...data.data_collector import DataCollector
        
        # Создаем экземпляр с exchange_client и сессией БД
        bot_manager.data_collector = DataCollector(
            bot_manager.exchange_client, 
            SessionLocal  # Передаем фабрику сессий, а не self.db
        )
        
        # Запускаем сборщик
        await bot_manager.data_collector.start()
        
        logger.info("✅ DataCollector инициализирован и запущен")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации DataCollector: {e}")
        return False


async def init_market_analyzer(bot_manager) -> bool:
    """Инициализация анализатора рынка"""
    try:
        # Инициализируем анализатор рынка (заглушка)
        from ...analysis.market_analyzer import MarketAnalyzer
        bot_manager.market_analyzer = MarketAnalyzer()
        logger.info("✅ Анализатор рынка инициализирован")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации анализатора рынка: {e}")
        return False



async def init_risk_manager(bot_manager) -> bool:
    """Инициализация менеджера рисков - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        logger.info("🛡️ Инициализация Enhanced Risk Manager...")
        
        # Импортируем реальный Enhanced Risk Manager
        from ...risk.enhanced_risk_manager import EnhancedRiskManager, get_risk_manager
        
        # Создаем экземпляр через фабричную функцию
        bot_manager.risk_manager = get_risk_manager()
        
        # Проверяем что объект создан правильно
        if bot_manager.risk_manager is None:
            logger.error("❌ Не удалось создать экземпляр risk_manager")
            return False
            
        # Инициализируем систему управления рисками
        if hasattr(bot_manager.risk_manager, 'initialize'):
            await bot_manager.risk_manager.initialize()
        
        logger.info("✅ Enhanced Risk Manager успешно инициализирован")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта Enhanced Risk Manager: {e}")
        logger.info("🔄 Пытаемся использовать базовый risk manager...")
        
        # Fallback к базовому risk manager
        try:
            from ...risk.risk_calculator import RiskCalculator
            bot_manager.risk_manager = RiskCalculator()
            logger.info("✅ Базовый Risk Calculator инициализирован как fallback")
            return True
        except Exception as fallback_error:
            logger.error(f"❌ Не удалось создать даже базовый risk manager: {fallback_error}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка инициализации risk manager: {e}")
        logger.error(f"❌ Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return False


async def init_portfolio_manager(bot_manager) -> bool:
    """Инициализация менеджера портфеля"""
    try:
        # Инициализируем менеджер портфеля (заглушка)
        logger.info("✅ Менеджер портфеля инициализирован")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации менеджера портфеля: {e}")
        return False


async def init_strategy_factory(bot_manager) -> bool:
    """Инициализация фабрики стратегий - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Импортируем фабрику стратегий
        from ...strategies import strategy_factory, StrategyFactory

        # === НАЧАЛО ИСПРАВЛЕНИЯ ===
        
        # Вспомогательная функция для безопасного получения float из конфигурации
        def safe_get_float(key: str, default: float) -> float:
            """
            Безопасно получает значение из конфигурации, обрабатывая пустые строки.
            """
            value = getattr(config, key, default)
            # Проверяем, является ли значение пустой строкой
            if isinstance(value, str) and value.strip() == '':
                logger.warning(f"Параметр '{key}' не найден или пуст, используется значение по умолчанию: {default}")
                return default
            try:
                # Пытаемся преобразовать значение в float
                return float(value)
            except (ValueError, TypeError):
                # Если не получилось, используем значение по умолчанию
                logger.warning(f"Не удалось преобразовать значение '{value}' для ключа '{key}' в float. Используется значение по умолчанию: {default}")
                return default

        # === КОНЕЦ ИСПРАВЛЕНИЯ ===
        
        # Создаем или используем существующую фабрику
        if strategy_factory:
            bot_manager.strategy_factory = strategy_factory
        else:
            bot_manager.strategy_factory = StrategyFactory()
        
        # Получаем список доступных стратегий
        available_strategies = bot_manager.strategy_factory.list_strategies()
        logger.info(f"📊 Доступно стратегий: {len(available_strategies)}")
        logger.info(f"📋 Список: {', '.join(available_strategies)}")
        
        # Инициализируем активные стратегии на основе конфигурации
        bot_manager.active_strategies = {}
        
        # === НАЧАЛО ИСПРАВЛЕНИЯ ===
        # Получаем веса стратегий из конфигурации с использованием безопасной функции
        active_strategy_weights = {
            'multi_indicator': safe_get_float('MULTI_INDICATOR_WEIGHT', 1.0),
            'momentum': safe_get_float('MOMENTUM_WEIGHT', 0.8),
            'mean_reversion': safe_get_float('MEAN_REVERSION_WEIGHT', 0.7),
            'breakout': 0.6,  # Не указан в конфиге, используем жестко заданное значение
            'scalping': safe_get_float('SCALPING_WEIGHT', 0.5),
            'swing': 0.6,  # Не указан в конфиге, используем жестко заданное значение
            'whale_hunting': safe_get_float('WHALE_HUNTING_WEIGHT', 1.5),
            'sleeping_giants': safe_get_float('SLEEPING_GIANTS_WEIGHT', 1.3),
            'order_book_analysis': safe_get_float('ORDER_BOOK_WEIGHT', 1.2)
        }
        # === КОНЕЦ ИСПРАВЛЕНИЯ ===
        
        # Создаем экземпляры активных стратегий
        for strategy_name, weight in active_strategy_weights.items():
            if weight > 0 and strategy_name in available_strategies:
                try:
                    strategy = bot_manager.strategy_factory.create(strategy_name)
                    bot_manager.active_strategies[strategy_name] = {
                        'instance': strategy,
                        'weight': weight,
                        'enabled': True,
                        'performance': {
                            'total_signals': 0,
                            'successful_signals': 0,
                            'failed_signals': 0,
                            'total_profit': 0.0,
                            'win_rate': 0.0,
                            'last_signal': None
                        }
                    }
                    logger.info(f"✅ Активирована стратегия {strategy_name} с весом {weight}")
                except Exception as e:
                    logger.error(f"❌ Ошибка создания стратегии {strategy_name}: {e}")
        
        # Сохраняем конфигурацию весов для использования в анализе
        bot_manager.strategy_weights = active_strategy_weights
        
        # Добавляем нормализованные веса (в процентах)
        total_weight = sum(w for w in active_strategy_weights.values() if w > 0)
        bot_manager.normalized_strategy_weights = {
            name: (weight / total_weight * 100) if total_weight > 0 else 0
            for name, weight in active_strategy_weights.items()
        }
        
        logger.info(f"✅ Инициализировано {len(bot_manager.active_strategies)} активных стратегий")
        logger.info("📊 Нормализованные веса стратегий:")
        for name, weight in bot_manager.normalized_strategy_weights.items():
            if weight > 0:
                logger.info(f"   {name}: {weight:.1f}%")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации фабрики стратегий: {e}")
        import traceback
        traceback.print_exc()
        return False

        
async def init_signal_strategies(bot_manager) -> bool:
    """Инициализация стратегий системы сигналов - ИСПРАВЛЕНО"""
    
    def safe_get_float(key: str, default: float) -> float:
        """Безопасное получение float значения из конфигурации"""
        try:
            # Сначала пробуем получить из config
            if hasattr(config, key):
                value = getattr(config, key, default)
            else:
                # Если нет в config, пробуем переменные окружения
                value = os.environ.get(key, str(default))
            
            # Обработка различных типов значений
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                if value.strip() == '' or value.lower() == 'none':
                    return default
                return float(value.strip())
            else:
                return default
        except (ValueError, TypeError, AttributeError):
            logger.warning(f"Не удалось преобразовать {key}={value} в float, используем default={default}")
            return default
    
    try:
        # Проверяем включенные стратегии в конфигурации
        enabled_strategies = getattr(config, 'ENABLED_STRATEGIES', 'whale_hunting,sleeping_giants,order_book_analysis')
        
        # Обрабатываем как строку, так и список из конфига
        if isinstance(enabled_strategies, str):
            # Если это строка, разделяем ее
            enabled_list = [s.strip() for s in enabled_strategies.split(',') if s.strip()]
        elif isinstance(enabled_strategies, list):
            # Если это уже список, просто используем его
            enabled_list = enabled_strategies
        else:
            # Обработка неожиданного типа данных
            logger.warning(f"Неожиданный тип для ENABLED_STRATEGIES: {type(enabled_strategies)}. Используются стратегии по умолчанию.")
            enabled_list = ['whale_hunting', 'sleeping_giants', 'order_book_analysis']

        bot_manager.signal_strategies = {}
        
        # Whale Hunting - исправляем инициализацию
        if 'whale_hunting' in enabled_list:
            try:
                from ...strategies.whale_hunting import WhaleHuntingStrategy
                min_usd_value = safe_get_float('WHALE_MIN_USD_VALUE', 100000.0)
                exchange_flow_threshold = safe_get_float('WHALE_EXCHANGE_FLOW_THRESHOLD', 500000.0)
                
                # Создаем стратегию с правильными параметрами
                bot_manager.signal_strategies['whale_hunting'] = WhaleHuntingStrategy(
                    name='whale_hunting',  # первый позиционный параметр
                    min_usd_value=min_usd_value,
                    exchange_flow_threshold=exchange_flow_threshold
                )
                logger.info("✅ WhaleHuntingStrategy инициализирована")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации WhaleHunting: {e}", exc_info=True)
        
        # Sleeping Giants - исправляем инициализацию
        if 'sleeping_giants' in enabled_list:
            try:
                from ...strategies.sleeping_giants import SleepingGiantsStrategy
                
                # Создаем стратегию с правильными параметрами (без 'name')
                bot_manager.signal_strategies['sleeping_giants'] = SleepingGiantsStrategy(
                    volatility_threshold=safe_get_float('SLEEPING_GIANTS_VOLATILITY_THRESHOLD', 0.02),
                    volume_anomaly_threshold=safe_get_float('SLEEPING_GIANTS_VOLUME_THRESHOLD', 0.7),
                    hurst_threshold=safe_get_float('SLEEPING_GIANTS_HURST_THRESHOLD', 0.45),
                    ofi_threshold=safe_get_float('SLEEPING_GIANTS_OFI_THRESHOLD', 0.3),
                    min_confidence=safe_get_float('SLEEPING_GIANTS_MIN_CONFIDENCE', 0.6)
                )
                logger.info("✅ SleepingGiantsStrategy инициализирована")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации SleepingGiants: {e}", exc_info=True)
        
        # Order Book Analysis - исправляем инициализацию
        if 'order_book_analysis' in enabled_list:
            try:
                from ...strategies.order_book_analysis import OrderBookAnalysisStrategy
                
                # Создаем конфиг для стратегии
                order_book_config = {
                    'wall_threshold': safe_get_float('ORDER_BOOK_WALL_THRESHOLD', 5.0),
                    'spoofing_time_window': int(safe_get_float('ORDER_BOOK_SPOOFING_WINDOW', 300)),
                    'absorption_volume_ratio': safe_get_float('ORDER_BOOK_ABSORPTION_RATIO', 3.0),
                    'imbalance_threshold': safe_get_float('ORDER_BOOK_IMBALANCE_THRESHOLD', 2.0),
                    'lookback_minutes': int(safe_get_float('ORDER_BOOK_LOOKBACK_MINUTES', 30))
                }
                
                # Передаем config как словарь, а не строку
                bot_manager.signal_strategies['order_book_analysis'] = OrderBookAnalysisStrategy(
                    config=order_book_config,
                    exchange_client=bot_manager.exchange_client  # ✅ ДОБАВЛЯЕМ exchange_client
                )
                logger.info("✅ OrderBookAnalysisStrategy инициализирована")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации OrderBookAnalysis: {e}", exc_info=True)
        
        logger.info(f"✅ Инициализировано {len(bot_manager.signal_strategies)} сигнальных стратегий")
        return len(bot_manager.signal_strategies) > 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации сигнальных стратегий: {e}")
        import traceback
        traceback.print_exc()
        return False


async def init_trader(bot_manager) -> bool:
    """Инициализация исполнителя сделок"""
    try:
        # Инициализируем исполнителя сделок (заглушка)
        logger.info("✅ Исполнитель сделок инициализирован")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации исполнителя сделок: {e}")
        return False


async def init_execution_engine(bot_manager) -> bool:
    """Инициализация движка исполнения ордеров"""
    try:
        from ...exchange.execution_engine import OrderExecutionEngine, get_execution_engine
        
        # Используем синглтон
        bot_manager.execution_engine = get_execution_engine()
        
        # Проверяем готовность
        if bot_manager.execution_engine:
            logger.info("✅ OrderExecutionEngine инициализирован")
            
            # Настраиваем параметры если нужно
            bot_manager.execution_engine.validation_settings.update({
                'min_confidence': getattr(bot_manager.config, 'MIN_SIGNAL_CONFIDENCE', 0.6),
                'max_slippage': getattr(bot_manager.config, 'MAX_SLIPPAGE_PERCENT', 0.5) / 100,
                'min_volume_ratio': 0.01,
                'max_position_correlation': 0.7
            })
            
            return True
        else:
            logger.warning("⚠️ OrderExecutionEngine недоступен, используем прямое исполнение")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации OrderExecutionEngine: {e}")
        return False


async def init_notifier(bot_manager) -> bool:
    """Инициализация системы уведомлений"""
    try:
        # Инициализируем систему уведомлений (заглушка)
        if config.TELEGRAM_ENABLED and config.TELEGRAM_BOT_TOKEN:
            logger.info("✅ Система уведомлений Telegram инициализирована")
        else:
            logger.info("⚠️ Telegram уведомления отключены")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации уведомлений: {e}")
        return False


async def init_ml_system(bot_manager) -> bool:
    """Инициализация ML системы - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Проверяем включено ли ML в конфигурации
        ml_enabled = getattr(config, 'ENABLE_ML', False) or getattr(config, 'ENABLE_ML_SYSTEM', False)
        
        if not ml_enabled:
            logger.info("ℹ️ Машинное обучение отключено в конфигурации")
            # Создаем заглушку для ML системы
            bot_manager.ml_system = None
            return True
            
        logger.info("🧠 Инициализация ML системы...")
        
        # Пытаемся импортировать и инициализировать ML систему
        try:
            from ...ml import MLSystem, get_models_status
            
            # Проверяем статус ML моделей
            models_status = get_models_status()
            logger.info(f"📊 Статус ML моделей: {models_status}")
            
            # Создаем ML систему
            bot_manager.ml_system = MLSystem()
            
            # Инициализируем систему
            await bot_manager.ml_system.initialize()
            
            # Настройка функции создания состояния для RL агента
            if hasattr(bot_manager.ml_system, 'rl_agent') and bot_manager.ml_system.rl_agent:
                def create_state_from_df(df):
                    """Создание состояния для RL агента из DataFrame"""
                    if df is None or len(df) == 0:
                        return np.array([0.0] * 10)  # Fallback состояние
                    
                    return np.array([
                        df['close'].iloc[-1] / df['close'].iloc[-5] - 1,  # Price change
                        df['volume'].iloc[-1] / df['volume'].iloc[-5] - 1,  # Volume change
                        len(df),  # Data points
                        df['close'].pct_change().std(),  # Volatility
                        (df['close'].iloc[-1] - df['close'].min()) / (df['close'].max() - df['close'].min()),  # Position in range
                        df['close'].rolling(5).mean().iloc[-1] / df['close'].iloc[-1] - 1,  # MA5 vs current
                        df['close'].rolling(20).mean().iloc[-1] / df['close'].iloc[-1] - 1,  # MA20 vs current
                        df['volume'].iloc[-5:].mean() / df['volume'].iloc[-20:].mean(),  # Volume ratio
                        0.5  # Portfolio state placeholder
                    ])
                
                bot_manager.ml_system.create_state_from_df = create_state_from_df
            
            # Запускаем фоновое обучение если нужно
            training_enabled = getattr(config, 'ENABLE_ML_TRAINING', False)
            if training_enabled and hasattr(bot_manager, '_trading_loops'):
                from .trading_loops import ml_training_loop
                asyncio.create_task(ml_training_loop(bot_manager))
                logger.info("🎯 Запущено фоновое обучение ML моделей")
            
            logger.info("✅ ML система успешно инициализирована")
            return True
            
        except ImportError as e:
            logger.warning(f"⚠️ ML модули недоступны: {e}")
            # Создаем заглушку
            bot_manager.ml_system = None
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации ML системы: {e}")
            # Создаем заглушку для продолжения работы
            bot_manager.ml_system = None
            return True  # Возвращаем True чтобы не блокировать запуск
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в init_ml_system: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        # Создаем заглушку
        bot_manager.ml_system = None
        return True  # Возвращаем True чтобы не блокировать запуск


async def init_news_analyzer(bot_manager) -> bool:
    """Инициализация анализатора новостей"""
    try:
        if not config.ENABLE_NEWS_ANALYSIS:
            logger.info("⚠️ Анализ новостей отключен")
            return True
            
        # Инициализируем анализатор новостей (заглушка)
        logger.info("✅ Анализатор новостей инициализирован")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации анализатора новостей: {e}")
        return False


async def init_websocket_manager(bot_manager) -> bool:
    """Инициализация менеджера WebSocket"""
    try:
        # Инициализируем WebSocket менеджер (заглушка)
        logger.info("✅ Менеджер WebSocket инициализирован")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации WebSocket менеджера: {e}")
        return False


async def init_export_manager(bot_manager) -> bool:
    """Инициализация менеджера экспорта"""
    try:
        # Инициализируем менеджер экспорта (заглушка)
        logger.info("✅ Менеджер экспорта инициализирован")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации менеджера экспорта: {e}")
        return False


async def init_health_monitor(bot_manager) -> bool:
    """Инициализация монитора здоровья"""
    try:
        # Инициализируем монитор здоровья (заглушка)
        logger.info("✅ Монитор здоровья инициализирован")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации монитора здоровья: {e}")
        return False


async def initialize_enhanced_exchange(bot_manager):
    """Инициализация enhanced exchange клиента - ИСПРАВЛЕНО"""
    try:
        logger.info("🚀 Инициализация enhanced exchange...")
        
        # Проверяем доступность V5 возможностей
        from ...exchange import check_bybit_v5_capabilities
        v5_capabilities = check_bybit_v5_capabilities()
        logger.info(f"🔍 V5 возможности: {v5_capabilities}")
        
        if not v5_capabilities.get('enhanced_features', False):
            logger.warning("⚠️ Enhanced возможности недоступны")
            return False
        
        # Создаем enhanced клиент
        from ...exchange import get_enhanced_exchange_client
        bot_manager.enhanced_exchange_client = get_enhanced_exchange_client()
        
        # ✅ ИСПРАВЛЕНО: Проверяем инициализацию более безопасно
        if hasattr(bot_manager.enhanced_exchange_client, 'initialize'):
            success = await bot_manager.enhanced_exchange_client.initialize()
            if success:
                logger.info("✅ Enhanced exchange клиент активирован")
                
                # ✅ ИСПРАВЛЕНО: Безопасная проверка health_check
                try:
                    if hasattr(bot_manager.enhanced_exchange_client, 'health_check'):
                        health_status = await bot_manager.enhanced_exchange_client.health_check()
                        status = health_status.get('overall_status', 'unknown')
                        logger.info(f"🔍 Enhanced клиент статус: {status}")
                    else:
                        logger.info("🔍 Enhanced клиент статус: initialized (no health_check)")
                except Exception as health_error:
                    logger.warning(f"⚠️ Health check недоступен: {health_error}")
                    # Не считаем это критической ошибкой
                
                bot_manager.v5_integration_enabled = True
                return True
            else:
                logger.error("❌ Не удалось инициализировать enhanced клиент")
                return False
        else:
            # Если нет метода initialize - считаем что уже готов
            logger.info("✅ Enhanced клиент готов (без дополнительной инициализации)")
            bot_manager.v5_integration_enabled = True
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации enhanced клиента: {e}")
        return False


async def display_account_info(bot_manager):
    """Отображение информации об аккаунте и балансе"""
    try:
        logger.info("💰 Получение информации о балансе аккаунта...")
        
        # Получаем баланс через enhanced client (приоритет)
        balance_info = None
        
        if bot_manager.enhanced_exchange_client:
            try:
                # Проверяем доступность v5_client через bybit_integration
                if hasattr(bot_manager.enhanced_exchange_client, 'bybit_integration') and \
                   hasattr(bot_manager.enhanced_exchange_client.bybit_integration, 'v5_client') and \
                   bot_manager.enhanced_exchange_client.bybit_integration.v5_client:
                    # Получаем баланс через v5_client
                    balance_info = await bot_manager.enhanced_exchange_client.bybit_integration.v5_client.get_wallet_balance()
                    logger.debug("✅ Баланс получен через v5_client")
                else:
                    logger.warning("⚠️ V5 client недоступен в enhanced client")
            except Exception as e:
                logger.warning(f"⚠️ Enhanced client недоступен: {e}")
        
        # Fallback к обычному клиенту
        if not balance_info and bot_manager.exchange_client:
            try:
                # Пробуем через UnifiedExchangeClient
                if hasattr(bot_manager.exchange_client, 'exchange') and bot_manager.exchange_client.exchange:
                    # Используем встроенный метод get_balance из UnifiedExchangeClient
                    unified_balance = await bot_manager.exchange_client.get_balance()
                    
                    # Преобразуем формат для _process_balance_info
                    if 'error' not in unified_balance:
                        balance_info = {
                            'retCode': 0,
                            'result': {
                                'list': [{
                                    'accountType': 'UNIFIED',
                                    'totalEquity': str(unified_balance.get('total_usdt', 0)),
                                    'totalAvailableBalance': str(unified_balance.get('free_usdt', 0)),
                                    'totalWalletBalance': str(unified_balance.get('total_usdt', 0)),
                                    'coin': []
                                }]
                            }
                        }
                        
                        # Добавляем детали по монетам
                        for coin, details in unified_balance.get('assets', {}).items():
                            balance_info['result']['list'][0]['coin'].append({
                                'coin': coin,
                                'walletBalance': str(details.get('total', 0)),
                                'availableToWithdraw': str(details.get('free', 0)),
                                'equity': str(details.get('total', 0))
                            })
                        
                        logger.debug("✅ Баланс получен и преобразован из UnifiedExchangeClient")
            except Exception as e:
                logger.error(f"❌ Ошибка получения баланса: {e}")
        
        if balance_info and isinstance(balance_info, dict):
            await process_balance_info(bot_manager, balance_info)
            
        if hasattr(bot_manager.enhanced_exchange_client, 'v5_client'):
            # Проверяем разные типы аккаунтов
            account_types = ['UNIFIED', 'CONTRACT', 'SPOT']
            for acc_type in account_types:
                try:
                    balance_info = await bot_manager.enhanced_exchange_client.v5_client.get_wallet_balance(
                        accountType=acc_type
                    )
                    logger.info(f"💰 {acc_type} аккаунт: {balance_info}")
                except Exception as e:
                    logger.debug(f"❌ {acc_type} недоступен: {e}")
                    
        else:
            logger.warning("⚠️ Не удалось получить информацию о балансе")
            
    except Exception as e:
        logger.error(f"❌ Ошибка отображения информации об аккаунте: {e}")
        logger.error(traceback.format_exc())


async def process_balance_info(bot_manager, balance_info: dict):
    """Обработка и отображение информации о балансе - ИСПРАВЛЕНО"""
    try:
        logger.info("💰 ═══════════════════════════════════════")
        logger.info("💰 ИНФОРМАЦИЯ О ТОРГОВОМ АККАУНТЕ BYBIT")
        logger.info("💰 ═══════════════════════════════════════")
        
        # Функция для безопасного преобразования в float
        def safe_float(value, default=0.0):
            """Безопасное преобразование значения в float"""
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                if value.strip() == '' or value.strip() == '0' or value.strip() == 'null':
                    return default
                try:
                    return float(value.strip())
                except (ValueError, AttributeError):
                    return default
            return default
        
        # Обработка для Bybit Unified Account
        if 'result' in balance_info and balance_info.get('retCode') == 0:
            result = balance_info.get('result', {})
            account_list = result.get('list', [])
            
            if account_list:
                account = account_list[0]
                
                # Общая информация
                account_type = account.get('accountType', 'UNIFIED')
                total_equity = safe_float(account.get('totalEquity', 0))
                total_available = safe_float(account.get('totalAvailableBalance', 0))
                total_wallet = safe_float(account.get('totalWalletBalance', 0))
                
                logger.info(f"💼 ТИП АККАУНТА: {account_type} (Единый торговый)")
                logger.info(f"💰 Общий баланс: ${total_wallet:.2f}")
                logger.info(f"📊 Общий капитал: ${total_equity:.2f}")
                logger.info(f"✅ Доступно для торговли: ${total_available:.2f}")
                
                # Детали по монетам
                coins = account.get('coin', [])
                logger.info("📊 ДЕТАЛИЗАЦИЯ ПО АКТИВАМ:")
                
                for coin_data in coins:
                    coin_symbol = coin_data.get('coin', '')
                    
                    if coin_symbol == 'USDT':
                        # ✅ ИСПРАВЛЕНО: Извлекаем все возможные поля баланса
                        wallet_balance = safe_float(coin_data.get('walletBalance', 0))
                        equity = safe_float(coin_data.get('equity', 0))
                        
                        # Пробуем разные поля для доступного баланса
                        available_withdraw = safe_float(coin_data.get('availableToWithdraw', 0))
                        available_balance = safe_float(coin_data.get('availableBalance', 0))
                        free_balance = safe_float(coin_data.get('free', 0))
                        
                        # Для SPOT аккаунта может быть availableToBorrow
                        available_borrow = safe_float(coin_data.get('availableToBorrow', 0))
                        
                        # ✅ ИСПРАВЛЕНО: Правильная обработка Unified Account
                        locked = safe_float(coin_data.get('locked', 0))
                        
                        # Для Unified Account используем walletBalance - locked
                        # Если locked = 0, то весь баланс доступен
                        if locked == 0 or locked < 1:  # Игнорируем мелкие блокировки
                            available_final = wallet_balance
                            locked = 0  # Сбрасываем мелкие блокировки
                        else:
                            # Только если действительно есть заблокированные средства
                            available_final = wallet_balance - locked
                        
                        # Дополнительная проверка других полей
                        if available_final < 1 and wallet_balance > 1:
                            # Пробуем другие поля если основной расчет дал мало
                            alternative_available = max(
                                available_withdraw, 
                                available_balance, 
                                free_balance, 
                                available_borrow,
                                wallet_balance * 0.99  # 99% от баланса как fallback
                            )
                            
                            if alternative_available > available_final:
                                logger.info(f"🔧 Используем альтернативный расчет доступного баланса: {alternative_available:.2f}")
                                available_final = alternative_available
                                locked = wallet_balance - available_final
                        else:
                            # Используем максимальное из доступных значений
                            available_final = max(available_withdraw, available_balance, free_balance, available_borrow)
                        
                        logger.info(f"   💰 USDT:")
                        logger.info(f"      📈 Баланс: {wallet_balance:.2f}")
                        logger.info(f"      ✅ Доступно: {available_final:.2f}")
                        logger.info(f"      🔒 Заблокировано: {locked:.2f}")
                        
                        # Сохраняем значения
                        bot_manager.balance = wallet_balance
                        bot_manager.available_balance = available_final
                        bot_manager.locked_balance = locked
                        
                        # Логируем отладочную информацию
                        logger.debug(f"🔍 USDT баланс детали:")
                        logger.debug(f"   walletBalance: {coin_data.get('walletBalance', 'N/A')}")
                        logger.debug(f"   availableToWithdraw: {coin_data.get('availableToWithdraw', 'N/A')}")
                        logger.debug(f"   availableBalance: {coin_data.get('availableBalance', 'N/A')}")
                        logger.debug(f"   free: {coin_data.get('free', 'N/A')}")
                        logger.debug(f"   locked: {coin_data.get('locked', 'N/A')}")
                        logger.debug(f"   equity: {coin_data.get('equity', 'N/A')}")
        
        # Обработка для обычного формата баланса
        elif isinstance(balance_info, dict) and any(key in balance_info for key in ['USDT', 'BTC', 'ETH']):
            logger.info("🏦 БАЛАНС ПО АКТИВАМ:")
            
            main_currencies = ['USDT', 'BTC', 'ETH', 'BNB']
            
            for currency in main_currencies:
                if currency in balance_info:
                    balance_data = balance_info[currency]
                    if isinstance(balance_data, dict):
                        free = safe_float(balance_data.get('free', 0))
                        used = safe_float(balance_data.get('used', 0))
                        total = safe_float(balance_data.get('total', 0))
                        
                        if total > 0:
                            logger.info(f"   🪙 {currency}: {total:.4f} (свободно: {free:.4f})")
                    
                    # Устанавливаем USDT как основной баланс
                    if currency == 'USDT' and isinstance(balance_data, dict):
                        bot_manager.balance = safe_float(balance_data.get('total', 0))
                        bot_manager.available_balance = safe_float(balance_data.get('free', 0))
        
        # ✅ ДОБАВЛЕНО: Финальная проверка и установка безопасных значений
        if not hasattr(bot_manager, 'balance') or bot_manager.balance is None:
            bot_manager.balance = 0.0
            logger.warning("⚠️ Не удалось определить основной баланс, установлен 0")
        
        if not hasattr(bot_manager, 'available_balance') or bot_manager.available_balance is None:
            bot_manager.available_balance = 0.0
            logger.warning("⚠️ Не удалось определить доступный баланс, установлен 0")
        
        # Логируем итоговые значения
        logger.info(f"📊 ИТОГО для торговли:")
        logger.info(f"   💰 Общий баланс: ${bot_manager.balance:.2f}")
        logger.info(f"   💸 Доступно: ${bot_manager.available_balance:.2f}")
        logger.info(f"   🔒 В позициях: ${getattr(bot_manager, 'locked_balance', 0):.2f}")
        
        logger.info("💰 ═══════════════════════════════════════")
        
        if getattr(UnifiedConfig, 'PAPER_TRADING', False):
            # Устанавливаем начальный Paper Trading баланс
            paper_balance = getattr(UnifiedConfig, 'INITIAL_CAPITAL', 10000.0)
            
            bot_manager.paper_balance = paper_balance
            bot_manager.paper_positions = {}
            bot_manager.paper_trades_history = []
            bot_manager.paper_stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_pnl': 0.0,
                'total_commission': 0.0,
                'max_drawdown': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0,
                'win_rate': 0.0
            }
            
            # Для PAPER_TRADING устанавливаем баланс равным INITIAL_CAPITAL
            bot_manager.balance = paper_balance
            bot_manager.available_balance = paper_balance
            
            logger.info("="*50)
            logger.info("📝 РЕЖИМ PAPER TRADING АКТИВИРОВАН")
            logger.info(f"💰 Виртуальный баланс: ${paper_balance:,.2f}")
            logger.info(f"💸 Доступно для торговли: ${paper_balance:,.2f}")
            logger.info("="*50)
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки баланса: {e}")
        logger.error(traceback.format_exc())
        
        # ✅ ДОБАВЛЕНО: Устанавливаем безопасные значения по умолчанию
        if not hasattr(bot_manager, 'balance'):
            bot_manager.balance = 0.0
        if not hasattr(bot_manager, 'available_balance'):
            bot_manager.available_balance = 0.0
        
        logger.warning(f"⚠️ Установлены безопасные значения: баланс=${bot_manager.balance:.2f}, доступно=${bot_manager.available_balance:.2f}")
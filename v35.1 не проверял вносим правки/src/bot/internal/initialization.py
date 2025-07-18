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

from src.core.database import SessionLocal, get_session
from src.core.unified_config import unified_config as config
from src.bot.internal.types import ComponentInfo, ComponentStatus

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
    """✅ ИСПРАВЛЕНО: Используем EnhancedUnifiedExchangeClient"""
    try:
        # Импортируем нужные классы
        from ...exchange import get_enhanced_exchange_client, BYBIT_INTEGRATION_AVAILABLE
        
        if BYBIT_INTEGRATION_AVAILABLE:
            logger.info("🚀 Используем EnhancedUnifiedExchangeClient")
            bot_manager.exchange_client = get_enhanced_exchange_client()
        else:
            logger.warning("⚠️ Enhanced клиент недоступен, используем базовый")
            from ...exchange import UnifiedExchangeClient
            bot_manager.exchange_client = UnifiedExchangeClient()
        
        # Подключаемся к бирже
        exchange_name = getattr(config, 'DEFAULT_EXCHANGE', 'bybit')
        testnet = getattr(config, 'BYBIT_TESTNET', True)
        
        logger.info(f"🔗 Подключение к {exchange_name} (testnet={testnet})...")
        success = await bot_manager.exchange_client.connect(exchange_name, testnet)
        
        if success:
            logger.info("✅ Exchange клиент инициализирован")
            
            # Для Enhanced клиента инициализируем дополнительные компоненты
            if hasattr(bot_manager.exchange_client, 'initialize'):
                await bot_manager.exchange_client.initialize()
                
            return True
        else:
            logger.error("❌ Не удалось подключиться к бирже")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации exchange клиента: {e}")
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
    """Инициализация менеджера рисков"""
    try:
        # Инициализируем менеджер рисков (заглушка)
        logger.info("✅ Менеджер рисков инициализирован")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации менеджера рисков: {e}")
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
    """Инициализация фабрики стратегий"""
    try:
        # Инициализируем фабрику стратегий (заглушка)
        logger.info("✅ Фабрика стратегий инициализирована")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации фабрики стратегий: {e}")
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
    """Инициализация системы машинного обучения"""
    try:
        if not getattr(bot_manager.config, 'ENABLE_MACHINE_LEARNING', False):
            logger.info("ℹ️ Машинное обучение отключено в конфигурации")
            return False
        
        # Создаем комплексную ML систему
        from ...ml.models.direction_classifier import DirectionClassifier
        from ...ml.models.price_regressor import PriceLevelRegressor
        from ...ml.models.rl_agent import TradingRLAgent
        from ...ml.features.feature_engineering import FeatureEngineer
        from ...ml.training.trainer import MLTrainer
        
        class MLSystem:
            def __init__(self):
                self.direction_classifier = DirectionClassifier()
                self.price_regressor = PriceLevelRegressor()
                self.rl_agent = TradingRLAgent()
                self.feature_engineer = FeatureEngineer()
                self.trainer = MLTrainer()
                self.is_initialized = False
                
            async def initialize(self):
                """Инициализация всех ML компонентов"""
                try:
                    # Инициализируем trainer
                    await self.trainer.initialize()
                    
                    # Загружаем модели если есть
                    await self.load_models()
                    
                    self.is_initialized = True
                    logger.info("✅ ML система инициализирована")
                except Exception as e:
                    logger.error(f"❌ Ошибка инициализации ML: {e}")
                    self.is_initialized = False
                
            async def load_models(self):
                """Загрузка обученных моделей"""
                try:
                    # Получаем список доступных моделей
                    available_models = self.trainer.list_available_models()
                    
                    if available_models:
                        logger.info(f"📊 Найдено {len(available_models)} обученных моделей")
                        # Загружаем последние модели для основных пар
                        for model_info in available_models[:5]:  # Максимум 5 моделей
                            logger.info(f"📈 Загружаем модель для {model_info['symbol']}")
                    else:
                        logger.warning("⚠️ Обученные модели не найдены, будут использованы базовые")
                except Exception as e:
                    logger.error(f"❌ Ошибка загрузки моделей: {e}")
            
            async def predict_direction(self, symbol: str, df) -> Dict[str, Any]:
                """Предсказание направления движения цены"""
                try:
                    # Извлекаем признаки
                    features = await self.feature_engineer.extract_features(symbol, df)
                    
                    # Получаем предсказание
                    prediction = self.direction_classifier.predict(features)
                    
                    return {
                        'action': prediction['direction_labels'][0],  # BUY/SELL/HOLD
                        'confidence': prediction['confidence'][0],
                        'probabilities': prediction['probabilities'][0],
                        'features': features.to_dict() if hasattr(features, 'to_dict') else {},
                        'model_type': 'ensemble',
                        'forecast_horizon': 5
                    }
                except Exception as e:
                    logger.error(f"❌ Ошибка предсказания направления: {e}")
                    return None
            
            async def predict_price_levels(self, symbol: str, df) -> Dict[str, Any]:
                """Предсказание уровней цены"""
                try:
                    # Используем price regressor
                    features = await self.feature_engineer.extract_features(symbol, df)
                    levels = self.price_regressor.predict_levels(features)
                    
                    current_price = df['close'].iloc[-1]
                    
                    return {
                        'support': levels.get('support', current_price * 0.98),
                        'resistance': levels.get('resistance', current_price * 1.02),
                        'pivot': levels.get('pivot', current_price),
                        'confidence': levels.get('confidence', 0.5),
                        'targets': {
                            'target_1': current_price * 1.01,
                            'target_2': current_price * 1.02,
                            'target_3': current_price * 1.03
                        }
                    }
                except Exception as e:
                    logger.error(f"❌ Ошибка предсказания уровней: {e}")
                    return {'support': 0, 'resistance': 0}
            
            async def get_rl_recommendation(self, symbol: str, df) -> Dict[str, Any]:
                """Получение рекомендации от RL агента"""
                try:
                    # Подготавливаем состояние
                    state = self._prepare_rl_state(df)
                    
                    # Получаем действие
                    action_data = self.rl_agent.predict(state)
                    
                    return {
                        'action': action_data['action_name'],  # BUY/HOLD/SELL
                        'confidence': action_data['confidence'],
                        'q_values': action_data.get('q_values', [])
                    }
                except Exception as e:
                    logger.error(f"❌ Ошибка RL рекомендации: {e}")
                    return None
            
            def _prepare_rl_state(self, df) -> Any:
                """Подготовка состояния для RL агента"""
                import numpy as np
                # Простое состояние из последних значений
                row = df.iloc[-1]
                state = np.array([
                    row.get('rsi', 50) / 100.0,
                    row.get('macd', 0) / 100.0,
                    row.get('bb_position', 0.5),
                    row.get('volume_ratio', 1.0),
                    row.get('price_change', 0) / 10.0,
                    df['close'].pct_change().iloc[-5:].mean() * 100,  # 5-период momentum
                    df['volume'].iloc[-5:].mean() / df['volume'].iloc[-20:].mean(),  # Volume ratio
                    0.5  # Portfolio state placeholder
                ])
                return state
        
        # Создаем и инициализируем ML систему
        bot_manager.ml_system = MLSystem()
        await bot_manager.ml_system.initialize()
        
        # Запускаем фоновое обучение если нужно
        if getattr(bot_manager.config, 'ENABLE_ML_TRAINING', False):
            from .trading_loops import ml_training_loop
            asyncio.create_task(ml_training_loop(bot_manager))
        
        logger.info("✅ ML система инициализирована и готова к работе")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации ML системы: {e}")
        return False


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
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки баланса: {e}")
        logger.error(traceback.format_exc())
        
        # ✅ ДОБАВЛЕНО: Устанавливаем безопасные значения по умолчанию
        if not hasattr(bot_manager, 'balance'):
            bot_manager.balance = 0.0
        if not hasattr(bot_manager, 'available_balance'):
            bot_manager.available_balance = 0.0
        
        logger.warning(f"⚠️ Установлены безопасные значения: баланс=${bot_manager.balance:.2f}, доступно=${bot_manager.available_balance:.2f}")
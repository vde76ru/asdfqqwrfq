"""
Модуль торговых циклов BotManager
Файл: src/bot/internal/trading_loops.py

✅ ОБНОВЛЕНИЯ:
- Правильные циклы анализа сигналов с интервалами из конфига
- Универсальные циклы для стратегий
- Агрегатор сигналов и система уведомлений
- Корректная обработка ошибок и отмена задач
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

from src.bot.internal.types import BotStatus, TradingOpportunity
from src.core.unified_config import unified_config as config

logger = logging.getLogger(__name__)

API_SEMAPHORE = asyncio.Semaphore(3)  # Не более 3 одновременных API запросов
REQUEST_DELAY = 0.2  # 200мс между запросами


def get_trading_loops(bot_instance):
    """Возвращает объект с методами торговых циклов"""
    
    class TradingLoops:
        def __init__(self, bot):
            self.bot = bot
            
        async def _main_trading_loop(self):
            """Главный торговый цикл"""
            return await _main_trading_loop(self.bot)
            
        async def _market_monitoring_loop(self):
            """Цикл мониторинга рынка"""
            return await _market_monitoring_loop(self.bot)
            
        async def _pair_discovery_loop(self):
            """Цикл обнаружения новых торговых пар"""
            return await _pair_discovery_loop(self.bot)
            
        async def _position_management_loop(self):
            """Цикл управления позициями"""
            return await _position_management_loop(self.bot)
            
        async def _risk_monitoring_loop(self):
            """Цикл мониторинга рисков"""
            return await _risk_monitoring_loop(self.bot)
            
        async def _health_monitoring_loop(self):
            """Цикл мониторинга здоровья системы"""
            return await _health_monitoring_loop(self.bot)
            
        async def _performance_tracking_loop(self):
            """Цикл отслеживания производительности"""
            return await _performance_tracking_loop(self.bot)
            
        async def _cleanup_loop(self):
            """Цикл очистки устаревших данных"""
            return await _cleanup_loop(self.bot)
            
        async def _balance_monitoring_loop(self):
            """Цикл мониторинга баланса"""
            return await _balance_monitoring_loop(self.bot)
            
        async def _strategy_evaluation_loop(self):
            """Цикл оценки стратегий"""
            return await _strategy_evaluation_loop(self.bot)
            
        async def _data_collection_loop(self):
            """Цикл сбора данных"""
            return await _data_collection_loop(self.bot)
            
        async def _sentiment_analysis_loop(self):
            """Цикл анализа настроений"""
            return await _sentiment_analysis_loop(self.bot)
            
        async def _event_processing_loop(self):
            """Цикл обработки событий"""
            return await _event_processing_loop(self.bot)
            
        async def start_signal_system_loops(self):
            """Запуск циклов системы сигналов"""
            return await start_signal_system_loops(self.bot)
    
    return TradingLoops(bot_instance)


# === ОСНОВНЫЕ ФУНКЦИИ ЦИКЛОВ ===

async def _main_trading_loop(bot_instance):
    """
    Главный торговый цикл
    Координирует все торговые операции
    """
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            
            if bot_instance.status != BotStatus.RUNNING:
                await asyncio.sleep(1)
                continue
                
            cycle_start = time.time()
            bot_instance.cycles_count += 1
            
            # 1. Анализ рыночных условий
            if hasattr(bot_instance, 'market_analyzer') and hasattr(bot_instance.market_analyzer, 'analyze_market_conditions'):
                if hasattr(bot_instance, 'active_pairs'):
                    for symbol in bot_instance.active_pairs:
                        try:
                            await bot_instance.market_analyzer.analyze_market_conditions(symbol)
                        except Exception as e:
                            logger.error(f"Ошибка анализа рыночных условий для {symbol}: {e}")
            
            # 2. Обновление позиций
            if hasattr(bot_instance, '_position_management') and hasattr(bot_instance._position_management, 'manage_open_positions'):
                await bot_instance._position_management.manage_open_positions()
            
            # 3. Поиск торговых возможностей
            opportunities = []
            try:
                from .market_analysis import _find_all_trading_opportunities
                opportunities = await _find_all_trading_opportunities(bot_instance)
                logger.info(f"🎯 Найдено торговых возможностей: {len(opportunities)}")
            except ImportError:
                logger.debug("Модуль market_analysis недоступен")
            
            # 4. Исполнение лучших сделок
            if opportunities:
                try:
                    from .trade_execution import _execute_best_trades
                    trades_executed = await _execute_best_trades(bot_instance, opportunities)
                    logger.info(f"✅ Исполнено сделок: {trades_executed}")
                except ImportError:
                    logger.debug("Модуль trade_execution недоступен")
            
            # Вычисляем время цикла
            cycle_time = time.time() - cycle_start
            logger.info(f"⏱️ Цикл #{bot_instance.cycles_count} завершен за {cycle_time:.2f}с")
            
            # Адаптивная задержка
            if cycle_time < 30:
                await asyncio.sleep(max(5, 30 - cycle_time))
            
        except asyncio.CancelledError:
            logger.info("🛑 Главный торговый цикл остановлен")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в торговом цикле: {e}")
            await asyncio.sleep(5)


async def _market_monitoring_loop(bot_instance):
    """Цикл мониторинга рынка"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика мониторинга рынка
            logger.debug("📊 Мониторинг рыночных условий...")
            await asyncio.sleep(300)  # 5 минут
        except asyncio.CancelledError:
            logger.info("🛑 Мониторинг рынка остановлен")
            break


async def _pair_discovery_loop(bot_instance):
    """Цикл обновления торговых пар"""
    discovery_interval = getattr(config, 'PAIR_DISCOVERY_INTERVAL_HOURS', 24) * 3600
    
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            logger.debug("🔍 Обновление списка торговых пар...")
            await asyncio.sleep(discovery_interval)
        except asyncio.CancelledError:
            logger.info("🛑 Обнаружение пар остановлено")
            break


async def _position_management_loop(bot_instance):
    """Цикл управления позициями"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            logger.debug("💼 Управление позициями...")
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            logger.info("🛑 Управление позициями остановлено")
            break


async def _risk_monitoring_loop(bot_instance):
    """Цикл мониторинга рисков"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            logger.debug("⚠️ Мониторинг рисков...")
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("🛑 Мониторинг рисков остановлен")
            break


async def _health_monitoring_loop(bot_instance):
    """Цикл мониторинга здоровья"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            if hasattr(bot_instance, '_check_system_health'):
                await bot_instance._check_system_health()
            await asyncio.sleep(120)  # 2 минуты
        except asyncio.CancelledError:
            logger.info("🛑 Мониторинг здоровья остановлен")
            break


async def _performance_tracking_loop(bot_instance):
    """Цикл отслеживания производительности"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            if hasattr(bot_instance, '_track_performance_metrics'):
                await bot_instance._track_performance_metrics()
            await asyncio.sleep(300)  # 5 минут
        except asyncio.CancelledError:
            logger.info("🛑 Отслеживание производительности остановлено")
            break


async def _cleanup_loop(bot_instance):
    """Цикл очистки устаревших данных"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            if hasattr(bot_instance, 'cleanup_old_data'):
                await bot_instance.cleanup_old_data()
            await asyncio.sleep(3600)  # 1 час
        except asyncio.CancelledError:
            logger.info("🛑 Очистка данных остановлена")
            break


async def _balance_monitoring_loop(bot_instance):
    """Цикл мониторинга баланса"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            logger.debug("💰 Мониторинг баланса...")
            await asyncio.sleep(300)  # 5 минут
        except asyncio.CancelledError:
            logger.info("🛑 Мониторинг баланса остановлен")
            break


async def _strategy_evaluation_loop(bot_instance):
    """Цикл оценки стратегий"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            logger.debug("📈 Оценка стратегий...")
            await asyncio.sleep(1800)  # 30 минут
        except asyncio.CancelledError:
            logger.info("🛑 Оценка стратегий остановлена")
            break


async def _data_collection_loop(bot_instance):
    """Цикл сбора данных"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            logger.debug("📊 Сбор данных...")
            await asyncio.sleep(60)  # 1 минута
        except asyncio.CancelledError:
            logger.info("🛑 Сбор данных остановлен")
            break


async def _sentiment_analysis_loop(bot_instance):
    """Цикл анализа настроений"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            logger.debug("😊 Анализ настроений...")
            await asyncio.sleep(600)  # 10 минут
        except asyncio.CancelledError:
            logger.info("🛑 Анализ настроений остановлен")
            break


async def _event_processing_loop(bot_instance):
    """Цикл обработки событий"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            logger.debug("📨 Обработка событий...")
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("🛑 Обработка событий остановлена")
            break


# === ЦИКЛЫ СИСТЕМЫ СИГНАЛОВ ===

async def start_signal_system_loops(bot_instance):
    """
    Запуск циклов системы генерации сигналов
    ✅ ПРАВИЛЬНЫЕ ИНТЕРВАЛЫ ИЗ КОНФИГУРАЦИИ
    """
    logger.info("🚀 Запуск циклов системы сигналов...")
    tasks = []

    try:
        # === ПРОДЮСЕРЫ ДАННЫХ ===
        if hasattr(bot_instance, 'onchain_producer') and bot_instance.onchain_producer:
            task = asyncio.create_task(bot_instance.onchain_producer.start())
            tasks.append(('onchain_producer', task))
            logger.info("▶️ Запущен OnchainDataProducer")

        if hasattr(bot_instance, 'bybit_producer') and bot_instance.bybit_producer:
            task = asyncio.create_task(bot_instance.bybit_producer.start())
            tasks.append(('bybit_producer', task))
            logger.info("▶️ Запущен BybitDataProducer")

        # === АНАЛИТИЧЕСКИЕ СТРАТЕГИИ ===
        if hasattr(bot_instance, 'whale_hunting_strategy') and bot_instance.whale_hunting_strategy:
            interval = int(getattr(config, 'WHALE_HUNTING_INTERVAL', 60))
            task = asyncio.create_task(
                run_strategy_loop(bot_instance.whale_hunting_strategy, interval, "WhaleHunting", bot_instance)
            )

            tasks.append(('whale_hunting', task))
            logger.info(f"▶️ Запущена WhaleHuntingStrategy (интервал: {interval}с)")

        if hasattr(bot_instance, 'sleeping_giants_strategy') and bot_instance.sleeping_giants_strategy:
            interval = int(getattr(config, 'SLEEPING_GIANTS_INTERVAL', 300))
            task = asyncio.create_task(
                run_strategy_loop(bot_instance.sleeping_giants_strategy, interval, "SleepingGiants", bot_instance)
            )
            tasks.append(('sleeping_giants', task))
            logger.info(f"▶️ Запущена SleepingGiantsStrategy (интервал: {interval}с)")

        if hasattr(bot_instance, 'order_book_analysis') and bot_instance.order_book_analysis:
            interval = int(getattr(config, 'ORDER_BOOK_ANALYSIS_INTERVAL', 60))
            task = asyncio.create_task(
                run_strategy_loop(bot_instance.order_book_analysis, interval, "OrderBookAnalysis", bot_instance)
            )
            tasks.append(('order_book', task))
            logger.info(f"▶️ Запущена OrderBookAnalysis (интервал: {interval}с)")
            
        # === ОБНОВЛЕНИЕ МАТРИЦЫ СИГНАЛОВ ===
        interval = int(getattr(config, 'MATRIX_UPDATE_INTERVAL', 30))
        task = asyncio.create_task(
            run_matrix_update_loop(bot_instance, interval)
        )
        tasks.append(('matrix_update', task))
        logger.info(f"+ Запущено обновление матрицы сигналов (интервал: {interval}c)")

        # === АГРЕГАТОР СИГНАЛОВ ===
        if hasattr(bot_instance, 'signal_aggregator') and bot_instance.signal_aggregator:
            interval = int(getattr(config, 'SIGNAL_AGGREGATION_INTERVAL', 60))
            task = asyncio.create_task(
                run_aggregator_loop(bot_instance.signal_aggregator, interval)
            )
            tasks.append(('signal_aggregator', task))
            logger.info(f"▶️ Запущен SignalAggregator (интервал: {interval}с)")

        # === СИСТЕМА УВЕДОМЛЕНИЙ ===
        if hasattr(bot_instance, 'notification_manager') and bot_instance.notification_manager:
            task = asyncio.create_task(
                run_notification_loop(bot_instance.notification_manager)
            )
            tasks.append(('notifications', task))
            logger.info("▶️ Запущена система уведомлений")

        # Сохраняем задачи в bot_instance
        if not hasattr(bot_instance, 'signal_tasks'):
            bot_instance.signal_tasks = []
        bot_instance.signal_tasks.extend(tasks)
        
        logger.info(f"✅ Запущено {len(tasks)} циклов анализа сигналов")

    except Exception as e:
        logger.error(f"❌ Ошибка запуска циклов анализа: {e}")
        # Отменяем все запущенные задачи
        for name, task in tasks:
            task.cancel()


async def run_strategy_loop(strategy, interval: int, name: str, bot_instance):
    """Универсальный цикл для запуска стратегии с передачей данных"""
    logger.info(f"▶️ Запуск цикла {name} с интервалом {interval}с")
    
    while True:
        try:
            await asyncio.sleep(interval)  # ✅ Сначала ждем интервал
            
            async with API_SEMAPHORE:  # ✅ Потом захватываем семафор
                logger.debug(f"  {name}: начало цикла анализа")
                
                if hasattr(strategy, 'analyze'):
                    if hasattr(bot_instance, 'active_pairs'):
                        for symbol in bot_instance.active_pairs:
                            try:
                                # ✅ ИСПРАВЛЕНИЕ: Получаем exchange_client
                                exchange_client = bot_instance.exchange_client or getattr(bot_instance, 'enhanced_exchange_client', None)
                                
                                # ✅ Проверяем сигнатуру метода analyze
                                import inspect
                                sig = inspect.signature(strategy.analyze)
                                params = sig.parameters
                                
                                # ✅ Если метод принимает exchange_client, передаем его
                                if 'exchange_client' in params:
                                    signals = await strategy.analyze(symbol, exchange_client=exchange_client)
                                else:
                                    signals = await strategy.analyze(symbol=symbol)
                                
                                if signals:
                                    if isinstance(signals, dict) and 'signals' in signals:
                                        num_signals = len(signals['signals'])
                                        if num_signals > 0:
                                            logger.info(f" {name} ({symbol}): сгенерировано {num_signals} сигналов")
                                    elif isinstance(signals, list) and len(signals) > 0:
                                        logger.info(f" {name} ({symbol}): сгенерировано {len(signals)} сигналов")
                            except Exception as pair_e:
                                logger.error(f"❌ {name}: ошибка анализа пары {symbol}: {pair_e}", exc_info=False)
                
                elif hasattr(strategy, 'run'):
                    await strategy.run()
                else:
                    logger.warning(f"  {name}: не найден подходящий метод запуска")
                    break
                
                await asyncio.sleep(REQUEST_DELAY)  # ✅ Задержка внутри семафора
                
        except asyncio.CancelledError:
            logger.info(f"  {name}: остановка цикла")
            break
        except Exception as e:
            logger.error(f"❌ {name}: ошибка в цикле: {e}", exc_info=True)
            await asyncio.sleep(interval * 2)


async def run_aggregator_loop(aggregator, interval: int):
    """Цикл для агрегатора сигналов"""
    logger.info(f"🔄 Запуск цикла SignalAggregator с интервалом {interval}с")
    
    while True:
        try:
            logger.debug("🔄 SignalAggregator: агрегация сигналов")
            
            if hasattr(aggregator, 'aggregate_signals'):
                await aggregator.aggregate_signals()
            elif hasattr(aggregator, 'run'):
                await aggregator.run()
            
            await asyncio.sleep(interval)
            
        except asyncio.CancelledError:
            logger.info("🛑 SignalAggregator: остановка")
            break
        except Exception as e:
            logger.error(f"❌ SignalAggregator: ошибка: {e}")
            await asyncio.sleep(interval * 2)
            
async def run_matrix_update_loop(bot_instance, interval: int):
    """Цикл обновления матрицы сигналов"""
    logger.info(f"📊 Запуск цикла обновления матрицы с интервалом {interval}c")  # ✅ Исправлено: добавлен эмодзи
    while True:
        try:
            await asyncio.sleep(interval)
            await bot_instance.update_signals_matrix()
        except asyncio.CancelledError:
            logger.info("🛑 Цикл обновления матрицы остановлен")  # ✅ Исправлено: правильный символ
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле обновления матрицы: {e}")  # ✅ Исправлено: правильный символ
            await asyncio.sleep(interval)


async def run_notification_loop(notification_manager):
    """Цикл для системы уведомлений"""
    check_interval = 60  # Проверка каждую минуту
    daily_summary_sent = False
    logger.info(f"🔄 Запуск цикла уведомлений с интервалом {check_interval}с")
    
    while True:
        try:
            # Проверка и отправка уведомлений о сигналах
            if hasattr(notification_manager, 'check_and_send_notifications'):
                await notification_manager.check_and_send_notifications()
            
            # Ежедневная сводка в 00:00 UTC
            current_hour = datetime.utcnow().hour
            if current_hour == 0 and not daily_summary_sent:
                if hasattr(notification_manager, 'send_daily_summary'):
                    await notification_manager.send_daily_summary()
                daily_summary_sent = True
            elif current_hour != 0:
                daily_summary_sent = False
            
            await asyncio.sleep(check_interval)
            
        except asyncio.CancelledError:
            logger.info("🛑 NotificationManager: остановка")
            break
        except Exception as e:
            logger.error(f"❌ NotificationManager: ошибка: {e}")
            await asyncio.sleep(check_interval * 2)


async def _start_all_trading_loops(bot_instance):
    """Запуск всех торговых циклов"""
    try:
        logger.info("🔄 Запуск всех торговых циклов...")
        
        if not hasattr(bot_instance, 'tasks'):
            bot_instance.tasks = {}
        
        # Основной торговый цикл
        bot_instance.tasks['main_trading'] = asyncio.create_task(
            _main_trading_loop(bot_instance), name="main_trading"
        )
        
        # Цикл мониторинга рынка
        bot_instance.tasks['market_monitoring'] = asyncio.create_task(
            _market_monitoring_loop(bot_instance), name="market_monitoring"
        )
        
        # Цикл обновления торговых пар
        bot_instance.tasks['pair_discovery'] = asyncio.create_task(
            _pair_discovery_loop(bot_instance), name="pair_discovery"
        )
        
        # Цикл управления позициями
        bot_instance.tasks['position_management'] = asyncio.create_task(
            _position_management_loop(bot_instance), name="position_management"
        )
        
        # Цикл мониторинга рисков
        bot_instance.tasks['risk_monitoring'] = asyncio.create_task(
            _risk_monitoring_loop(bot_instance), name="risk_monitoring"
        )
        
        # Цикл мониторинга здоровья
        bot_instance.tasks['health_monitoring'] = asyncio.create_task(
            _health_monitoring_loop(bot_instance), name="health_monitoring"
        )
        
        # Цикл отслеживания производительности
        bot_instance.tasks['performance_tracking'] = asyncio.create_task(
            _performance_tracking_loop(bot_instance), name="performance_tracking"
        )
        
        # Цикл очистки данных
        bot_instance.tasks['cleanup'] = asyncio.create_task(
            _cleanup_loop(bot_instance), name="cleanup"
        )
        
        # Цикл мониторинга баланса
        bot_instance.tasks['balance_monitoring'] = asyncio.create_task(
            _balance_monitoring_loop(bot_instance), name="balance_monitoring"
        )
        
        # Цикл оценки стратегий
        bot_instance.tasks['strategy_evaluation'] = asyncio.create_task(
            _strategy_evaluation_loop(bot_instance), name="strategy_evaluation"
        )
        
        # Цикл сбора данных
        bot_instance.tasks['data_collection'] = asyncio.create_task(
            _data_collection_loop(bot_instance), name="data_collection"
        )
        
        # === ДОБАВЛЯЕМ ЗАПУСК СИСТЕМЫ СИГНАЛОВ ===
        # Запускаем циклы системы сигналов
        await start_signal_system_loops(bot_instance)
        
        logger.info(f"✅ Запущено {len(bot_instance.tasks)} торговых циклов")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске торговых циклов: {e}")
        raise


async def start_all_trading_loops(bot_instance):
    """Публичный метод для запуска всех циклов"""
    return await _start_all_trading_loops(bot_instance)


async def stop_all_trading_loops(bot_instance):
    """Остановка всех торговых циклов"""
    logger.info("🛑 Остановка всех торговых циклов...")
    
    # Устанавливаем флаг остановки
    if hasattr(bot_instance, '_stop_event'):
        bot_instance._stop_event.set()
    
    # Отменяем все задачи
    if hasattr(bot_instance, 'tasks'):
        for name, task in bot_instance.tasks.items():
            if not task.done():
                logger.info(f"🛑 Отмена задачи: {name}")
                task.cancel()
        
        # Ждем завершения задач
        await asyncio.gather(*bot_instance.tasks.values(), return_exceptions=True)
        bot_instance.tasks.clear()
    
    # Отменяем задачи сигналов
    if hasattr(bot_instance, 'signal_tasks'):
        for name, task in bot_instance.signal_tasks:
            if not task.done():
                logger.info(f"🛑 Отмена задачи сигналов: {name}")
                task.cancel()
        
        # Ждем завершения задач сигналов
        tasks = [task for _, task in bot_instance.signal_tasks]
        await asyncio.gather(*tasks, return_exceptions=True)
        bot_instance.signal_tasks.clear()
    
    logger.info("✅ Все торговые циклы остановлены")
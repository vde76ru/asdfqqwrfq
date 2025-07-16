"""
Модуль торговых циклов BotManager
Файл: src/bot/internal/trading_loops.py

Все торговые циклы и мониторинг
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List

from .types import BotStatus, TradingOpportunity

logger = logging.getLogger(__name__)


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
            await bot_instance._analyze_market_conditions()
            
            # 2. Обновление позиций
            await bot_instance._update_all_positions()
            
            # 3. Поиск торговых возможностей
            from .market_analysis import _find_all_trading_opportunities
            opportunities = await _find_all_trading_opportunities(bot_instance)
            logger.info(f"🎯 Найдено торговых возможностей: {len(opportunities)}")
            
            # 4. Исполнение лучших сделок
            if opportunities:
                from .trade_execution import _execute_best_trades
                trades_executed = await _execute_best_trades(bot_instance, opportunities)
                logger.info(f"✅ Исполнено сделок: {trades_executed}")
            
            # Вычисляем время цикла
            cycle_time = time.time() - cycle_start
            logger.info(f"⏱️ Цикл #{bot_instance.cycles_count} завершен за {cycle_time:.2f}с, сделок: 0")
            
            # Адаптивная задержка - если цикл быстрый, добавляем паузу
            if cycle_time < 30:
                await asyncio.sleep(max(5, 30 - cycle_time))  # Минимум 30 секунд между циклами
            
        except Exception as e:
            logger.error(f"❌ Ошибка в торговом цикле: {e}")
            await asyncio.sleep(5)


async def _market_monitoring_loop(bot_instance):
    """Цикл мониторинга рынка"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика мониторинга рынка
            await asyncio.sleep(300)  # 5 минут
        except asyncio.CancelledError:
            break


async def _pair_discovery_loop(bot_instance):
    """Цикл обновления торговых пар"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика обновления пар
            await asyncio.sleep(bot_instance.config.PAIR_DISCOVERY_INTERVAL_HOURS * 3600)
        except asyncio.CancelledError:
            break


async def _position_management_loop(bot_instance):
    """Цикл управления позициями"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика управления позициями
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            break


async def _risk_monitoring_loop(bot_instance):
    """Цикл мониторинга рисков"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика мониторинга рисков
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break


async def _health_monitoring_loop(bot_instance):
    """Цикл мониторинга здоровья"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            await bot_instance._check_system_health()
            await asyncio.sleep(120)  # 2 минуты
        except asyncio.CancelledError:
            break


async def _performance_tracking_loop(bot_instance):
    """Цикл отслеживания производительности"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            await bot_instance._track_performance_metrics()
            await asyncio.sleep(300)  # 5 минут
        except asyncio.CancelledError:
            break


async def _cleanup_loop(bot_instance):
    """Цикл очистки устаревших данных"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            await bot_instance.cleanup_old_data()
            await asyncio.sleep(3600)  # 1 час
        except asyncio.CancelledError:
            break


async def _balance_monitoring_loop(bot_instance):
    """Цикл мониторинга баланса"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика мониторинга баланса
            await asyncio.sleep(300)  # 5 минут
        except asyncio.CancelledError:
            break


async def _strategy_evaluation_loop(bot_instance):
    """Цикл оценки стратегий"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика оценки стратегий
            await asyncio.sleep(1800)  # 30 минут
        except asyncio.CancelledError:
            break


async def _data_collection_loop(bot_instance):
    """Цикл сбора данных"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика сбора данных
            await asyncio.sleep(60)  # 1 минута
        except asyncio.CancelledError:
            break


async def _sentiment_analysis_loop(bot_instance):
    """Цикл анализа настроений"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика анализа настроений
            await asyncio.sleep(600)  # 10 минут
        except asyncio.CancelledError:
            break


async def _event_processing_loop(bot_instance):
    """Цикл обработки событий"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика обработки событий
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            break


async def start_signal_system_loops(bot_instance):
    """Запуск циклов системы генерации сигналов"""
    logger.info("Запуск циклов системы сигналов...")

    # === ПРОДЮСЕРЫ ДАННЫХ ===
    if bot_instance.onchain_producer:
        bot_instance.tasks['onchain_producer'] = asyncio.create_task(bot_instance.onchain_producer.start())
    if bot_instance.bybit_producer:
        bot_instance.tasks['bybit_producer'] = asyncio.create_task(bot_instance.bybit_producer.start())

    # === АНАЛИТИЧЕСКИЕ МОДУЛИ ===
    if bot_instance.whale_hunting_strategy:
        bot_instance.tasks['whale_hunting'] = asyncio.create_task(bot_instance.whale_hunting_strategy.start())
    
    if bot_instance.sleeping_giants_strategy:
        bot_instance.tasks['sleeping_giants'] = asyncio.create_task(bot_instance.sleeping_giants_strategy.start())

    if bot_instance.order_book_analysis:
        bot_instance.tasks['order_book_analysis'] = asyncio.create_task(bot_instance.order_book_analysis.start())
        
    if bot_instance.signal_aggregator:
        bot_instance.tasks['signal_aggregator'] = asyncio.create_task(bot_instance.signal_aggregator.start())

    # === УВЕДОМЛЕНИЯ ===
    if bot_instance.notification_manager:
        bot_instance.tasks['notification_manager'] = asyncio.create_task(bot_instance.notification_manager.check_and_send_notifications_loop())
        bot_instance.tasks['daily_summary'] = asyncio.create_task(bot_instance.notification_manager.send_daily_summary_loop())

    logger.info("Все циклы системы сигналов запущены")


async def _whale_hunting_analysis_loop(bot_instance):
    """
    Периодический цикл анализа стратегии "Охота на китов"
    Запускается каждые 30-60 секунд для анализа новых транзакций
    """
    analysis_interval = 30  # секунд
    
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            
            if bot_instance.whale_hunting_strategy:
                logger.info("🐋 Запуск анализа WhaleHuntingStrategy...")
                
                # Выполняем анализ
                signals = await bot_instance.whale_hunting_strategy.analyze()
                
                if signals:
                    logger.info(f"🎯 WhaleHuntingStrategy сгенерировала {len(signals)} сигналов")
                else:
                    logger.debug("🔍 WhaleHuntingStrategy не обнаружила новых сигналов")
            
            # Ждем перед следующим циклом
            await asyncio.sleep(analysis_interval)
            
        except asyncio.CancelledError:
            logger.info("🛑 Остановка цикла WhaleHuntingStrategy")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле WhaleHuntingStrategy: {e}")
            await asyncio.sleep(60)  # Увеличенная пауза при ошибке


async def _start_all_trading_loops(bot_instance):
    """Запуск всех торговых циклов"""
    try:
        logger.info("🔄 Запуск всех торговых циклов...")
        
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

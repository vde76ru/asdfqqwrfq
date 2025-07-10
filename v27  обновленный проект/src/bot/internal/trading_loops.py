"""
Основные торговые циклы BotManager
Файл: src/bot/internal/trading_loops.py
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

async def _main_trading_loop(bot_instance):
    """Главный торговый цикл - С КОНТРОЛЕМ RATE LIMITS"""
    logger.info("🚀 Запуск главного торгового цикла...")
    
    last_request_times = defaultdict(lambda: 0)
    
    while bot_instance.is_running and bot_instance.status == bot_instance.BotStatus.RUNNING:
        try:
            bot_instance.cycles_count += 1
            
            # Отправляем обновление статуса через WebSocket каждые 5 циклов
            if bot_instance.cycles_count % 5 == 0:
                bot_instance.emit_status_update()

            cycle_start = time.time()
            
            logger.info(f"🔄 Цикл #{bot_instance.cycles_count} - анализ {len(bot_instance.active_pairs)} пар")
            
            # === КОНТРОЛЬ RATE LIMITS ===
            # Bybit limits: 120 requests per minute для spot
            max_requests_per_minute = 100
            min_request_interval = 60.0 / max_requests_per_minute  # ~0.6 секунды
            
            # 1. Управление позициями
            from .position_management import _manage_all_positions
            await _manage_all_positions(bot_instance)
            await asyncio.sleep(0.1)  # ✅ Уменьшена задержка
            
            # 2. Обновление рыночных данных ПАРАЛЛЕЛЬНО для ускорения
            from .market_analysis import _update_market_data_for_symbol
            update_tasks = []
            for symbol in bot_instance.active_pairs:
                # Создаем задачи для параллельного обновления
                task = asyncio.create_task(_update_market_data_for_symbol(bot_instance, symbol))
                update_tasks.append(task)
                
                # Небольшая задержка между запусками для rate limit
                await asyncio.sleep(0.05)
            
            # Ждем завершения всех обновлений
            if update_tasks:
                await asyncio.gather(*update_tasks, return_exceptions=True)
            
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
            from .monitoring import _perform_health_check
            health_status = await _perform_health_check(bot_instance)
            # Обработка результатов проверки здоровья
            await asyncio.sleep(300)  # 5 минут
        except asyncio.CancelledError:
            break

async def _performance_monitoring_loop(bot_instance):
    """Цикл мониторинга производительности"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика мониторинга производительности
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break

async def _data_export_loop(bot_instance):
    """Цикл экспорта данных"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика экспорта данных
            await asyncio.sleep(3600)  # 1 час
        except asyncio.CancelledError:
            break

async def _ml_training_loop(bot_instance):
    """Фоновый цикл обучения ML моделей"""
    while not bot_instance._stop_event.is_set():
        try:
            # Ждем заданный интервал
            interval = getattr(bot_instance.config, 'ML_MODEL_RETRAIN_INTERVAL', 86400)  # 24 часа
            await asyncio.sleep(interval)
            
            if bot_instance._stop_event.is_set():
                break
            
            logger.info("🎓 Запуск переобучения ML моделей...")
            
            # Обучаем модели для активных пар
            if hasattr(bot_instance, 'ml_system') and bot_instance.ml_system and hasattr(bot_instance.ml_system, 'trainer'):
                for symbol in list(bot_instance.active_pairs)[:5]:  # Максимум 5 пар
                    try:
                        logger.info(f"🎓 Обучение модели для {symbol}...")
                        result = await bot_instance.ml_system.trainer.train_symbol_model(symbol)
                        
                        if result.get('success'):
                            logger.info(f"✅ Модель для {symbol} обучена успешно")
                        else:
                            logger.warning(f"⚠️ Не удалось обучить модель для {symbol}")
                        
                        # Пауза между обучениями
                        await asyncio.sleep(300)  # 5 минут
                        
                    except Exception as e:
                        logger.error(f"❌ Ошибка обучения для {symbol}: {e}")
        
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в ML training loop: {e}")

async def _ml_prediction_loop(bot_instance):
    """Цикл ML предсказаний"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика ML предсказаний
            await asyncio.sleep(300)  # 5 минут
        except asyncio.CancelledError:
            break

async def _news_collection_loop(bot_instance):
    """Цикл сбора новостей"""
    while not bot_instance._stop_event.is_set():
        try:
            await bot_instance._pause_event.wait()
            # Логика сбора новостей
            await asyncio.sleep(1800)  # 30 минут
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
        
        # Цикл обновления производительности
        bot_instance.tasks['performance_monitoring'] = asyncio.create_task(
            _performance_monitoring_loop(bot_instance), name="performance_monitoring"
        )
        
        # Цикл экспорта данных
        bot_instance.tasks['data_export'] = asyncio.create_task(
            _data_export_loop(bot_instance), name="data_export"
        )
        
        # Циклы машинного обучения (если включено)
        if bot_instance.config.ENABLE_MACHINE_LEARNING:
            bot_instance.tasks['ml_training'] = asyncio.create_task(
                _ml_training_loop(bot_instance), name="ml_training"
            )
            bot_instance.tasks['ml_prediction'] = asyncio.create_task(
                _ml_prediction_loop(bot_instance), name="ml_prediction"
            )
        
        # Циклы анализа новостей (если включено)
        if bot_instance.config.ENABLE_NEWS_ANALYSIS:
            bot_instance.tasks['news_collection'] = asyncio.create_task(
                _news_collection_loop(bot_instance), name="news_collection"
            )
            bot_instance.tasks['sentiment_analysis'] = asyncio.create_task(
                _sentiment_analysis_loop(bot_instance), name="sentiment_analysis"
            )
        
        # Цикл обработки событий
        bot_instance.tasks['event_processing'] = asyncio.create_task(
            _event_processing_loop(bot_instance), name="event_processing"
        )
        
        # Инициализируем здоровье задач
        for task_name in bot_instance.tasks:
            bot_instance.task_health[task_name] = 'starting'
        
        logger.info(f"✅ Запущено {len(bot_instance.tasks)} торговых циклов")
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска торговых циклов: {e}")
        raise
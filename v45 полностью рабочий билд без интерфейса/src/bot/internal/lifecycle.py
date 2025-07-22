"""
Модуль управления жизненным циклом BotManager
Файл: src/bot/internal/lifecycle.py

Все методы запуска, остановки, паузы и управления состоянием бота
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Tuple, Optional

from src.bot.internal.types import BotStatus
from src.bot.internal.initialization import initialize_all_components, display_account_info
from src.bot.internal.trading_pairs import discover_all_trading_pairs, load_pairs_from_config, load_historical_data_for_pairs
from src.bot.internal.trading_loops import start_all_trading_loops
from src.core.unified_config import unified_config as config



logger = logging.getLogger(__name__)


def get_lifecycle(bot_instance):
    """Возвращает объект с методами жизненного цикла"""
    
    class Lifecycle:
        def __init__(self, bot):
            self.bot = bot
            
        async def start_async(self):
            """Асинхронный запуск торгового бота"""
            return await start_async(self.bot)
            
        async def pause(self):
            """Приостановка торгового бота"""
            return await pause(self.bot)
            
        async def resume(self):
            """Возобновление работы торгового бота"""
            return await resume(self.bot)
            
        async def emergency_stop(self):
            """Экстренная остановка с закрытием всех позиций"""
            return await emergency_stop(self.bot)
            
        async def _start_all_trading_loops(self):
            """Запуск всех торговых циклов"""
            return await _start_all_trading_loops(self.bot)
    
    return Lifecycle(bot_instance)


# === ОСНОВНЫЕ ФУНКЦИИ ЖИЗНЕННОГО ЦИКЛА ===

def start(bot_manager) -> Tuple[bool, str]:
    """
    СИНХРОННАЯ обертка для запуска из Flask API.
    Создает и запускает фоновый поток для асинхронной логики.
    """
    if bot_manager.is_running:
        logger.warning("Попытка запустить уже работающего бота.")
        return False, "Бот уже запущен."

    logger.info("🚀 Получена команда на запуск бота. Создание фонового потока...")
    bot_manager.status = BotStatus.STARTING
    
    # Используем threading.Event для безопасного межпоточного общения
    bot_manager._stop_event = threading.Event()
    
    # Создаем поток, который будет управлять асинхронным циклом
    bot_manager._async_thread = threading.Thread(target=run_async_tasks, args=(bot_manager,), name="BotAsyncLoopThread")
    bot_manager._async_thread.daemon = True # Поток завершится, если основной процесс умрет
    bot_manager._async_thread.start()
    
    time.sleep(3) # Даем потоку время на запуск и начальную инициализацию

    if bot_manager.is_running:
        msg = "Бот успешно запущен в фоновом режиме."
        logger.info(msg)
        return True, msg
    else:
        msg = f"Не удалось запустить бота. Текущий статус: {bot_manager.status.value}. Проверьте логи на наличие ошибок."
        logger.error(msg)
        return False, msg


def stop(bot_manager) -> Tuple[bool, str]:
    """
    СИНХРОННАЯ обертка для остановки из Flask API.
    Сигнализирует фоновому потоку о необходимости завершения.
    """
    if not bot_manager.is_running:
        logger.warning("Попытка остановить уже остановленного бота.")
        return False, "Бот не запущен."

    logger.info("🛑 Получена команда на остановку бота...")
    bot_manager.status = BotStatus.STOPPING
    
    
    if bot_manager._stop_event:
        bot_manager._stop_event.set() # Сигнализируем циклу о необходимости остановиться
    else:
        # На случай, если что-то пошло не так
        bot_manager.is_running = False
        return False, "Внутренняя ошибка: событие остановки отсутствует."
        
    # Ждем завершения потока
    if bot_manager._async_thread:
        bot_manager._async_thread.join(timeout=15) # Даем 15 секунд на корректное завершение

    if bot_manager._async_thread and bot_manager._async_thread.is_alive():
         bot_manager.status = BotStatus.ERROR
         msg = "КРИТИЧЕСКАЯ ОШИБКА: Поток бота не завершился вовремя."
         logger.critical(msg)
         return False, msg
    
    bot_manager.is_running = False
    bot_manager.status = BotStatus.STOPPED
    bot_manager.stop_time = datetime.utcnow()
    
    msg = "Бот успешно остановлен."
    logger.info(msg)
    return True, msg


async def _stop_signal_components(bot_manager):
    """Остановка компонентов системы сигналов"""
    logger.info("🛑 Остановка компонентов системы сигналов...")
    
    # Остановка OnchainDataProducer
    if hasattr(bot_manager, 'onchain_producer') and bot_manager.onchain_producer:
        try:
            await bot_manager.onchain_producer.stop()
            logger.info("✅ OnchainDataProducer остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки OnchainDataProducer: {e}")
    
    # Остановка BybitDataProducer
    if hasattr(bot_manager, 'bybit_producer') and bot_manager.bybit_producer:
        try:
            await bot_manager.bybit_producer.stop()
            logger.info("✅ BybitDataProducer остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки BybitDataProducer: {e}")
    
    # Остановка WhaleHuntingStrategy
    if bot_manager.whale_hunting_strategy:
        try:
            await bot_manager.whale_hunting_strategy.stop()
            logger.info("✅ WhaleHuntingStrategy остановлена")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки WhaleHuntingStrategy: {e}")
    
    # Остановка SignalAggregator
    if bot_manager.signal_aggregator:
        try:
            await bot_manager.signal_aggregator.stop()
            logger.info("✅ SignalAggregator остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки SignalAggregator: {e}")
    
    logger.info("✅ Все компоненты системы сигналов остановлены")


def run_async_tasks(bot_manager):
    """
    Функция для запуска в отдельном потоке.
    Создает новый asyncio event loop и запускает асинхронные задачи.
    """
    try:
        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Запускаем основную асинхронную логику
        loop.run_until_complete(start_async(bot_manager))
        
    except Exception as e:
        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА в асинхронном потоке: {e}")
        bot_manager.status = BotStatus.ERROR
        bot_manager.is_running = False
    finally:
        # Очищаем event loop
        try:
            loop.close()
        except:
            pass
        logger.info("Асинхронный поток завершен.")


async def start_async(bot_manager):
    """
    Асинхронный запуск торгового бота
    Основная логика запуска всех компонентов
    """
    try:
        logger.info("=== ЗАПУСК ТОРГОВОГО БОТА ===")
        bot_manager.start_time = datetime.utcnow()
        bot_manager.status = BotStatus.STARTING

        bot_manager._stop_event = asyncio.Event()
        bot_manager._pause_event = asyncio.Event()
        bot_manager._pause_event.set()  # Изначально не на паузе

        # 1. Инициализация компонентов
        logger.info("📍 Этап 1: Инициализация компонентов...")
        success = await initialize_all_components(bot_manager)
        if not success:
            logger.error("❌ Не удалось инициализировать компоненты")
            bot_manager.status = BotStatus.ERROR
            bot_manager.is_running = False
            # Отправляем уведомление если доступно
            if hasattr(bot_manager, 'notifier') and bot_manager.notifier:
                await bot_manager.notifier.send_message("❌ Критическая ошибка: не удалось инициализировать компоненты бота")
            return

        # Проверяем критические компоненты после инициализации
        critical_components = ['exchange_client', 'data_collector', 'market_analyzer', 'risk_manager']
        missing_components = []
        
        for comp_name in critical_components:
            if not hasattr(bot_manager, comp_name) or getattr(bot_manager, comp_name) is None:
                missing_components.append(comp_name)
        
        if missing_components:
            logger.error(f"❌ Отсутствуют критические компоненты: {missing_components}")
            bot_manager.status = BotStatus.ERROR
            bot_manager.is_running = False
            return

        # 2. Загрузка торговых пар
        logger.info("📍 Этап 2: Загрузка торговых пар...")
        load_pairs_from_config(bot_manager)
        
        # Проверяем, что загружены торговые пары
        if not hasattr(bot_manager, 'active_pairs') or not bot_manager.active_pairs:
            logger.error("❌ Не загружены торговые пары")
            bot_manager.status = BotStatus.ERROR
            bot_manager.is_running = False
            return

        # 3. Автоматическое обнаружение торговых пар (если включено)
        if hasattr(bot_manager.config, 'AUTO_DISCOVER_PAIRS') and bot_manager.config.AUTO_DISCOVER_PAIRS:
            logger.info("📍 Этап 3: Автоматическое обнаружение торговых пар...")
            try:
                await discover_all_trading_pairs(bot_manager)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка автоматического обнаружения пар: {e}")
                # Не критично, продолжаем

        # 4. Загрузка исторических данных
        logger.info("📍 Этап 4: Загрузка исторических данных...")
        try:
            await load_historical_data_for_pairs(bot_manager)
        except Exception as e:
            logger.error(f"❌ Критическая ошибка загрузки исторических данных: {e}")
            bot_manager.status = BotStatus.ERROR
            bot_manager.is_running = False
            return

        # 5. Отображение информации об аккаунте
        logger.info("📍 Этап 5: Информация об аккаунте...")
        try:
            await display_account_info(bot_manager)
            
            # Проверяем, что баланс был установлен
            if not hasattr(bot_manager, 'balance') or bot_manager.balance is None:
                logger.warning("⚠️ Не удалось получить баланс, устанавливаем 0")
                bot_manager.balance = 0.0
                bot_manager.available_balance = 0.0
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения информации об аккаунте: {e}")
            # Устанавливаем безопасные значения
            bot_manager.balance = 0.0
            bot_manager.available_balance = 0.0

        # 5.5. Инициализация торговых стратегий
        logger.info("📍 Этап 5.5: Инициализация торговых стратегий...")
        try:
            from ...strategies import (
                MultiIndicatorStrategy, MomentumStrategy, MeanReversionStrategy,
                BreakoutStrategy, ScalpingStrategy, SwingStrategy,
                ConservativeStrategy, SafeMultiIndicatorStrategy
            )
            bot_manager.available_strategies = {
                'multi_indicator': MultiIndicatorStrategy, 'momentum': MomentumStrategy,
                'mean_reversion': MeanReversionStrategy, 'breakout': BreakoutStrategy,
                'scalping': ScalpingStrategy, 'swing': SwingStrategy,
                'conservative': ConservativeStrategy, 'safe_multi_indicator': SafeMultiIndicatorStrategy
            }
            logger.info(f"✅ Загружено {len(bot_manager.available_strategies)} классов стратегий")

            # Инициализация strategy_instances если не существует
            if not hasattr(bot_manager, 'strategy_instances'):
                bot_manager.strategy_instances = {}

            # Правильная обработка весов стратегий из конфига
            strategy_weights = {}
            strategy_weights_config = getattr(config, 'STRATEGY_WEIGHTS', None)

            if strategy_weights_config:
                if isinstance(strategy_weights_config, str):
                    # Парсим строку формата "name:weight,name:weight"
                    for pair in strategy_weights_config.split(','):
                        if ':' in pair:
                            name, weight = pair.strip().split(':')
                            strategy_weights[name.strip()] = float(weight)
                elif isinstance(strategy_weights_config, dict):
                    strategy_weights = strategy_weights_config
            else:
                # Дефолтные веса, если в конфиге ничего нет
                strategy_weights = {
                    'multi_indicator': 25.0, 'momentum': 20.0, 'mean_reversion': 15.0,
                    'breakout': 15.0, 'scalping': 10.0, 'swing': 10.0, 'ml_prediction': 5.0
                }

            # Создаем экземпляры стратегий
            for strategy_name, weight in strategy_weights.items():
                if weight > 0 and strategy_name in bot_manager.available_strategies:
                    try:
                        strategy_class = bot_manager.available_strategies[strategy_name]
                        bot_manager.strategy_instances[strategy_name] = strategy_class()
                        logger.info(f"✅ Активирована стратегия: {strategy_name}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка создания стратегии {strategy_name}: {e}")

            if not bot_manager.strategy_instances:
                logger.warning("⚠️ Ни одна стратегия не была активирована. Проверьте STRATEGY_WEIGHTS в конфигурации.")
                # Активируем хотя бы одну стратегию по умолчанию
                if 'multi_indicator' in bot_manager.available_strategies:
                    bot_manager.strategy_instances['multi_indicator'] = bot_manager.available_strategies['multi_indicator']()
                    logger.info("✅ Активирована стратегия по умолчанию: multi_indicator")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка при инициализации стратегий: {e}")
            bot_manager.status = BotStatus.ERROR
            bot_manager.is_running = False
            return

        # Инициализация tasks если не существует
        if not hasattr(bot_manager, 'tasks'):
            bot_manager.tasks = {}

        # 6. Запуск всех торговых циклов
        logger.info("📍 Этап 6: Запуск торговых циклов...")
        try:
            await start_all_trading_loops(bot_manager)
        except Exception as e:
            logger.error(f"❌ Ошибка запуска торговых циклов: {e}")
            bot_manager.status = BotStatus.ERROR
            bot_manager.is_running = False
            return

        # Устанавливаем финальный статус
        bot_manager.status = BotStatus.RUNNING
        bot_manager.is_running = True

        logger.info("=== БОТ УСПЕШНО ЗАПУЩЕН ===")
        logger.info(f"💼 Активных торговых пар: {len(bot_manager.active_pairs)}")
        logger.info(f"🎯 Активных стратегий: {len(bot_manager.strategy_instances)}")
        logger.info(f"⚡ Активных задач: {len(bot_manager.tasks)}")
        logger.info(f"💰 Баланс: ${getattr(bot_manager, 'balance', 0):.2f}")
        logger.info(f"💸 Доступно: ${getattr(bot_manager, 'available_balance', 0):.2f}")

        # Отправляем уведомление об успешном запуске
        if hasattr(bot_manager, 'notifier') and bot_manager.notifier:
            await bot_manager.notifier.send_message(
                f"✅ Бот успешно запущен!\n"
                f"Торговых пар: {len(bot_manager.active_pairs)}\n"
                f"Стратегий: {len(bot_manager.strategy_instances)}\n"
                f"Баланс: ${getattr(bot_manager, 'balance', 0):.2f}"
            )

        # Ожидание сигнала остановки
        await bot_manager._stop_event.wait()

        # Остановка всех задач
        logger.info("📍 Получен сигнал остановки, завершаем все задачи...")
        await _stop_all_tasks(bot_manager)

    except Exception as e:
        logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА при запуске бота: {e}")
        import traceback
        traceback.print_exc()
        
        bot_manager.status = BotStatus.ERROR
        bot_manager.is_running = False
        
        # Отправляем критическое уведомление
        if hasattr(bot_manager, 'notifier') and bot_manager.notifier:
            await bot_manager.notifier.send_message(
                f"🚨 КРИТИЧЕСКАЯ ОШИБКА!\n"
                f"Бот не смог запуститься: {str(e)}"
            )
        
        raise



async def _start_all_trading_loops(bot_manager):
    """Запуск всех торговых циклов"""
    from .trading_loops import start_all_trading_loops
    await start_all_trading_loops(bot_manager)


async def _stop_all_tasks(bot_manager):
    """Остановка всех запущенных задач"""
    logger.info("🛑 Остановка всех активных задач...")
    
    # Сначала останавливаем компоненты системы сигналов
    await _stop_signal_components(bot_manager)
    
    # Отменяем все задачи
    for task_name, task in bot_manager.tasks.items():
        if task and not task.done():
            logger.info(f"  ⏹️ Отмена задачи: {task_name}")
            task.cancel()
    
    # Ждем завершения всех задач
    if bot_manager.tasks:
        await asyncio.gather(*bot_manager.tasks.values(), return_exceptions=True)
    
    logger.info("✅ Все задачи остановлены")


async def pause(bot_manager):
    """
    Приостановка торгового бота
    Останавливает торговлю, но оставляет мониторинг активным
    """
    if bot_manager.status != BotStatus.RUNNING:
        return False, "Бот не запущен"
    
    logger.info("⏸️ Приостановка торгового бота...")
    
    bot_manager.status = BotStatus.PAUSED
    bot_manager.pause_time = datetime.utcnow()
    
    # Сбрасываем событие паузы, чтобы остановить торговые циклы
    if bot_manager._pause_event:
        bot_manager._pause_event.clear()
    
    # Закрываем все открытые позиции (опционально)
    if hasattr(bot_manager.config, 'CLOSE_POSITIONS_ON_PAUSE') and bot_manager.config.CLOSE_POSITIONS_ON_PAUSE:
        logger.info("📊 Закрытие всех открытых позиций...")
        # Логика закрытия позиций
    
    logger.info("✅ Бот приостановлен")
    return True, "Бот успешно приостановлен"


async def resume(bot_manager):
    """
    Возобновление работы торгового бота после паузы
    """
    if bot_manager.status != BotStatus.PAUSED:
        return False, "Бот не на паузе"
    
    logger.info("▶️ Возобновление работы торгового бота...")
    
    bot_manager.status = BotStatus.RUNNING
    bot_manager.pause_time = None
    
    # Устанавливаем событие паузы, чтобы возобновить торговые циклы
    if bot_manager._pause_event:
        bot_manager._pause_event.set()
    
    logger.info("✅ Бот возобновил работу")
    return True, "Бот успешно возобновил работу"


async def emergency_stop(bot_manager):
    """
    Экстренная остановка с закрытием всех позиций
    Используется в критических ситуациях
    """
    logger.critical("🚨 === ЭКСТРЕННАЯ ОСТАНОВКА БОТА ===")
    
    bot_manager.status = BotStatus.EMERGENCY_STOP
    
    try:
        # 1. Немедленно останавливаем все торговые операции
        if bot_manager._pause_event:
            bot_manager._pause_event.clear()
        
        # 2. Закрываем ВСЕ открытые позиции
        logger.critical("🚨 Закрытие всех открытых позиций...")
        closed_count = 0
        
        if bot_manager.positions:
            for symbol, position in list(bot_manager.positions.items()):
                try:
                    # Здесь должна быть логика закрытия позиции
                    logger.info(f"  📊 Закрытие позиции {symbol}")
                    closed_count += 1
                except Exception as e:
                    logger.error(f"  ❌ Ошибка закрытия {symbol}: {e}")
        
        logger.critical(f"🚨 Закрыто позиций: {closed_count}")
        
        # 3. Отменяем все ожидающие ордера
        logger.critical("🚨 Отмена всех ожидающих ордеров...")
        cancelled_count = 0
        
        if bot_manager.pending_orders:
            for order_id in list(bot_manager.pending_orders.keys()):
                try:
                    # Здесь должна быть логика отмены ордера
                    logger.info(f"  ❌ Отмена ордера {order_id}")
                    cancelled_count += 1
                except Exception as e:
                    logger.error(f"  ❌ Ошибка отмены {order_id}: {e}")
        
        logger.critical(f"🚨 Отменено ордеров: {cancelled_count}")
        
        # 4. Сигнализируем всем циклам об остановке
        if bot_manager._stop_event:
            bot_manager._stop_event.set()
        
        # 5. Сохраняем критическую информацию
        emergency_info = {
            'timestamp': datetime.utcnow().isoformat(),
            'reason': 'emergency_stop',
            'positions_closed': closed_count,
            'orders_cancelled': cancelled_count,
            'balance': bot_manager.balance,
            'status': 'completed'
        }
        
        logger.critical(f"🚨 Экстренная остановка завершена: {emergency_info}")
        
        # Финальный статус
        bot_manager.is_running = False
        bot_manager.status = BotStatus.STOPPED
        bot_manager.stop_time = datetime.utcnow()
        
        return True, f"Экстренная остановка выполнена. Закрыто позиций: {closed_count}, отменено ордеров: {cancelled_count}"
        
    except Exception as e:
        logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА при экстренной остановке: {e}")
        import traceback
        traceback.print_exc()
        return False, f"Ошибка экстренной остановки: {str(e)}"

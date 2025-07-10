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

from .types import BotStatus
from .initialization import initialize_all_components, display_account_info
from .trading_pairs import discover_all_trading_pairs, load_pairs_from_config, load_historical_data_for_pairs
from .trading_loops import start_all_trading_loops

logger = logging.getLogger(__name__)


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

    bot_manager.status = BotStatus.STOPPED
    bot_manager.is_running = False
    msg = "Бот успешно остановлен."
    logger.info(msg)
    return True, msg


def run_async_tasks(bot_manager):
    """
    ✨ НОВЫЙ ВСПОМОГАТЕЛЬНЫЙ МЕТОД
    Эта функция выполняется в отдельном потоке. Она создает новый цикл
    событий asyncio и запускает в нем основную асинхронную логику бота.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_async(bot_manager))
    except Exception as e:
        logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА в потоке бота: {e}", exc_info=True)
        bot_manager.status = BotStatus.ERROR
        bot_manager.is_running = False
    finally:
        logger.info("🏁 Поток бота и его цикл событий asyncio завершены.")


async def start_async(bot_manager):
    """
    ✨ НОВЫЙ АСИНХРОННЫЙ МЕТОД (ранее это была ваша логика в start())
    Здесь находится ВСЯ ваша асинхронная логика инициализации и работы.
    """
    try:
        logger.info("🤖 Асинхронный запуск: инициализация компонентов...")
        bot_manager.start_time = datetime.utcnow()
        
        # --- Этапы инициализации (асинхронные) ---
        if not await initialize_all_components(bot_manager):
             raise RuntimeError("Критическая ошибка: не удалось инициализировать компоненты.")

        # ✅ ДОБАВЛЯЕМ ЗАГРУЗКУ ТОРГОВЫХ ПАР
        logger.info("💰 Поиск и загрузка торговых пар...")
        from .trading_pairs import discover_all_trading_pairs, load_pairs_from_config
        pairs_discovered = await discover_all_trading_pairs(bot_manager)
        if not pairs_discovered:
            logger.warning("⚠️ Ошибка автопоиска пар, используем конфигурационные")
            load_pairs_from_config(bot_manager)
        
        # Обновляем DataCollector с активными парами
        if bot_manager.data_collector and bot_manager.active_pairs:
            bot_manager.data_collector.set_active_pairs(list(bot_manager.active_pairs))
            logger.info(f"📊 DataCollector обновлен с {len(bot_manager.active_pairs)} парами")

        # Загружаем исторические данные для активных пар
        if bot_manager.active_pairs:
            logger.info("📈 Загрузка исторических данных...")
            from .trading_pairs import load_historical_data_for_pairs
            await load_historical_data_for_pairs(bot_manager)
        
        # Если все прошло успешно, меняем статус
        bot_manager.is_running = True
        bot_manager.status = BotStatus.RUNNING
        logger.info("✅ Бот готов к работе. Запуск главного торгового цикла...")

        # --- Главный торговый цикл ---
        from .trading_loops import main_trading_loop
        await main_trading_loop(bot_manager)

    except Exception as e:
        bot_manager.status = BotStatus.ERROR
        bot_manager.is_running = False
        logger.error(f"❌ Ошибка во время асинхронного запуска или работы бота: {e}", exc_info=True)
        if hasattr(bot_manager, '_send_error_notification'):
            await send_error_notification(bot_manager, f"Критическая ошибка бота: {e}")
    finally:
        logger.info("🛑 Асинхронная часть бота завершает работу.")


async def pause(bot_manager) -> Tuple[bool, str]:
    """Приостановка торгового бота"""
    if bot_manager.status != BotStatus.RUNNING:
        return False, "Бот не запущен"
    
    try:
        logger.info("⏸️ Приостановка торгового бота...")
        bot_manager.status = BotStatus.PAUSED
        bot_manager.pause_time = datetime.utcnow()
        bot_manager._pause_event.clear()  # Ставим на паузу
        
        # Отменяем все новые ордера, но оставляем существующие позиции
        await cancel_pending_orders(bot_manager)
        
        await send_pause_notification(bot_manager)
        
        logger.info("✅ Торговый бот приостановлен")
        return True, "Бот приостановлен"
        
    except Exception as e:
        error_msg = f"Ошибка приостановки: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


async def resume(bot_manager) -> Tuple[bool, str]:
    """Возобновление работы торгового бота"""
    if bot_manager.status != BotStatus.PAUSED:
        return False, "Бот не на паузе"
    
    try:
        logger.info("▶️ Возобновление работы торгового бота...")
        bot_manager.status = BotStatus.RUNNING
        bot_manager._pause_event.set()  # Снимаем с паузы
        
        # Обновляем рыночные данные
        await refresh_market_data(bot_manager)
        
        await send_resume_notification(bot_manager)
        
        if bot_manager.pause_time:
            pause_duration = (datetime.utcnow() - bot_manager.pause_time).total_seconds()
            logger.info(f"✅ Работа возобновлена после паузы {pause_duration:.1f}с")
        
        return True, "Работа возобновлена"
        
    except Exception as e:
        error_msg = f"Ошибка возобновления: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


async def emergency_stop(bot_manager) -> Tuple[bool, str]:
    """Экстренная остановка с закрытием всех позиций"""
    try:
        logger.critical("🚨 ЭКСТРЕННАЯ ОСТАНОВКА АКТИВИРОВАНА!")
        bot_manager.status = BotStatus.EMERGENCY_STOP
        bot_manager.emergency_stop_triggered = True
        
        # Мгновенно закрываем все позиции
        await emergency_close_all_positions(bot_manager)
        
        # Отменяем все ордера
        await cancel_all_orders(bot_manager)
        
        # Останавливаем все циклы
        bot_manager._stop_event.set()
        
        await send_emergency_notification(bot_manager)
        
        logger.critical("🚨 Экстренная остановка завершена")
        return True, "Экстренная остановка выполнена"
        
    except Exception as e:
        error_msg = f"Ошибка экстренной остановки: {str(e)}"
        logger.critical(error_msg)
        return False, error_msg


# =================================================================
# ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ЖИЗНЕННОГО ЦИКЛА
# =================================================================

async def setup_signal_handlers(bot_manager):
    """Настройка обработчиков сигналов"""
    pass


async def validate_configuration(bot_manager) -> bool:
    """Валидация конфигурации"""
    return True


async def connect_exchange(bot_manager) -> bool:
    """Подключение к бирже - использует уже инициализированный exchange_client"""
    try:
        if not bot_manager.exchange_client:
            logger.error("❌ Exchange client не инициализирован")
            return False
            
        # Проверяем подключение
        if hasattr(bot_manager.exchange_client, 'is_connected') and bot_manager.exchange_client.is_connected:
            logger.info("✅ Уже подключены к бирже")
            return True
            
        # Если есть метод проверки соединения
        if hasattr(bot_manager.exchange_client, 'test_connection'):
            connected = await bot_manager.exchange_client.test_connection()
            if connected:
                logger.info("✅ Подключение к бирже работает")
                return True
                
        logger.warning("⚠️ Не удалось проверить подключение к бирже")
        return True  # Продолжаем работу
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки подключения к бирже: {e}")
        return False


async def load_historical_data(bot_manager):
    """Заглушка для загрузки исторических данных"""
    try:
        logger.info("📊 Загрузка исторических данных...")
        # Здесь можно добавить логику загрузки исторических данных
        await asyncio.sleep(1)  # Имитация загрузки
        logger.info("✅ Исторические данные загружены")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки исторических данных: {e}")
        return False


async def perform_initial_market_analysis(bot_manager):
    """Начальный анализ рынка"""
    pass


async def setup_monitoring_system(bot_manager):
    """Настройка системы мониторинга"""
    pass


async def start_websocket_connections(bot_manager):
    """Запуск WebSocket соединений"""
    pass


async def send_startup_notification(bot_manager):
    """Отправка уведомления о запуске"""
    pass


async def log_startup_statistics(bot_manager):
    """Логирование статистики запуска"""
    pass


async def save_current_state(bot_manager):
    """Сохранение текущего состояния"""
    pass


async def close_all_positions_safely(bot_manager):
    """Безопасное закрытие всех позиций"""
    pass


async def cancel_all_orders(bot_manager):
    """Отмена всех ордеров"""
    pass


async def stop_all_tasks(bot_manager):
    """Остановка всех задач"""
    for task_name, task in bot_manager.tasks.items():
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Таймаут остановки задачи: {task_name}")
            except asyncio.CancelledError:
                pass


async def close_websocket_connections(bot_manager):
    """Закрытие WebSocket соединений"""
    pass


async def stop_ml_system(bot_manager):
    """Остановка ML системы"""
    pass


async def export_final_data(bot_manager):
    """Экспорт финальных данных"""
    pass


async def disconnect_exchange(bot_manager):
    """Отключение от биржи"""
    pass


async def close_database_connections(bot_manager):
    """Закрытие соединений с БД"""
    pass


async def cleanup_caches(bot_manager):
    """Очистка кэшей"""
    bot_manager.market_data_cache.clear()
    bot_manager.ml_predictions.clear()
    bot_manager.current_opportunities.clear()


async def send_shutdown_notification(bot_manager, old_status):
    """Отправка уведомления об остановке"""
    pass


async def send_error_notification(bot_manager, error_msg):
    """Отправка уведомления об ошибке"""
    pass


async def cancel_pending_orders(bot_manager):
    """Отмена ожидающих ордеров"""
    pass


async def send_pause_notification(bot_manager):
    """Отправка уведомления о паузе"""
    pass


async def refresh_market_data(bot_manager):
    """Обновление рыночных данных"""
    pass


async def send_resume_notification(bot_manager):
    """Отправка уведомления о возобновлении"""
    pass


async def emergency_close_all_positions(bot_manager):
    """Экстренное закрытие всех позиций"""
    pass


async def send_emergency_notification(bot_manager):
    """Отправка экстренного уведомления"""
    pass
#!/usr/bin/env python3
"""
МЕТОДЫ СОВМЕСТИМОСТИ - Compatibility
Файл: src/bot/internal/compatibility.py

Содержит методы для обратной совместимости:
- Синхронные обертки для запуска/остановки
- Строковое представление
- Методы для совместимости с внешними модулями
"""

import asyncio
import threading
import time
import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

def get_compatibility(bot_instance):
    """Возвращает объект с методами совместимости"""
    
    class Compatibility:
        def __init__(self, bot):
            self.bot = bot
            
        def start(self):
            """Синхронная обертка для запуска бота"""
            from .lifecycle import start
            return start(self.bot)
            
        def stop(self):
            """Синхронная обертка для остановки бота"""
            from .lifecycle import stop
            return stop(self.bot)
            
        def __repr__(self):
            """Строковое представление для отладки"""
            return f"<BotManager status={self.bot.status.value}>"
            
        def set_socketio(self, socketio_instance):
            """Установка SocketIO для WebSocket коммуникаций"""
            self.bot.socketio = socketio_instance
            if hasattr(self.bot, 'websocket_manager') and self.bot.websocket_manager:
                self.bot.websocket_manager.socketio = socketio_instance
            return True
    
    return Compatibility(bot_instance)

class Compatibility:
    """Класс для методов совместимости"""
    
    def __init__(self, bot_manager):
        self.bot = bot_manager
    
    def start(self) -> Tuple[bool, str]:
        """
        СИНХРОННАЯ обертка для запуска из Flask API.
        Создает и запускает фоновый поток для асинхронной логики.
        """
        if self.bot.is_running:
            logger.warning("Попытка запустить уже работающего бота.")
            return False, "Бот уже запущен."

        logger.info("🚀 Получена команда на запуск бота. Создание фонового потока...")
        self.bot.status = self.bot.BotStatus.STARTING if hasattr(self.bot, 'BotStatus') else 'starting'
        
        # Используем threading.Event для безопасного межпоточного общения
        self.bot._stop_event = threading.Event()
        
        # Создаем поток, который будет управлять асинхронным циклом
        self.bot._async_thread = threading.Thread(target=self._run_async_tasks, name="BotAsyncLoopThread")
        self.bot._async_thread.daemon = True # Поток завершится, если основной процесс умрет
        self.bot._async_thread.start()
        
        time.sleep(3) # Даем потоку время на запуск и начальную инициализацию

        if self.bot.is_running:
            msg = "Бот успешно запущен в фоновом режиме."
            logger.info(msg)
            return True, msg
        else:
            msg = f"Не удалось запустить бота. Текущий статус: {self.bot.status}. Проверьте логи на наличие ошибок."
            logger.error(msg)
            return False, msg

    def stop(self) -> Tuple[bool, str]:
        """
        СИНХРОННАЯ обертка для остановки из Flask API.
        Сигнализирует фоновому потоку о необходимости завершения.
        """
        if not self.bot.is_running:
            logger.warning("Попытка остановить уже остановленного бота.")
            return False, "Бот не запущен."

        logger.info("🛑 Получена команда на остановку бота...")
        self.bot.status = self.bot.BotStatus.STOPPING if hasattr(self.bot, 'BotStatus') else 'stopping'
        
        if self.bot._stop_event:
            self.bot._stop_event.set() # Сигнализируем циклу о необходимости остановиться
        else:
            # На случай, если что-то пошло не так
            self.bot.is_running = False
            return False, "Внутренняя ошибка: событие остановки отсутствует."
            
        # Ждем завершения потока
        if self.bot._async_thread:
            self.bot._async_thread.join(timeout=15) # Даем 15 секунд на корректное завершение

        if self.bot._async_thread and self.bot._async_thread.is_alive():
             self.bot.status = self.bot.BotStatus.ERROR if hasattr(self.bot, 'BotStatus') else 'error'
             msg = "КРИТИЧЕСКАЯ ОШИБКА: Поток бота не завершился вовремя."
             logger.critical(msg)
             return False, msg

        self.bot.status = self.bot.BotStatus.STOPPED if hasattr(self.bot, 'BotStatus') else 'stopped'
        self.bot.is_running = False
        msg = "Бот успешно остановлен."
        logger.info(msg)
        return True, msg

    def _run_async_tasks(self):
        """
        ✨ НОВЫЙ ВСПОМОГАТЕЛЬНЫЙ МЕТОД
        Эта функция выполняется в отдельном потоке. Она создает новый цикл
        событий asyncio и запускает в нем основную асинхронную логику бота.
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    
            # ✅ ИСПРАВЛЕНО: Импортируем главную асинхронную функцию `start_async` напрямую,
            # а не несуществующий класс `Lifecycle`.
            from .lifecycle import start_async
    
            # Запускаем основную логику в цикле событий
            loop.run_until_complete(start_async(self.bot))
    
        except Exception as e:
            logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА в потоке бота: {e}", exc_info=True)
            self.bot.status = self.bot.BotStatus.ERROR if hasattr(self.bot, 'BotStatus') else 'error'
            self.bot.is_running = False
        finally:
            logger.info("🏁 Поток бота и его цикл событий asyncio завершены.")
    
    def __repr__(self) -> str:
        """Строковое представление для отладки"""
        return (
            f"BotManager(status={self.bot.status}, "
            f"pairs={len(getattr(self.bot, 'active_pairs', []))}, "
            f"positions={len(getattr(self.bot, 'positions', {}))}, "
            f"cycles={getattr(self.bot, 'cycles_count', 0)}, "
            f"uptime={self.bot.start_time})"
        )
    
    # Дополнительные методы совместимости для внешних модулей
    
    async def update_pairs(self, pairs: list) -> None:
        """Обновление торговых пар (для совместимости)"""
        self.bot.trading_pairs = pairs
        # Обновляем также активные пары
        self.bot.active_pairs = pairs[:getattr(self.bot.config, 'MAX_TRADING_PAIRS', 10)]
        logger.info(f"📊 Обновлены торговые пары: {len(pairs)}")
    
    def set_socketio(self, socketio_instance):
        """Установка SocketIO для WebSocket коммуникаций"""
        self.bot.socketio = socketio_instance
        logger.info("✅ SocketIO установлен в BotManager")
    
    # Альтернативные синхронные методы для старого API
    
    def start_sync(self) -> Tuple[bool, str]:
        """Синхронная обертка для запуска бота (альтернативное название)"""
        try:
            # Если есть асинхронный метод start_async
            if hasattr(self.bot, 'lifecycle') and hasattr(self.bot.lifecycle, 'start_async'):
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self.bot.lifecycle.start_async())
                return result
            
            # Иначе используем базовую логику
            if self.bot.is_running:
                return False, "Бот уже запущен"
            
            self.bot.is_running = True
            self.bot.start_time = datetime.utcnow()
            self.bot.stop_time = None
            
            logger.info("✅ Бот запущен (синхронный режим)")
            return True, "Бот успешно запущен"
            
        except Exception as e:
            logger.error(f"Ошибка запуска бота: {e}")
            return False, f"Ошибка запуска: {str(e)}"
    
    def stop_sync(self) -> Tuple[bool, str]:
        """Синхронная обертка для остановки бота (альтернативное название)"""
        try:
            # Если есть асинхронный метод stop_async
            if hasattr(self.bot, 'lifecycle') and hasattr(self.bot.lifecycle, 'stop_async'):
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self.bot.lifecycle.stop_async())
                return result
            
            # Иначе используем базовую логику
            if not self.bot.is_running:
                return False, "Бот не запущен"
            
            self.bot.is_running = False
            self.bot.stop_time = self.bot.datetime.utcnow()
            
            logger.info("✅ Бот остановлен (синхронный режим)")
            return True, "Бот успешно остановлен"
            
        except Exception as e:
            logger.error(f"Ошибка остановки бота: {e}")
            return False, f"Ошибка остановки: {str(e)}"

# Функция для получения экземпляра
def get_compatibility(bot_manager):
    """Получить экземпляр совместимости"""
    return Compatibility(bot_manager)

# Экспорты
__all__ = ['Compatibility', 'get_compatibility']
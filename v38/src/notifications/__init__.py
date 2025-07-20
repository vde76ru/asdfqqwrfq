# Файл: src/notifications/__init__.py
import logging
from .telegram import telegram_notifier, TelegramNotifier

logger = logging.getLogger(__name__)

class NotificationManager:
    """Центральный менеджер для всех каналов уведомлений."""
    def __init__(self):
        self.telegram = telegram_notifier
        self.telegram_enabled = self.telegram.enabled
        
        logger.info(f"NotificationManager инициализирован. Telegram: {'Включен' if self.telegram_enabled else 'Отключен'}")

    async def send_signal_alert(self, message: str):
        """Отправка уведомления о сигнале."""
        if self.telegram_enabled:
            await self.telegram.send_message(message)

    async def send_error_alert(self, component: str, error_message: str):
        """Отправка уведомления об ошибке."""
        message = f"🚨 <b>ОШИБКА В СИСТЕМЕ</b>\n\n"
        message += f"🔧 <b>Компонент:</b> {component}\n"
        message += f"❌ <b>Ошибка:</b> {error_message}"
        if self.telegram_enabled:
            await self.telegram.send_message(message)

# Глобальный экземпляр менеджера
notification_manager = NotificationManager()

__all__ = ['notification_manager', 'NotificationManager', 'TelegramNotifier']
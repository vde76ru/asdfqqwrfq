# Файл: src/notifications/telegram.py
import logging
import aiohttp
from ..core.unified_config import unified_config as config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Отвечает за отправку сообщений в Telegram."""
    def __init__(self):
        self.token = getattr(config, 'TELEGRAM_BOT_TOKEN', None)
        self.chat_id = getattr(config, 'TELEGRAM_CHAT_ID', None)
        self.enabled = bool(self.token and self.chat_id)
        
        if self.enabled:
            self.api_url = f"https://api.telegram.org/bot{self.token}"
            logger.info("✅ TelegramNotifier инициализирован с токеном и chat_id.")
        else:
            logger.warning("⚠️ TelegramNotifier отключен: токен или chat_id не найдены.")

    async def send_message(self, text: str, parse_mode: str = 'HTML') -> bool:
        """Асинхронная отправка сообщения."""
        if not self.enabled:
            return False
        
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.api_url}/sendMessage", json=payload) as response:
                    if response.status == 200:
                        logger.info("✅ Уведомление в Telegram успешно отправлено.")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка отправки в Telegram: {response.status} - {error_text}")
                        return False
        except Exception as e:
            logger.error(f"❌ Исключение при отправке в Telegram: {e}", exc_info=True)
            return False

# Глобальный экземпляр для удобного импорта
telegram_notifier = TelegramNotifier()
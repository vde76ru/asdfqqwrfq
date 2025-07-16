# Файл: src/bot/__init__.py
# Инициализация пакета bot с корректными и безопасными импортами.

import logging

logger = logging.getLogger(__name__)

# =================================================================
# 🎯 ИСПРАВЛЕНИЕ: Используем прямой импорт BotManager и get_bot_manager
# без сложной и подверженной ошибкам логики.
# Это устраняет ошибки "No module named 'src.bot.core'" и делает код чище.
# =================================================================

try:
    # Пытаемся импортировать основные компоненты напрямую.
    from .manager import BotManager, get_bot_manager
    logger.info("✅ Основные компоненты BotManager импортированы успешно.")
    BOT_AVAILABLE = True
except ImportError as e:
    # Если импорт не удался, выводим подробное сообщение об ошибке.
    logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать BotManager из src.bot.manager.")
    logger.critical(f"   > Ошибка: {e}")
    logger.critical(f"   > Проверьте файл 'src/bot/manager.py' и его импорты на наличие ошибок.")
    BotManager = None
    get_bot_manager = None
    BOT_AVAILABLE = False

# Экспортируем только то, что действительно нужно другим частям приложения.
__all__ = [
    'BotManager',
    'get_bot_manager',
    'BOT_AVAILABLE'
]

if not BOT_AVAILABLE:
    # Если основные компоненты не загрузились, генерируем исключение,
    # чтобы предотвратить запуск приложения в нерабочем состоянии.
    raise ImportError(
        "Критический модуль 'src.bot.manager' не может быть загружен. "
        "Приложение не может продолжить работу. Смотрите логи выше для деталей."
    )

logger.info("🤖 Пакет 'bot' успешно инициализирован.")

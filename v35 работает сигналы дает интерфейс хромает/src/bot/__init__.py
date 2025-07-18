# src/bot/__init__.py
# Инициализация пакета bot с корректными и безопасными импортами.
import logging

logger = logging.getLogger(__name__)

# Определяем переменные по умолчанию на случай сбоя импорта
BotManager = None
get_bot_manager = None
BOT_AVAILABLE = False

try:
    # Пытаемся импортировать основные компоненты напрямую.
    from .manager import BotManager, get_bot_manager
    
    # Если импорт успешен, устанавливаем флаг доступности
    if BotManager and get_bot_manager:
        logger.info("✅ Основные компоненты BotManager импортированы успешно.")
        BOT_AVAILABLE = True
    else:
        # Эта ветка на случай, если файл manager.py пуст или не содержит нужных классов
        logger.critical("❌ Файл 'src/bot/manager.py' не содержит BotManager или get_bot_manager.")

except ImportError as e:
    # Если импорт не удался, выводим подробное сообщение об ошибке.
    # Это основная точка отказа, которую мы видели в логах.
    logger.critical("❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать BotManager из src.bot.manager.")
    logger.critical(f"   > Ошибка Python: {e}")
    logger.critical("   > Это может быть вызвано ошибкой внутри 'src/bot/manager.py' или одного из файлов, которые он импортирует.")
    logger.critical("   > Проверьте логи выше на наличие других ошибок, которые могли произойти до этой.")

except Exception as e:
    # Ловим любые другие неожиданные ошибки при импорте
    logger.critical(f"❌ НЕОЖИДАННАЯ ОШИБКА при импорте BotManager: {e}", exc_info=True)


# Экспортируем только то, что действительно нужно другим частям приложения.
__all__ = [
    'BotManager',
    'get_bot_manager',
    'BOT_AVAILABLE'
]

# ----- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ -----
# Мы больше не вызываем 'raise ImportError'.
# Вместо этого, другие части приложения (например, create_app) должны проверять
# флаг BOT_AVAILABLE, чтобы понять, можно ли продолжать работу.
if not BOT_AVAILABLE:
    logger.warning("⚠️ Бот будет работать в ОГРАНИЧЕННОМ РЕЖИМЕ, так как BotManager недоступен.")

logger.info("✅ Пакет 'bot' инициализирован.")

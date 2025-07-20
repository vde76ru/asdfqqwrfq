# МОЯ ПРЕДЛОЖЕННАЯ ВЕРСИЯ (ПРАВИЛЬНАЯ)
#/src/logging/__init__.py


from .smart_logger import logger # <--- Ключевой импорт экземпляра
from .log_manager import LogManager
from .analytics_collector import AnalyticsCollector

__all__ = [
    "logger", # <--- Ключевой экспорт экземпляра
    "LogManager",
    "AnalyticsCollector"
]
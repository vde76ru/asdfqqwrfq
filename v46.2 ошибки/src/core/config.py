"""
Алиас для обратной совместимости
Все модули должны использовать unified_config
/src/core/config.py
"""
from .unified_config import unified_config as Config

# Экспорт для обратной совместимости
__all__ = ['Config']
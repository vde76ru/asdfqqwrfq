"""
Внутренние модули BotManager
Файл: src/bot/internal/__init__.py

Экспортирует все внутренние компоненты для использования в BotManager
"""

# Импортируем типы первыми, так как они используются везде
from .types import *

# Затем импортируем модули в порядке зависимостей
from . import (
    initialization,
    lifecycle,
    trading_pairs,
    trading_loops,
    monitoring,
    compatibility
)

# После импорта модулей импортируем utilities, который может использовать функции из других модулей
from . import utilities

__all__ = [
    'initialization',
    'lifecycle',
    'trading_pairs',
    'trading_loops',
    'monitoring',
    'utilities',
    'compatibility',
    # Экспортируем все типы
    'BotStatus',
    'ComponentStatus',
    'MarketPhase',
    'RiskLevel',
    'TradeDecision',
    'TradingOpportunity',
    'MarketState',
    'ComponentInfo',
    'PerformanceMetrics',
    'TradingStatistics'
]
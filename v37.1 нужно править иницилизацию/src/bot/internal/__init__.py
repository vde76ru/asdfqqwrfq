"""
Внутренние модули BotManager
Файл: src/bot/internal/__init__.py

Экспорты всех внутренних компонентов для использования в manager.py
"""

# Типы данных
from .types import (
    BotStatus,
    ComponentStatus, 
    MarketPhase,
    RiskLevel,
    TradeDecision,
    TradingOpportunity,
    MarketState,
    ComponentInfo,
    PerformanceMetrics,
    TradingStatistics
)

# Модули функциональности  
from . import initialization
from . import lifecycle
from . import trading_pairs
from . import trading_loops
from . import market_analysis
from . import trade_execution
from . import position_management
from . import monitoring
from . import utilities
from . import compatibility

__all__ = [
    # Типы данных
    'BotStatus',
    'ComponentStatus',
    'MarketPhase', 
    'RiskLevel',
    'TradeDecision',
    'TradingOpportunity',
    'MarketState',
    'ComponentInfo',
    'PerformanceMetrics',
    'TradingStatistics',
    
    # Модули
    'initialization',
    'lifecycle',
    'trading_pairs',
    'trading_loops', 
    'market_analysis',
    'trade_execution',
    'position_management',
    'monitoring',
    'utilities',
    'compatibility'
]
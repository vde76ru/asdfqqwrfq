#!/usr/bin/env python3
"""
Модуль data - сбор и обработка рыночных данных
"""

# Импортируем основные компоненты
try:
    from .data_collector import DataCollector
    DATA_COLLECTOR_AVAILABLE = True
except ImportError:
    DATA_COLLECTOR_AVAILABLE = False
    DataCollector = None

try:
    from .indicators import UnifiedIndicators, indicators
    INDICATORS_AVAILABLE = True
except ImportError:
    INDICATORS_AVAILABLE = False
    UnifiedIndicators = None
    indicators = None

__all__ = [
    'DataCollector',
    'UnifiedIndicators', 
    'indicators',
    'DATA_COLLECTOR_AVAILABLE',
    'INDICATORS_AVAILABLE'
]
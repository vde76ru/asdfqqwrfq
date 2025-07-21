# src/bot/core.py
# -*- coding: utf-8 -*-
"""
Временный файл-заглушка для обратной совместимости.

Этот модуль перехватывает старые запросы к 'src.bot.core'
и перенаправляет их на новый, правильный путь 'src.core'.
Это позволяет запустить приложение, даже если в коде остались
старые, труднонаходимые импорты.
"""
import logging

logger = logging.getLogger(__name__)

logger.warning("--------------------------------------------------")
logger.warning("!!! ОБНАРУЖЕН УСТАРЕВШИЙ ИМПОРТ 'src.bot.core' !!!")
logger.warning("--------------------------------------------------")
logger.warning("Перенаправление на 'src.core'. Пожалуйста, исправьте импорт в вызывающем файле.")

# Перенаправляем все запросы к этому модулю на правильный 'src.core'
try:
    from ..core import *
    from ..core.database import db, SessionLocal, engine
    from ..core.models import Base, User, Trade, Signal, Position, Balance, MarketData, OrderBookSnapshot, VolumeAnomaly
    from ..core.unified_config import unified_config as config

    logger.info("✅ Устаревший импорт 'src.bot.core' успешно перенаправлен на 'src.core'.")

except ImportError as e:
    logger.critical(f"❌ Не удалось выполнить перенаправление из src.bot.core на src.core: {e}")


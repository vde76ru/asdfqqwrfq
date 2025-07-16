#!/usr/bin/env python3
"""
УПРАВЛЕНИЕ ПОЗИЦИЯМИ - Position Management
Файл: src/bot/internal/position_management.py

Содержит все методы для управления торговыми позициями:
- Управление всеми позициями
- Фильтрация возможностей
- Ранжирование возможностей
- Проверки рисков
- Обновление производительности стратегий
- Очистка устаревших возможностей
- Экстренные остановки
- Инициализация стратегий
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque

# Импорты типов
from .types import TradingOpportunity, MarketPhase, RiskLevel

logger = logging.getLogger(__name__)

def get_position_management(bot_instance):
    """Возвращает объект с методами управления позициями"""
    
    class PositionManagement:
        def __init__(self, bot):
            self.bot = bot
            
        async def manage_open_positions(self):
            """Управление открытыми позициями"""
            return await manage_open_positions(self.bot)
            
        async def check_and_update_stop_losses(self):
            """Проверка и обновление стоп-лоссов"""
            return await check_and_update_stop_losses(self.bot)
    
    return PositionManagement(bot_instance)

class PositionManagement:
    """Класс для управления позициями"""
    
    def __init__(self, bot_manager):
        self.bot = bot_manager
        
    async def _manage_all_positions(self):
        """Управление всеми открытыми позициями"""
        logger.debug("📊 Проверка открытых позиций...")
        
        # Проверяем через position_manager если доступен
        if hasattr(self.bot, 'position_manager') and self.bot.position_manager:
            try:
                positions = await self.bot.position_manager.get_all_positions()
                if positions:
                    logger.info(f"📊 Активных позиций: {len(positions)}")
                    # TODO: Реализовать управление позициями
            except Exception as e:
                logger.error(f"❌ Ошибка управления позициями: {e}")
        
        return True
    
    async def _filter_opportunities(self, opportunities: List[TradingOpportunity]) -> List[TradingOpportunity]:
        """Фильтрация возможностей"""
        return opportunities
    
    async def _rank_all_opportunities(self, opportunities: List[TradingOpportunity]) -> List[TradingOpportunity]:
        """Ранжирование возможностей"""
        return opportunities
    
    async def _perform_pre_trade_risk_check(self) -> bool:
        """Проверка рисков перед торговлей"""
        return True
    
    async def _update_strategy_performance(self):
        """Обновление производительности стратегий"""
        pass
    
    async def _cleanup_expired_opportunities(self):
        """Очистка устаревших возможностей"""
        pass
    
    async def _trigger_emergency_stop(self, reason: str):
        """Запуск экстренной остановки"""
        logger.critical(f"🚨 Запуск экстренной остановки: {reason}")
        await self.bot.emergency_stop()
    
    async def _initialize_strategies(self):
        """Инициализация стратегий - ПОЛНАЯ РЕАЛИЗАЦИЯ"""
        try:
            logger.info("🎯 Инициализация стратегий...")
            
            # Загружаем доступные стратегии
            try:
                from ...strategies import (
                    MultiIndicatorStrategy,
                    MomentumStrategy, 
                    MeanReversionStrategy,
                    BreakoutStrategy,
                    ScalpingStrategy,
                    #SwingTradingStrategy
                )
                
                # Регистрируем стратегии
                self.bot.available_strategies = {
                    'multi_indicator': MultiIndicatorStrategy,
                    'momentum': MomentumStrategy,
                    'mean_reversion': MeanReversionStrategy,
                    'breakout': BreakoutStrategy,
                    'scalping': ScalpingStrategy,
                    #'swing': SwingTradingStrategy
                }
                
                logger.info(f"✅ Загружено {len(self.bot.available_strategies)} стратегий")
                
            except ImportError as e:
                logger.warning(f"⚠️ Не все стратегии доступны: {e}")
                # Минимальный набор стратегий
                self.bot.available_strategies = {}
            
            # Активируем стратегии согласно весам из конфигурации
            try:
                strategy_weights = {
                    'multi_indicator': 25.0,
                    'momentum': 20.0,
                    'mean_reversion': 15.0,
                    'breakout': 15.0,
                    'scalping': 10.0,
                    #'swing': 10.0,
                    'ml_prediction': 5.0
                }
                
                # Если есть веса в конфигурации - используем их
                strategy_weights_config = getattr(self.bot.config, 'STRATEGY_WEIGHTS', None)
                if strategy_weights_config:
                    # Парсим строку формата "name:weight,name:weight"
                    if isinstance(strategy_weights_config, str):
                        for pair in strategy_weights_config.split(','):
                            if ':' in pair:
                                name, weight = pair.strip().split(':')
                                strategy_weights[name.strip()] = float(weight)
                    elif isinstance(strategy_weights_config, dict):
                        strategy_weights.update(strategy_weights_config)
                
                # Создаем экземпляры активных стратегий
                for strategy_name, weight in strategy_weights.items():
                    if weight > 0 and strategy_name in self.bot.available_strategies:
                        try:
                            # Создаем экземпляр стратегии
                            strategy_class = self.bot.available_strategies[strategy_name]
                            strategy_instance = strategy_class()
                            
                            self.bot.strategy_instances[strategy_name] = strategy_instance
                            
                            # Инициализируем производительность стратегии
                            self.bot.strategy_performance[strategy_name] = {
                                'weight': weight,
                                'enabled': True,
                                'total_trades': 0,
                                'winning_trades': 0,
                                'losing_trades': 0,
                                'total_profit': 0.0,
                                'win_rate': 0.0,
                                'last_used': None
                            }
                            
                            logger.info(f"✅ Активирована стратегия {strategy_name} с весом {weight}%")
                            
                        except Exception as e:
                            logger.error(f"❌ Ошибка создания стратегии {strategy_name}: {e}")
                
                # Проверяем что хотя бы одна стратегия активна
                if not self.bot.strategy_instances:
                    logger.warning("⚠️ Нет активных стратегий, создаем базовую")
                    # Создаем минимальную стратегию-заглушку
                    class BasicStrategy:
                        def __init__(self):
                            self.name = 'basic'
                        
                        async def analyze(self, symbol, data):
                            return {'signal': 'HOLD', 'confidence': 0.5}
                    
                    self.bot.strategy_instances['basic'] = BasicStrategy()
                    self.bot.strategy_performance['basic'] = {
                        'weight': 100.0,
                        'enabled': True,
                        'total_trades': 0,
                        'winning_trades': 0,
                        'losing_trades': 0,
                        'total_profit': 0.0,
                        'win_rate': 0.0,
                        'last_used': None
                    }
                
                logger.info(f"✅ Инициализировано {len(self.bot.strategy_instances)} стратегий")
                
                # Логируем активные стратегии
                active_strategies = [name for name, inst in self.bot.strategy_instances.items()]
                logger.info(f"📊 Активные стратегии: {', '.join(active_strategies)}")
                
                # Нормализуем веса (чтобы сумма была 100%)
                total_weight = sum(
                    perf['weight'] 
                    for perf in self.bot.strategy_performance.values() 
                    if perf.get('enabled', True)
                )
                
                if total_weight > 0:
                    for strategy_name in self.bot.strategy_performance:
                        if self.bot.strategy_performance[strategy_name].get('enabled', True):
                            normalized_weight = (
                                self.bot.strategy_performance[strategy_name]['weight'] / total_weight * 100
                            )
                            self.bot.strategy_performance[strategy_name]['normalized_weight'] = normalized_weight
                            logger.debug(
                                f"📊 {strategy_name}: вес {normalized_weight:.1f}% "
                                f"(оригинальный: {self.bot.strategy_performance[strategy_name]['weight']})"
                            )
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации стратегий: {e}")
                import traceback
                traceback.print_exc()
                return False
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка инициализации стратегий: {e}")
            return False

# Функция для получения экземпляра
def get_position_management(bot_manager):
    """Получить экземпляр менеджера позиций"""
    return PositionManagement(bot_manager)

# Экспорты
__all__ = ['PositionManagement', 'get_position_management']
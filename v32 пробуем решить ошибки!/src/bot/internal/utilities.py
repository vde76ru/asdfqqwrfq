#!/usr/bin/env python3
"""
УТИЛИТЫ И СТАТУС - Utilities
Файл: src/bot/internal/utilities.py

Содержит все вспомогательные методы:
- Получение статуса (основной и полный)
- Очистка данных для JSON
- Обновления статуса через WebSocket
- Расчеты времени работы
- Информация о балансе и позициях
- Лучшие стратегии
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import is_dataclass, asdict
from enum import Enum
from collections import deque

# Импорты типов
from .types import BotStatus

logger = logging.getLogger(__name__)

def get_utilities(bot_instance):
    """Возвращает объект с утилитами"""
    
    class Utilities:
        def __init__(self, bot):
            self.bot = bot
            
        def get_active_strategies(self):
            """Получение списка активных стратегий"""
            return get_active_strategies(self.bot)
            
        async def cleanup_old_data(self):
            """Очистка устаревших данных"""
            return await cleanup_old_data(self.bot)
            
        def format_balance_info(self, balance_info):
            """Форматирование информации о балансе"""
            return format_balance_info(self.bot, balance_info)
            
        def log_trade_result(self, trade_result):
            """Логирование результата сделки"""
            return log_trade_result(self.bot, trade_result)
    
    return Utilities(bot_instance)

class Utilities:
    """Класс утилит"""
    
    def __init__(self, bot_manager):
        self.bot = bot_manager
    
    def get_full_status(self) -> Dict[str, Any]:
        """
        Возвращает полный статус бота, безопасный для JSON-сериализации.
        """
        logger.debug("Вызов get_full_status() -> делегирование в get_status() с очисткой")
        raw_status = self.get_status()
        
        # Очищаем данные от несериализуемых объектов
        sanitized_status = self._sanitize_for_json(raw_status)
        
        return sanitized_status
    
    def _sanitize_for_json(self, data: Any) -> Any:
        """
        Рекурсивно преобразует данные для безопасной JSON-сериализации,
        конвертируя deque и set в list.
        """
        if isinstance(data, dict):
            return {k: self._sanitize_for_json(v) for k, v in data.items()}
        if isinstance(data, (list, tuple)):
            return [self._sanitize_for_json(v) for v in data]
        if isinstance(data, (deque, set)):
            # САМОЕ ВАЖНОЕ: deque и set преобразуются в простой список
            return [self._sanitize_for_json(v) for v in data]
        if isinstance(data, (datetime, pd.Timestamp)):
            return data.isoformat()
        if isinstance(data, (np.int64, np.int32)):
            return int(data)
        if isinstance(data, (np.float64, np.float32)):
            return float(data)
        # Для Enum-объектов
        if isinstance(data, Enum):
            return data.value
        # Для Dataclass-объектов
        if hasattr(data, '__dict__'):
            # Проверяем, не является ли объект простым типом, у которого тоже есть __dict__
            if not isinstance(data, (int, float, str, bool)) and type(data).__module__ != 'builtins':
                try:
                    # Попытка использовать asdict если это dataclass
                    if is_dataclass(data):
                         return self._sanitize_for_json(asdict(data))
                except ImportError:
                    pass
        
        return data

    def get_status(self) -> Dict[str, Any]:
       
        try:
            # Весь ваш оригинальный код для инициализации атрибутов
            if not hasattr(self.bot, 'opportunities_found'):
                self.bot.opportunities_found = 0
            if not hasattr(self.bot, 'missed_opportunities'):
                self.bot.missed_opportunities = 0
            if not hasattr(self.bot, 'market_state'):
                self.bot.market_state = type('obj', (object,), {
                    'overall_trend': 'UNKNOWN',
                    'volatility': 'MEDIUM',
                    'fear_greed_index': 50,
                    'market_regime': 'SIDEWAYS_MARKET',
                    'risk_level': 'medium',
                    'btc_dominance': 0.0,
                    'eth_dominance': 0.0,
                    'total_market_cap': 0.0,
                    'volume_24h': 0.0
                })()

            # 1. Сначала собираем "сырые" данные, как в вашем оригинальном коде.
            raw_status_data = {
                'status': self.bot.status, # Передаем объект как есть, очиститель справится
                'is_running': self.bot.is_running,
                'is_paused': self.bot.status == BotStatus.PAUSED,
                'start_time': self.bot.start_time,
                'stop_time': self.bot.stop_time,
                'pause_time': self.bot.pause_time,
                'uptime_seconds': (datetime.utcnow() - self.bot.start_time).total_seconds() if self.bot.start_time and self.bot.is_running else 0,
                'cycles_count': getattr(self.bot, 'cycles_count', 0),
                'mode': 'paper' if self.bot.config.PAPER_TRADING else 'live',
                
                'trading_pairs': {
                    'total_pairs': len(getattr(self.bot, 'all_trading_pairs', [])),
                    'active_pairs': len(getattr(self.bot, 'active_pairs', [])),
                    'inactive_pairs': len(getattr(self.bot, 'inactive_pairs', [])),
                    'blacklisted_pairs': len(getattr(self.bot, 'blacklisted_pairs', set())),
                    'watchlist_pairs': len(getattr(self.bot, 'watchlist_pairs', [])),
                    'trending_pairs': getattr(self.bot, 'trending_pairs', [])[:5],
                    'high_volume_pairs': getattr(self.bot, 'high_volume_pairs', [])[:5]
                },
                
                'trading': {
                    'open_positions': len(getattr(self.bot, 'positions', {})),
                    'pending_orders': len(getattr(self.bot, 'pending_orders', {})),
                    'trades_today': getattr(self.bot, 'trades_today', 0),
                    'daily_profit': round(getattr(self.bot, 'daily_profit', 0.0), 2),
                    'weekly_profit': round(getattr(self.bot, 'weekly_profit', 0.0), 2),
                    'monthly_profit': round(getattr(self.bot, 'monthly_profit', 0.0), 2),
                    'opportunities_found': getattr(self.bot, 'opportunities_found', 0),
                    'missed_opportunities': getattr(self.bot, 'missed_opportunities', 0)
                },
                
                'strategies': {
                    'available_strategies': list(getattr(self.bot, 'strategies', {}).keys()) if hasattr(self.bot, 'strategies') else ['multi_indicator', 'momentum', 'mean_reversion', 'breakout', 'scalping', 'swing'],
                    'active_strategies': list(getattr(self.bot, 'active_strategies', [])) if hasattr(self.bot, 'active_strategies') else ['auto'],
                    'best_performing_strategy': getattr(self.bot, 'best_strategy', 'auto') if hasattr(self.bot, 'best_strategy') else 'auto',
                    'strategy_performance': {}
                },
                
                'market_state': self.bot.market_state, # Передаем весь объект
                
                'machine_learning': {
                    'enabled': getattr(self.bot, 'ml_enabled', True) if hasattr(self.bot, 'ml_enabled') else True,
                    'models_loaded': len(getattr(self.bot, 'ml_models', {})) if hasattr(self.bot, 'ml_models') else 0,
                    'predictions_cached': len(getattr(self.bot, 'ml_predictions_cache', {})) if hasattr(self.bot, 'ml_predictions_cache') else 0,
                    'models_performance': {},
                    'training_queue_size': 0
                },
                
                'news_analysis': {
                    'enabled': getattr(self.bot, 'news_analysis_enabled', True) if hasattr(self.bot, 'news_analysis_enabled') else True,
                    'news_cached': len(getattr(self.bot, 'news_cache', [])) if hasattr(self.bot, 'news_cache') else 0,
                    'sentiment_scores': 0,
                    'social_signals': 0
                },
                
                'risk_management': {
                    'portfolio_risk': getattr(self.bot, 'portfolio_risk', 0.0),
                    'daily_loss': getattr(self.bot, 'daily_loss', 0.0),
                    'risk_alerts': getattr(self.bot, 'risk_alerts', 0), # Может быть списком, _sanitize_value справится
                    'circuit_breaker_active': getattr(self.bot, 'circuit_breaker_active', False),
                    'correlation_pairs': 0,
                    'risk_limits': getattr(self.bot, 'risk_limits', {
                        'max_portfolio_risk': 0.1, 'max_daily_loss': 0.05,
                        'max_correlation': 0.7, 'max_positions': self.bot.config.MAX_POSITIONS,
                        'max_daily_trades': self.bot.config.MAX_DAILY_TRADES
                    })
                },
                
                'performance': getattr(self.bot, 'performance_metrics', {}),
                
                'components': getattr(self.bot, 'components', {}),
                
                'statistics': getattr(self.bot, 'trading_stats', {}),
                
                'tasks': {name: ('running' if task and not task.done() else 'stopped') for name, task in getattr(self.bot, 'tasks', {}).items()},
                
                'configuration': {
                    'max_positions': self.bot.config.MAX_POSITIONS,
                    'max_daily_trades': self.bot.config.MAX_DAILY_TRADES,
                    'max_trading_pairs': self.bot.config.MAX_TRADING_PAIRS,
                    'position_size_percent': self.bot.config.POSITION_SIZE_PERCENT,
                    'stop_loss_percent': self.bot.config.STOP_LOSS_PERCENT,
                    'take_profit_percent': self.bot.config.TAKE_PROFIT_PERCENT,
                    'testnet_mode': self.bot.config.TESTNET,
                    'ml_enabled': getattr(self.bot, 'ml_enabled', True),
                    'news_analysis_enabled': getattr(self.bot, 'news_analysis_enabled', True)
                },
                
                'timestamps': {
                    'current_time': datetime.utcnow(),
                    'last_analysis': getattr(self.bot, 'last_analysis_time', None),
                    'last_trade': getattr(self.bot, 'last_trade_time', None),
                    'last_health_check': getattr(self.bot, 'last_health_check', None)
                }
            }
            
            # ✅ ЕДИНСТВЕННОЕ ИЗМЕНЕНИЕ: мы вызываем нашу универсальную функцию-очиститель
            # для всего собранного словаря. Это решает все проблемы с JSON.
            return self._sanitize_value(raw_status_data)
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при сборке статуса бота: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'is_running': getattr(self.bot, 'is_running', False)
            }
            
    def _sanitize_value(self, value):
        """ ✨ НОВЫЙ ВСПОМОГАТЕЛЬНЫЙ МЕТОД: Преобразует сложные типы в простые для JSON """
        if isinstance(value, Enum):
            # Самое главное: Преобразуем Enum в его строковое значение
            return value.value
        if isinstance(value, (datetime, pd.Timestamp)):
            return value.isoformat()
        if isinstance(value, (np.int64, np.int32)):
            return int(value)
        if isinstance(value, (np.float64, np.float32)):
            return float(value)
        if isinstance(value, (deque, set)):
            # Преобразуем deque и set в простой список
            return [self._sanitize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._sanitize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize_value(v) for v in value]
        if hasattr(value, '__dict__'):
             if not isinstance(value, (int, float, str, bool, type(None))) and type(value).__module__ != 'builtins':
                try:
                    if is_dataclass(value):
                         return self._sanitize_value(asdict(value))
                except (ImportError, TypeError):
                    # Если asdict не сработал или не является датаклассом, просто возвращаем строковое представление
                    return str(value)
        return value
            
    def emit_status_update(self):
        """Отправка обновления статуса через WebSocket"""
        try:
            if hasattr(self.bot, 'socketio') and self.bot.socketio:
                status_data = {
                    'status': self.bot.status.value,
                    'is_running': self.bot.is_running,
                    'active_pairs': len(self.bot.active_pairs),
                    'positions': len(self.bot.positions),
                    'cycles_count': self.bot.cycles_count,
                    'uptime': str(datetime.utcnow() - self.bot.start_time) if self.bot.start_time else '0:00:00'
                }
                self.bot.socketio.emit('bot_status_update', status_data)
        except Exception as e:
            logger.debug(f"Не удалось отправить обновление статуса: {e}")
            
    def _calculate_uptime(self) -> Optional[int]:
        """Рассчитать время работы в секундах"""
        if not self.bot.start_time:
            return 0
        
        end_time = self.bot.stop_time or datetime.utcnow()
        return int((end_time - self.bot.start_time).total_seconds())
        
    def _get_trades_today_count(self) -> int:
        """Получить количество сделок за сегодня"""
        try:
            from ...core.database import SessionLocal
            from ...core.models import Trade
            
            with SessionLocal() as db:
                today = datetime.utcnow().date()
                count = db.query(Trade).filter(
                    Trade.created_at >= today
                ).count()
                return count
        except:
            return 0
        
    def get_balance_info(self) -> Dict[str, Any]:
        """Получение информации о балансе"""
        try:
            # Проверяем наличие атрибутов
            total_balance = getattr(self.bot, 'balance', 0.0)
            available_balance = getattr(self.bot, 'available_balance', 0.0)
            locked_balance = getattr(self.bot, 'locked_balance', 0.0)
            
            # Если есть enhanced_exchange_client, получаем актуальные данные
            if hasattr(self.bot, 'enhanced_exchange_client') and self.bot.enhanced_exchange_client:
                try:
                    balance_info = self.bot.enhanced_exchange_client.get_balance()
                    if isinstance(balance_info, dict) and 'USDT' in balance_info:
                        usdt_balance = balance_info['USDT']
                        if isinstance(usdt_balance, dict):
                            total_balance = float(usdt_balance.get('total', total_balance))
                            available_balance = float(usdt_balance.get('free', available_balance))
                            locked_balance = float(usdt_balance.get('used', locked_balance))
                except Exception as e:
                    logger.warning(f"Не удалось получить баланс из exchange_client: {e}")
            
            return {
                'total_usdt': total_balance,
                'available_usdt': available_balance,
                'in_positions': locked_balance,
                'pnl_today': 0.0,  # TODO: Рассчитать из сделок
                'pnl_percent': 0.0,
                'source': 'bot_manager'
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return {
                'total_usdt': 0.0,
                'available_usdt': 0.0,
                'in_positions': 0.0,
                'pnl_today': 0.0,
                'pnl_percent': 0.0,
                'source': 'error'
            }
    
    def get_positions_info(self) -> Dict[str, Any]:
        """Получение информации о позициях"""
        try:
            positions = []
            total_pnl = 0.0
            
            # Если есть position_manager
            if hasattr(self.bot, 'position_manager') and self.bot.position_manager:
                try:
                    # Получаем позиции из position_manager
                    active_positions = self.bot.position_manager.get_all_positions()
                    for pos_id, pos_data in active_positions.items():
                        positions.append({
                            'id': pos_id,
                            'symbol': pos_data.get('symbol', 'UNKNOWN'),
                            'side': pos_data.get('side', 'BUY'),
                            'entry_price': float(pos_data.get('entry_price', 0)),
                            'current_price': float(pos_data.get('current_price', 0)),
                            'quantity': float(pos_data.get('quantity', 0)),
                            'pnl': float(pos_data.get('pnl', 0)),
                            'pnl_percent': float(pos_data.get('pnl_percent', 0)),
                            'strategy': pos_data.get('strategy', 'unknown')
                        })
                        total_pnl += float(pos_data.get('pnl', 0))
                except Exception as e:
                    logger.warning(f"Ошибка получения позиций из position_manager: {e}")
            
            return {
                'positions': positions,
                'count': len(positions),
                'total_pnl': round(total_pnl, 2),
                'source': 'bot_manager'
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения позиций: {e}")
            return {
                'positions': [],
                'count': 0,
                'total_pnl': 0.0,
                'source': 'error'
            }
    
    def _get_best_strategy(self) -> Optional[str]:
        """Получение лучшей стратегии"""
        if not self.bot.strategy_performance:
            return None
        
        best_strategy = max(
            self.bot.strategy_performance.items(),
            key=lambda x: x[1].get('win_rate', 0)
        )
        return best_strategy[0]

# Функция для получения экземпляра
def get_utilities(bot_manager):
    """Получить экземпляр утилит"""
    return Utilities(bot_manager)

# Экспорты
__all__ = ['Utilities', 'get_utilities']
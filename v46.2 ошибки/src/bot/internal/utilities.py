#!/usr/bin/env python3
"""
УТИЛИТЫ И СТАТУС - Utilities
Файл: src/bot/internal/utilities.py
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import is_dataclass, asdict
from enum import Enum
from collections import deque

# Импорты типов
from src.bot.internal.types import BotStatus

logger = logging.getLogger(__name__)

# ===== ФУНКЦИИ УРОВНЯ МОДУЛЯ (БЕЗ ОТСТУПОВ!) =====

def _calculate_uptime(bot_manager) -> str:
    """Рассчитать время работы"""
    if not hasattr(bot_manager, 'start_time') or not bot_manager.start_time:
        return "00:00:00"
    
    if not hasattr(bot_manager, 'is_running') or not bot_manager.is_running:
        return "00:00:00"
    
    uptime = datetime.utcnow() - bot_manager.start_time
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def _send_status_update_via_websocket(bot_manager, status_data):
    """Отправка обновления статуса через WebSocket"""
    try:
        if hasattr(bot_manager, 'socketio') and bot_manager.socketio:
            bot_manager.socketio.emit('bot_status_update', status_data)
    except Exception as e:
        logger.debug(f"Не удалось отправить обновление статуса: {e}")

def get_status(bot_manager) -> Dict[str, Any]:
    """
    Получение полного статуса бота
    Возвращает детальную информацию о состоянии всех компонентов
    """
    try:
        # Безопасное получение статуса
        if hasattr(bot_manager, 'status'):
            if hasattr(bot_manager.status, 'value'):
                # Это Enum
                status_value = bot_manager.status.value
            else:
                # Это строка
                status_value = str(bot_manager.status)
        else:
            status_value = 'unknown'
        
        # Базовая информация
        status = {
            'status': status_value,
            'is_running': getattr(bot_manager, 'is_running', False),
            'uptime': _calculate_uptime(bot_manager),
            'start_time': bot_manager.start_time.isoformat() if hasattr(bot_manager, 'start_time') and bot_manager.start_time else None,
            'cycles_count': getattr(bot_manager, 'cycles_count', 0),
            'active_pairs': getattr(bot_manager, 'active_pairs', []),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Добавляем информацию о балансе
        balance_info = get_balance_info(bot_manager)
        status['balance'] = balance_info
        
        # Добавляем информацию о позициях
        positions = get_positions_info(bot_manager)
        status['positions'] = {
            'count': len(positions),
            'list': positions
        }
        
        # Добавляем информацию о стратегиях
        if hasattr(bot_manager, 'strategy_instances'):
            status['strategies'] = {
                'active': list(bot_manager.strategy_instances.keys()),
                'count': len(bot_manager.strategy_instances)
            }
        
        # Добавляем информацию о задачах
        if hasattr(bot_manager, 'tasks'):
            status['tasks'] = {
                'count': len(bot_manager.tasks),
                'active': [name for name, task in bot_manager.tasks.items() if task and not task.done()]
            }
        
        # Отправляем обновление через WebSocket если доступен
        _send_status_update_via_websocket(bot_manager, status)
        
        return status
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}")
        return {
            'status': 'error',
            'is_running': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

def get_balance_info(bot_manager) -> Dict[str, Any]:
    """Получение информации о балансе для API"""
    try:
        # Проверяем атрибуты бота
        total_balance = getattr(bot_manager, 'balance', 0.0)
        available_balance = getattr(bot_manager, 'available_balance', 0.0)
        locked_balance = getattr(bot_manager, 'locked_balance', 0.0)
        
        # Если есть enhanced_exchange_client, получаем актуальные данные
        if hasattr(bot_manager, 'enhanced_exchange_client') and bot_manager.enhanced_exchange_client:
            try:
                balance_info = bot_manager.enhanced_exchange_client.get_balance()
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

def get_positions_info(bot_manager) -> List[Dict[str, Any]]:
    """Получение информации о позициях для API"""
    try:
        positions = []
        
        # Если есть position_manager
        if hasattr(bot_manager, 'position_manager') and bot_manager.position_manager:
            try:
                # Получаем позиции из position_manager
                active_positions = bot_manager.position_manager.get_all_positions()
                for pos_id, pos_data in active_positions.items():
                    positions.append({
                        'id': pos_id,
                        'symbol': pos_data.get('symbol', ''),
                        'side': pos_data.get('side', ''),
                        'size': pos_data.get('size', 0),
                        'entry_price': pos_data.get('entry_price', 0),
                        'current_price': pos_data.get('current_price', 0),
                        'pnl': pos_data.get('pnl', 0),
                        'pnl_percent': pos_data.get('pnl_percent', 0),
                        'status': pos_data.get('status', 'active')
                    })
            except Exception as e:
                logger.warning(f"Не удалось получить позиции из position_manager: {e}")
        
        # Если есть обычный positions dict
        if hasattr(bot_manager, 'positions') and isinstance(bot_manager.positions, dict):
            for symbol, position in bot_manager.positions.items():
                if isinstance(position, dict):
                    positions.append({
                        'id': symbol,
                        'symbol': symbol,
                        'side': position.get('side', 'buy'),
                        'size': position.get('size', 0),
                        'entry_price': position.get('entry_price', 0),
                        'current_price': position.get('current_price', 0),
                        'pnl': position.get('pnl', 0),
                        'pnl_percent': position.get('pnl_percent', 0),
                        'status': 'active'
                    })
        
        return positions
        
    except Exception as e:
        logger.error(f"Ошибка получения позиций: {e}")
        return []

def get_performance_stats(bot_manager):
    """Получение статистики производительности"""
    # Реализация функции
    return {}

def get_active_strategies(bot_manager):
    """Получение списка активных стратегий"""
    # Реализация функции
    return []

async def cleanup_old_data(bot_manager):
    """Очистка устаревших данных"""
    # Реализация функции
    pass

def format_balance_info(bot_manager, balance_info):
    """Форматирование информации о балансе"""
    # Реализация функции
    return balance_info

def log_trade_result(bot_manager, trade_result):
    """Логирование результата сделки"""
    # Реализация функции
    pass

# ===== КЛАСС UTILITIES =====

class Utilities:
    """Класс утилит"""
    
    def __init__(self, bot_manager):
        self.bot = bot_manager
    
    def get_status(self):
        """Получение статуса бота"""
        return get_status(self.bot)
    
    def get_performance_stats(self):
        """Получение статистики производительности"""
        return get_performance_stats(self.bot)
    
    def get_active_strategies(self):
        """Получение списка активных стратегий"""
        return get_active_strategies(self.bot)
    
    def get_balance_info(self):
        """Получение информации о балансе"""
        return get_balance_info(self.bot)
    
    def get_positions_info(self):
        """Получение информации о позициях"""
        return get_positions_info(self.bot)
    
    async def cleanup_old_data(self):
        """Очистка устаревших данных"""
        return await cleanup_old_data(self.bot)
    
    def format_balance_info(self, balance_info):
        """Форматирование информации о балансе"""
        return format_balance_info(self.bot, balance_info)
    
    def log_trade_result(self, trade_result):
        """Логирование результата сделки"""
        return log_trade_result(self.bot, trade_result)
    
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
                # Безопасное получение статуса
                if hasattr(self.bot, 'status'):
                    if hasattr(self.bot.status, 'value'):
                        status_value = self.bot.status.value
                    else:
                        status_value = str(self.bot.status)
                else:
                    status_value = 'unknown'
                    
                status_data = {
                    'status': status_value,
                    'is_running': self.bot.is_running,
                    'active_pairs': len(self.bot.active_pairs),
                    'positions': len(self.bot.positions),
                    'cycles_count': self.bot.cycles_count,
                    'uptime': str(datetime.utcnow() - self.bot.start_time) if self.bot.start_time else '0:00:00'
                }
                self.bot.socketio.emit('bot_status_update', status_data)
        except Exception as e:
            logger.debug(f"Не удалось отправить обновление статуса: {e}")
    
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
    
    def _get_best_strategy(self) -> Optional[str]:
        """Получение лучшей стратегии"""
        if not self.bot.strategy_performance:
            return None
        
        best_strategy = max(
            self.bot.strategy_performance.items(),
            key=lambda x: x[1].get('win_rate', 0)
        )
        return best_strategy[0]

# ===== ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ЭКЗЕМПЛЯРА =====

def get_utilities(bot_manager):
    """Получить экземпляр утилит"""
    return Utilities(bot_manager)

# Экспорты
__all__ = ['Utilities', 'get_utilities']
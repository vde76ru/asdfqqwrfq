#!/usr/bin/env python3
"""
МОНИТОРИНГ И ПРОВЕРКИ ЗДОРОВЬЯ - Monitoring
Файл: src/bot/internal/monitoring.py

Содержит все методы для мониторинга состояния системы:
- Проверка здоровья системы
- Enhanced данные и баланс
- Мониторинг enhanced систем
- Логирование статистики
"""

import asyncio
import logging
import psutil
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# Импорты типов
from src.bot.internal.types import ComponentStatus

logger = logging.getLogger(__name__)

def get_monitoring(bot_instance):
    """Возвращает объект с методами мониторинга"""
    
    class Monitoring:
        def __init__(self, bot):
            self.bot = bot
            
        async def monitor_performance(self):
            """Мониторинг производительности"""
            return await monitor_performance(self.bot)
            
        async def check_system_health(self):
            """Проверка состояния системы"""
            return await check_system_health(self.bot)
    
    return Monitoring(bot_instance)

class Monitoring:
    """Класс для мониторинга системы"""
    
    def __init__(self, bot_manager):
        self.bot = bot_manager
        
    async def _perform_health_check(self) -> Dict[str, Any]:
        """Проверка здоровья всей системы"""
        try:
            health_info = {
                'timestamp': datetime.utcnow().isoformat(),
                'overall_healthy': True,
                'components': {},
                'tasks': {},
                'system': {},
                'alerts': []
            }
            
            # Проверка компонентов
            for name, comp in self.bot.components.items():
                is_healthy = comp.status == ComponentStatus.READY
                if comp.last_heartbeat:
                    time_since_heartbeat = (datetime.utcnow() - comp.last_heartbeat).total_seconds()
                    is_healthy = is_healthy and time_since_heartbeat < comp.health_check_interval * 2
                
                health_info['components'][name] = {
                    'status': comp.status.value,
                    'healthy': is_healthy,
                    'last_heartbeat': comp.last_heartbeat.isoformat() if comp.last_heartbeat else None,
                    'restart_count': comp.restart_count
                }
                
                if not is_healthy and comp.is_critical:
                    health_info['overall_healthy'] = False
                    health_info['alerts'].append(f"Critical component {name} is unhealthy")
            
            # Проверка задач
            for name, task in self.bot.tasks.items():
                task_healthy = task and not task.done()
                health_info['tasks'][name] = {
                    'running': task_healthy,
                    'health': self.bot.task_health.get(name, 'unknown'),
                    'done': task.done() if task else True
                }
                
                if not task_healthy:
                    health_info['alerts'].append(f"Task {name} is not running")
            
            # Системные метрики
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                
                health_info['system'] = {
                    'memory_usage_mb': memory_info.rss / 1024 / 1024,
                    'cpu_percent': process.cpu_percent(),
                    'open_files': len(process.open_files()),
                    'threads': process.num_threads()
                }
                
                # Проверяем лимиты
                if health_info['system']['memory_usage_mb'] > 2048:  # 2GB
                    health_info['alerts'].append("High memory usage detected")
                
            except Exception as e:
                health_info['system']['error'] = str(e)
            
            # Проверка торговых лимитов
            if self.bot.trades_today >= self.bot.config.MAX_DAILY_TRADES * 0.9:
                health_info['alerts'].append("Approaching daily trade limit")
            
            if len(self.bot.positions) >= self.bot.config.MAX_POSITIONS * 0.9:
                health_info['alerts'].append("Approaching position limit")
            
            # Общее здоровье
            if health_info['alerts']:
                health_info['overall_healthy'] = False
            
            self.bot.last_health_check_time = datetime.utcnow().isoformat()
            return health_info
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки здоровья: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'overall_healthy': False,
                'error': str(e)
            }
    
    async def get_market_data_enhanced(self, symbol: str) -> Optional[Dict]:
        """Получение рыночных данных через enhanced API"""
        try:
            # Пробуем enhanced клиент
            if self.bot.v5_integration_enabled and self.bot.enhanced_exchange_client:
                data = await self.bot.enhanced_exchange_client.get_market_data(symbol)
                if data:
                    # Логируем источник данных
                    source = data.get('source', 'v5' if 'source' not in data else data['source'])
                    logger.debug(f"📊 {symbol} данные из {source}")
                    return data
                else:
                    logger.debug(f"⚠️ Enhanced API не вернул данные для {symbol}")
            
            # Fallback к legacy exchange
            if self.bot.exchange_client and hasattr(self.bot.exchange_client, 'get_ticker'):
                legacy_data = await self.bot.exchange_client.get_ticker(symbol)
                if legacy_data:
                    # Нормализуем к enhanced формату
                    return {
                        'symbol': symbol,
                        'timestamp': int(datetime.now().timestamp() * 1000),
                        'price': legacy_data.get('price', 0),
                        'bid': legacy_data.get('bid', 0),
                        'ask': legacy_data.get('ask', 0),
                        'volume': legacy_data.get('volume', 0),
                        'change': legacy_data.get('change_percent_24h', 0),
                        'source': 'legacy'
                    }
            
            logger.warning(f"⚠️ Не удалось получить данные для {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных {symbol}: {e}")
            return None
    
    async def get_account_balance_enhanced(self) -> Optional[Dict]:
        """Получение баланса через enhanced API"""
        try:
            # Пробуем enhanced клиент
            if self.bot.v5_integration_enabled and self.bot.enhanced_exchange_client:
                balance = await self.bot.enhanced_exchange_client.get_account_info()
                if balance:
                    logger.debug(f"💰 Баланс из {balance.get('source', 'v5')}")
                    return balance
            
            # Fallback к legacy
            if self.bot.exchange_client and hasattr(self.bot.exchange_client, 'get_balance'):
                legacy_balance = await self.bot.exchange_client.get_balance()
                if legacy_balance and 'error' not in legacy_balance:
                    return legacy_balance
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            return None
    
    async def monitor_enhanced_health(self):
        """Мониторинг состояния enhanced системы"""
        try:
            if self.bot.v5_integration_enabled and self.bot.enhanced_exchange_client:
                health = await self.bot.enhanced_exchange_client.health_check()
                
                # Логируем статистику каждые 10 минут
                if hasattr(self.bot, '_last_health_log'):
                    if datetime.now() - self.bot._last_health_log > timedelta(minutes=10):
                        self._log_health_stats(health)
                        self.bot._last_health_log = datetime.now()
                else:
                    self.bot._last_health_log = datetime.now()
                    self._log_health_stats(health)
                
                # Проверяем деградацию
                if health['overall_status'] == 'degraded':
                    logger.warning("⚠️ Enhanced система в режиме деградации")
                
                return health
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга health: {e}")
            return None
    
    def _log_health_stats(self, health: Dict):
        """Логирование статистики health"""
        try:
            stats = health.get('statistics', {})
            logger.info("📊 Enhanced система статистика:")
            logger.info(f"   V5 запросы: {stats.get('v5_requests', 0)}")
            logger.info(f"   Legacy запросы: {stats.get('legacy_requests', 0)}")
            logger.info(f"   Общий статус: {health.get('overall_status', 'unknown')}")
            
            # Миграционный статус
            if hasattr(self.bot.enhanced_exchange_client, 'get_migration_status'):
                migration = self.bot.enhanced_exchange_client.get_migration_status()
                logger.info(f"   V5 использование: {migration.get('v5_usage_percentage', 0):.1f}%")
                
        except Exception as e:
            logger.debug(f"Ошибка логирования health stats: {e}")

# Функция для получения экземпляра
def get_monitoring(bot_manager):
    """Получить экземпляр системы мониторинга"""
    return Monitoring(bot_manager)

# Экспорты
__all__ = ['Monitoring', 'get_monitoring']
"""
РАСШИРЕННЫЙ WEBSOCKET СЕРВЕР
============================
Файл: src/web/enhanced_websocket.py

Обеспечивает real-time обновления для дашборда
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Set, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from collections import defaultdict
import traceback

logger = logging.getLogger(__name__)

class EnhancedWebSocketManager:
    """
    Расширенный менеджер WebSocket соединений с полной функциональностью
    """
    
    def __init__(self):
        # Активные соединения
        self.active_connections: Set[WebSocket] = set()
        
        # Подписки по типам данных
        self.subscriptions: Dict[str, Set[WebSocket]] = defaultdict(set)
        
        # Очереди сообщений для каждого соединения
        self.message_queues: Dict[WebSocket, asyncio.Queue] = {}
        
        # Статистика
        self.stats = {
            'total_connections': 0,
            'messages_sent': 0,
            'messages_failed': 0,
            'bytes_sent': 0,
            'uptime_start': datetime.utcnow()
        }
        
        # Фоновые задачи
        self.background_tasks = []
        
        # Кеш последних данных
        self.data_cache = {
            'bot_status': {},
            'balance': {},
            'positions': [],
            'tickers': {},
            'trades': [],
            'strategies': {},
            'logs': []
        }
        
        logger.info("✅ EnhancedWebSocketManager инициализирован")
    
    async def connect(self, websocket: WebSocket) -> None:
        """Подключение нового клиента"""
        await websocket.accept()
        
        self.active_connections.add(websocket)
        self.message_queues[websocket] = asyncio.Queue()
        self.stats['total_connections'] += 1
        
        logger.info(f"🔌 WebSocket подключен. Активных: {len(self.active_connections)}")
        
        # Отправляем начальные данные
        await self._send_initial_data(websocket)
        
        # Запускаем обработчик сообщений для этого соединения
        task = asyncio.create_task(self._handle_client_messages(websocket))
        self.background_tasks.append(task)
    
    def disconnect(self, websocket: WebSocket) -> None:
        """Отключение клиента"""
        self.active_connections.discard(websocket)
        
        # Удаляем из всех подписок
        for subscribers in self.subscriptions.values():
            subscribers.discard(websocket)
        
        # Удаляем очередь сообщений
        if websocket in self.message_queues:
            del self.message_queues[websocket]
        
        logger.info(f"🔌 WebSocket отключен. Активных: {len(self.active_connections)}")
    
    async def _send_initial_data(self, websocket: WebSocket) -> None:
        """Отправка начальных данных при подключении"""
        try:
            initial_data = {
                'type': 'initial',
                'timestamp': datetime.utcnow().isoformat(),
                'data': {
                    'bot_status': self.data_cache['bot_status'],
                    'balance': self.data_cache['balance'],
                    'positions': self.data_cache['positions'],
                    'tickers': self.data_cache['tickers'],
                    'recent_trades': self.data_cache['trades'][-10:],
                    'strategies': self.data_cache['strategies']
                }
            }
            
            await websocket.send_json(initial_data)
            logger.info("📤 Отправлены начальные данные")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки начальных данных: {e}")
    
    async def _handle_client_messages(self, websocket: WebSocket) -> None:
        """Обработка сообщений от клиента"""
        try:
            while websocket in self.active_connections:
                try:
                    # Ждем сообщение с таймаутом
                    data = await asyncio.wait_for(
                        websocket.receive_text(), 
                        timeout=60.0  # 60 секунд таймаут
                    )
                    
                    # Обрабатываем сообщение
                    await self._process_client_message(websocket, data)
                    
                except asyncio.TimeoutError:
                    # Отправляем ping для проверки соединения
                    await websocket.send_json({'type': 'ping'})
                    
                except WebSocketDisconnect:
                    break
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки сообщения: {e}")
                    
        finally:
            self.disconnect(websocket)
    
    async def _process_client_message(self, websocket: WebSocket, data: str) -> None:
        """Обработка конкретного сообщения от клиента"""
        try:
            message = json.loads(data)
            msg_type = message.get('type')
            
            if msg_type == 'ping':
                # Отвечаем на ping
                await websocket.send_json({'type': 'pong'})
                
            elif msg_type == 'subscribe':
                # Подписка на определенные типы данных
                topics = message.get('topics', [])
                for topic in topics:
                    self.subscriptions[topic].add(websocket)
                logger.info(f"📊 Клиент подписан на: {topics}")
                
            elif msg_type == 'unsubscribe':
                # Отписка от типов данных
                topics = message.get('topics', [])
                for topic in topics:
                    self.subscriptions[topic].discard(websocket)
                    
            elif msg_type == 'command':
                # Обработка команд
                await self._handle_command(websocket, message)
                
        except json.JSONDecodeError:
            logger.error("❌ Неверный формат JSON")
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения: {e}")
    
    async def _handle_command(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """Обработка команд от клиента"""
        command = message.get('command')
        params = message.get('params', {})
        
        try:
            if command == 'get_history':
                # Запрос истории
                data_type = params.get('type', 'trades')
                limit = params.get('limit', 50)
                
                response = {
                    'type': 'history',
                    'data_type': data_type,
                    'data': self._get_history(data_type, limit)
                }
                
                await websocket.send_json(response)
                
            elif command == 'get_chart_data':
                # Запрос данных для графика
                symbol = params.get('symbol', 'BTCUSDT')
                interval = params.get('interval', '5m')
                
                # Здесь должна быть логика получения данных
                response = {
                    'type': 'chart_data',
                    'symbol': symbol,
                    'interval': interval,
                    'data': []  # Заполнить реальными данными
                }
                
                await websocket.send_json(response)
                
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения команды {command}: {e}")
            await websocket.send_json({
                'type': 'error',
                'message': str(e)
            })
    
    def _get_history(self, data_type: str, limit: int) -> List[Any]:
        """Получение исторических данных из кеша"""
        if data_type == 'trades':
            return self.data_cache['trades'][-limit:]
        elif data_type == 'logs':
            return self.data_cache['logs'][-limit:]
        else:
            return []
    
    # =================================================================
    # BROADCAST МЕТОДЫ
    # =================================================================
    
    async def broadcast(self, message_type: str, data: Dict[str, Any]) -> None:
        """Отправка сообщения всем подключенным клиентам"""
        message = {
            'type': message_type,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        
        await self._broadcast_to_subscribers('all', message)
    
    async def broadcast_to_topic(self, topic: str, message_type: str, data: Dict[str, Any]) -> None:
        """Отправка сообщения подписчикам конкретного топика"""
        message = {
            'type': message_type,
            'topic': topic,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        
        await self._broadcast_to_subscribers(topic, message)
    
    async def _broadcast_to_subscribers(self, topic: str, message: Dict[str, Any]) -> None:
        """Внутренний метод для отправки сообщений"""
        # Определяем получателей
        if topic == 'all':
            subscribers = self.active_connections
        else:
            subscribers = self.subscriptions.get(topic, set())
        
        if not subscribers:
            return
        
        # Сериализуем сообщение один раз
        message_json = json.dumps(message, default=str, ensure_ascii=False)
        message_bytes = len(message_json.encode('utf-8'))
        
        # Отправляем асинхронно всем подписчикам
        tasks = []
        for websocket in list(subscribers):
            tasks.append(self._send_to_client(websocket, message_json))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Подсчитываем статистику
        successful = sum(1 for r in results if r is True)
        self.stats['messages_sent'] += successful
        self.stats['messages_failed'] += len(results) - successful
        self.stats['bytes_sent'] += message_bytes * successful
    
    async def _send_to_client(self, websocket: WebSocket, message: str) -> bool:
        """Отправка сообщения конкретному клиенту"""
        try:
            await websocket.send_text(message)
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отправки клиенту: {e}")
            self.disconnect(websocket)
            return False
    
    # =================================================================
    # ОБНОВЛЕНИЕ ДАННЫХ
    # =================================================================
    
    async def update_bot_status(self, status: Dict[str, Any]) -> None:
        """Обновление статуса бота"""
        self.data_cache['bot_status'] = status
        await self.broadcast('bot_status', status)
    
    async def update_balance(self, balance: Dict[str, Any]) -> None:
        """Обновление баланса"""
        self.data_cache['balance'] = balance
        await self.broadcast('balance_update', balance)
    
    async def update_positions(self, positions: List[Dict[str, Any]]) -> None:
        """Обновление позиций"""
        self.data_cache['positions'] = positions
        
        # Рассчитываем общую статистику
        total_pnl = sum(p.get('pnl', 0) for p in positions)
        
        await self.broadcast('position_update', {
            'positions': positions,
            'total_pnl': total_pnl,
            'count': len(positions)
        })
    
    async def update_ticker(self, symbol: str, ticker_data: Dict[str, Any]) -> None:
        """Обновление тикера"""
        self.data_cache['tickers'][symbol] = ticker_data
        
        await self.broadcast_to_topic('tickers', 'ticker_update', {
            'symbol': symbol,
            'ticker': ticker_data
        })
    
    async def add_trade(self, trade: Dict[str, Any]) -> None:
        """Добавление новой сделки"""
        self.data_cache['trades'].append(trade)
        
        # Храним только последние 1000 сделок
        if len(self.data_cache['trades']) > 1000:
            self.data_cache['trades'] = self.data_cache['trades'][-1000:]
        
        await self.broadcast('new_trade', trade)
    
    async def update_strategies(self, strategies: Dict[str, Any]) -> None:
        """Обновление информации о стратегиях"""
        self.data_cache['strategies'] = strategies
        await self.broadcast('strategy_update', {'strategies': strategies})
    
    async def add_log(self, level: str, message: str, source: str = 'system') -> None:
        """Добавление лога"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level,
            'message': message,
            'source': source
        }
        
        self.data_cache['logs'].append(log_entry)
        
        # Храним только последние 500 логов
        if len(self.data_cache['logs']) > 500:
            self.data_cache['logs'] = self.data_cache['logs'][-500:]
        
        await self.broadcast_to_topic('logs', 'log_message', log_entry)
    
    # =================================================================
    # СТАТИСТИКА И МОНИТОРИНГ
    # =================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики WebSocket сервера"""
        uptime = (datetime.utcnow() - self.stats['uptime_start']).total_seconds()
        
        return {
            'active_connections': len(self.active_connections),
            'total_connections': self.stats['total_connections'],
            'messages_sent': self.stats['messages_sent'],
            'messages_failed': self.stats['messages_failed'],
            'bytes_sent': self.stats['bytes_sent'],
            'uptime_seconds': int(uptime),
            'subscriptions': {
                topic: len(subscribers) 
                for topic, subscribers in self.subscriptions.items()
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья WebSocket сервера"""
        try:
            # Проверяем что можем отправить сообщение всем клиентам
            test_message = {'type': 'health_check', 'timestamp': datetime.utcnow().isoformat()}
            
            tasks = []
            for ws in self.active_connections:
                tasks.append(ws.send_json(test_message))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            healthy_connections = sum(1 for r in results if not isinstance(r, Exception))
            
            return {
                'status': 'healthy' if healthy_connections == len(self.active_connections) else 'degraded',
                'healthy_connections': healthy_connections,
                'total_connections': len(self.active_connections),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def cleanup(self) -> None:
        """Очистка ресурсов"""
        logger.info("🧹 Начинаем очистку WebSocket соединений...")
        
        # Отправляем сообщение о завершении
        await self.broadcast('shutdown', {'message': 'Server is shutting down'})
        
        # Закрываем все соединения
        for websocket in list(self.active_connections):
            try:
                await websocket.close()
            except Exception as e:
                logger.error(f"Ошибка закрытия соединения: {e}")
        
        # Отменяем фоновые задачи
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        
        logger.info("✅ WebSocket соединения закрыты")


# =================================================================
# ИНТЕГРАЦИЯ С BOT MANAGER
# =================================================================

class WebSocketBotIntegration:
    """
    Интеграция WebSocket с BotManager для real-time обновлений
    """
    
    def __init__(self, ws_manager: EnhancedWebSocketManager, bot_manager):
        self.ws_manager = ws_manager
        self.bot_manager = bot_manager
        self.update_interval = 2  # Обновление каждые 2 секунды
        self.running = False
        self._update_task = None
        
    async def start(self):
        """Запуск интеграции"""
        self.running = True
        self._update_task = asyncio.create_task(self._update_loop())
        logger.info("✅ WebSocket интеграция запущена")
        
    async def stop(self):
        """Остановка интеграции"""
        self.running = False
        if self._update_task:
            self._update_task.cancel()
        logger.info("⏹️ WebSocket интеграция остановлена")
    
    async def _update_loop(self):
        """Основной цикл обновлений"""
        while self.running:
            try:
                # Получаем данные от бота
                if self.bot_manager:
                    # Статус бота
                    bot_status = self.bot_manager.get_status()
                    await self.ws_manager.update_bot_status(bot_status)
                    
                    # Баланс
                    balance = self._get_balance_from_bot()
                    if balance:
                        await self.ws_manager.update_balance(balance)
                    
                    # Позиции
                    positions = self._get_positions_from_bot()
                    await self.ws_manager.update_positions(positions)
                    
                    # Стратегии
                    strategies = self._get_strategies_from_bot()
                    await self.ws_manager.update_strategies(strategies)
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле обновлений: {e}")
                await asyncio.sleep(5)  # Пауза при ошибке
    
    def _get_balance_from_bot(self) -> Optional[Dict[str, Any]]:
        """Получение баланса от бота"""
        try:
            # Здесь должна быть реальная логика получения баланса
            return {
                'total_usdt': 10000,
                'available_usdt': 9500,
                'in_positions': 500,
                'change_24h': 2.5
            }
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return None
    
    def _get_positions_from_bot(self) -> List[Dict[str, Any]]:
        """Получение позиций от бота"""
        try:
            # Здесь должна быть реальная логика получения позиций
            return []
        except Exception as e:
            logger.error(f"Ошибка получения позиций: {e}")
            return []
    
    def _get_strategies_from_bot(self) -> Dict[str, Any]:
        """Получение информации о стратегиях"""
        try:
            # Здесь должна быть реальная логика получения стратегий
            return {}
        except Exception as e:
            logger.error(f"Ошибка получения стратегий: {e}")
            return {}


# =================================================================
# WEBSOCKET ENDPOINT
# =================================================================

async def enhanced_websocket_endpoint(websocket: WebSocket, ws_manager: EnhancedWebSocketManager):
    """
    WebSocket endpoint для подключения клиентов
    """
    await ws_manager.connect(websocket)
    
    try:
        while True:
            # Просто держим соединение открытым
            # Вся логика обработки в _handle_client_messages
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"❌ Ошибка в WebSocket endpoint: {e}")
        logger.error(traceback.format_exc())
    finally:
        ws_manager.disconnect(websocket)


# =================================================================
# ФАБРИКА
# =================================================================

def create_enhanced_websocket_manager() -> EnhancedWebSocketManager:
    """Создание экземпляра расширенного WebSocket менеджера"""
    return EnhancedWebSocketManager()


# =================================================================
# ЭКСПОРТЫ
# =================================================================

__all__ = [
    'EnhancedWebSocketManager',
    'WebSocketBotIntegration',
    'enhanced_websocket_endpoint',
    'create_enhanced_websocket_manager'
]
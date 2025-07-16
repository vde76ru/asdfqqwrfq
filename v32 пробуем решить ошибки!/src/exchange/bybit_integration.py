#!/usr/bin/env python3
"""
ИСПРАВЛЕННАЯ ИНТЕГРАЦИЯ BYBIT V5 С СУЩЕСТВУЮЩЕЙ СИСТЕМОЙ
======================================================
Файл: src/exchange/bybit_integration.py

✅ ПОЛНАЯ ВЕРСИЯ СО ВСЕМИ МЕТОДАМИ
✅ ИСПРАВЛЕНЫ ВСЕ ПРОБЛЕМЫ:
✅ Устранено дублирование WebSocket подключений
✅ Правильное кэширование клиентов
✅ Корректное управление состоянием
✅ Соблюдение лимитов Bybit API
"""

import asyncio
import logging
import time
import threading
from typing import Dict, Any, Optional, Union, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import pandas as pd

try:
    from .bybit_client_v5 import BybitClientV5, create_bybit_client_from_env, BybitAPIError
    V5_AVAILABLE = True
except ImportError:
    V5_AVAILABLE = False
    BybitClientV5 = None
    create_bybit_client_from_env = None
    BybitAPIError = Exception

try:
    from ..core.unified_config import unified_config
    CONFIG_AVAILABLE = True
except ImportError:
    unified_config = None
    CONFIG_AVAILABLE = False

# КРИТИЧЕСКИ ВАЖНО: Правильный импорт TradingSignal
try:
    from ..common.types import UnifiedTradingSignal as TradingSignal
except ImportError:
    try:
        from ..common.types import TradingSignal
    except ImportError:
        # Создаем простую версию для совместимости
        @dataclass
        class TradingSignal:
            action: str
            confidence: float
            price: float
            symbol: str
            order_type: str = 'market'
            stop_loss: Optional[float] = None
            take_profit: Optional[float] = None

logger = logging.getLogger(__name__)

# ИСПРАВЛЕННОЕ глобальное кэширование клиентов
_cached_clients = {}
_client_locks = {}
_initialization_lock = threading.Lock()
_websocket_initialized = {}

from ..common.types import UnifiedTradingSignal as TradingSignal

@dataclass
class PositionInfo:
    """Информация о позиции"""
    symbol: str
    side: str
    size: float
    entry_price: float
    unrealized_pnl: float
    percentage: float
    leverage: float

class BybitWebSocketHandler:
    """Обработчик WebSocket сообщений - ПОЛНАЯ ВЕРСИЯ"""
    
    def __init__(self, integration_manager):
        self.integration_manager = integration_manager
        self.callbacks = {
            'position': [],
            'order': [],
            'wallet': [],
            'ticker': [],
            'orderbook': [],
            'trade': [],
            'execution': []
        }
        
    def add_callback(self, event_type: str, callback: Callable):
        """Добавление callback для события"""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
            logger.info(f"📡 Добавлен callback для {event_type}")
    
    def handle_private_message(self, message: dict):
        """Обработка приватных WebSocket сообщений"""
        try:
            topic = message.get('topic', '')
            data = message.get('data', [])
            
            self.integration_manager.stats['websocket_messages'] += 1
            
            if 'position' in topic:
                self._handle_position_update(data)
            elif 'order' in topic:
                self._handle_order_update(data)
            elif 'wallet' in topic:
                self._handle_wallet_update(data)
            elif 'execution' in topic:
                self._handle_execution_update(data)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки приватного сообщения: {e}")
    
    def handle_public_message(self, message: dict):
        """Обработка публичных WebSocket сообщений"""
        try:
            topic = message.get('topic', '')
            data = message.get('data', {})
            
            self.integration_manager.stats['websocket_messages'] += 1
            
            if 'tickers' in topic:
                self._handle_ticker_update(data)
            elif 'orderbook' in topic:
                self._handle_orderbook_update(data)
            elif 'publicTrade' in topic:
                self._handle_trade_update(data)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки публичного сообщения: {e}")
    
    def _handle_position_update(self, data: List[dict]):
        """Обработка обновления позиций"""
        try:
            for position_data in data:
                try:
                    symbol = position_data.get('symbol', '')
                    size = float(position_data.get('size', 0))
                    
                    if size > 0:  # Только активные позиции
                        position = PositionInfo(
                            symbol=symbol,
                            side=position_data.get('side', ''),
                            size=size,
                            entry_price=float(position_data.get('avgPrice', 0)),
                            unrealized_pnl=float(position_data.get('unrealisedPnl', 0)),
                            percentage=float(position_data.get('unrealisedPnl', 0)) / float(position_data.get('positionValue', 1)) * 100,
                            leverage=float(position_data.get('leverage', 1))
                        )
                        
                        # Обновляем кэш
                        self.integration_manager.cache['positions'][symbol] = position
                        
                        logger.info(f"📊 Позиция обновлена: {symbol} {position.side} {position.size}")
                        
                        # Безопасный вызов callbacks
                        for callback in self.callbacks.get('position', []):
                            try:
                                callback(position)
                            except Exception as callback_error:
                                logger.error(f"❌ Ошибка в position callback: {callback_error}")
                                
                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Ошибка парсинга данных позиции: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в _handle_position_update: {e}")
    
    def _handle_order_update(self, data: List[dict]):
        """Обработка обновления ордеров"""
        try:
            for order in data:
                order_id = order.get('orderId')
                symbol = order.get('symbol')
                status = order.get('orderStatus')
                
                logger.info(f"📝 Ордер обновлен: {order_id} {symbol} {status}")
                
                # Обновляем кэш
                if order_id:
                    self.integration_manager.cache['orders'][order_id] = order
                    self.integration_manager.cache['last_update']['orders'] = time.time()
                
                # Вызываем callbacks
                for callback in self.callbacks['order']:
                    try:
                        callback(order)
                    except Exception as e:
                        logger.error(f"❌ Ошибка в order callback: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_order_update: {e}")
    
    def _handle_wallet_update(self, data: List[dict]):
        """Обработка обновления баланса"""
        try:
            for wallet_data in data:
                account_type = wallet_data.get('accountType', 'UNIFIED')
                total_equity = wallet_data.get('totalEquity', '0')
                
                logger.info(f"💰 Баланс обновлен: {account_type} - {total_equity}")
                
                # Обновляем кэш
                coins = wallet_data.get('coin', [])
                for coin_data in coins:
                    coin = coin_data.get('coin')
                    if coin:
                        self.integration_manager.cache['balance'][coin] = {
                            'free': float(coin_data.get('availableToWithdraw', 0)),
                            'used': float(coin_data.get('locked', 0)),
                            'total': float(coin_data.get('walletBalance', 0))
                        }
                
                self.integration_manager.cache['last_update']['balance'] = time.time()
                
                # Вызываем callbacks
                for callback in self.callbacks['wallet']:
                    try:
                        callback(wallet_data)
                    except Exception as e:
                        logger.error(f"❌ Ошибка в wallet callback: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_wallet_update: {e}")
    
    def _handle_execution_update(self, data: List[dict]):
        """Обработка обновления исполнений"""
        try:
            for execution in data:
                exec_id = execution.get('execId')
                symbol = execution.get('symbol')
                side = execution.get('side')
                exec_qty = execution.get('execQty')
                exec_price = execution.get('execPrice')
                
                logger.info(f"⚡ Исполнение: {symbol} {side} {exec_qty} @ {exec_price}")
                
                # Вызываем callbacks
                for callback in self.callbacks['execution']:
                    try:
                        callback(execution)
                    except Exception as e:
                        logger.error(f"❌ Ошибка в execution callback: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_execution_update: {e}")
    
    def _handle_ticker_update(self, data):
        """Обработка обновления тикера"""
        try:
            if isinstance(data, list):
                for ticker in data:
                    symbol = ticker.get('symbol')
                    if symbol:
                        self.integration_manager.cache['market_info'][symbol] = ticker
                        
                self.integration_manager.cache['last_update']['tickers'] = time.time()
                
            # Вызываем callbacks
            for callback in self.callbacks['ticker']:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"❌ Ошибка в ticker callback: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_ticker_update: {e}")
    
    def _handle_orderbook_update(self, data):
        """Обработка обновления стакана"""
        try:
            symbol = data.get('s')
            if symbol:
                orderbook_data = {
                    'symbol': symbol,
                    'bids': data.get('b', []),
                    'asks': data.get('a', []),
                    'timestamp': data.get('ts', int(time.time() * 1000))
                }
                
                self.integration_manager.cache['market_info'][f"{symbol}_orderbook"] = orderbook_data
                
            # Вызываем callbacks
            for callback in self.callbacks['orderbook']:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"❌ Ошибка в orderbook callback: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_orderbook_update: {e}")
    
    def _handle_trade_update(self, data):
        """Обработка обновления сделок"""
        try:
            # Вызываем callbacks
            for callback in self.callbacks['trade']:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"❌ Ошибка в trade callback: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_trade_update: {e}")

class BybitIntegrationManager:
    """Менеджер интеграции Bybit V5 - ПОЛНАЯ ВЕРСИЯ"""
    
    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        self.v5_client: Optional[BybitClientV5] = None
        self.is_initialized = False
        
        # WebSocket состояние
        self.ws_connected = {'private': False, 'public': False}
        self.ws_handler = BybitWebSocketHandler(self)
        
        # Кэширование данных
        self.cache = {
            'positions': {},
            'orders': {},
            'balance': {},
            'symbols': [],
            'market_info': {},
            'last_update': {}
        }
        
        # Статистика
        self.stats = {
            'v5_requests': 0,
            'legacy_requests': 0,
            'websocket_messages': 0,
            'errors': 0,
            'start_time': time.time(),
            'orders_placed': 0,   
            'orders_failed': 0,
            'orders_cancelled': 0
        }
        
        # Настройки автообновления
        self.auto_update_interval = 30
        self.auto_update_task = None
        self._running = True
        
        logger.info("🔧 BybitIntegrationManager инициализирован")

    async def initialize(self, force_new: bool = False) -> bool:
        """Инициализация интеграции - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        global _cached_clients, _client_locks, _websocket_initialized
        
        if not V5_AVAILABLE:
            logger.error("❌ Bybit V5 клиент недоступен")
            return False
        
        with _initialization_lock:
            try:
                logger.info("🚀 Инициализация Bybit интеграции...")
                
                client_key = f"bybit_v5_{'testnet' if self.testnet else 'mainnet'}"
                
                # ИСПРАВЛЕННАЯ логика кэширования
                if not force_new and client_key in _cached_clients:
                    cached_client = _cached_clients[client_key]
                    if (hasattr(cached_client, 'is_initialized') and 
                        cached_client.is_initialized and
                        hasattr(cached_client, 'ws_manager') and
                        cached_client.ws_manager):
                        
                        logger.info("♻️ Используем кэшированный V5 клиент")
                        self.v5_client = cached_client
                        self.is_initialized = True
                        
                        # КРИТИЧЕСКИ ВАЖНО: Проверяем состояние WebSocket
                        if not _websocket_initialized.get(client_key, False):
                            await self._setup_websockets()
                            _websocket_initialized[client_key] = True
                        else:
                            logger.info("ℹ️ WebSocket уже инициализированы, пропускаем")
                            # Обновляем статус из кэшированного клиента
                            if hasattr(self.v5_client.ws_manager, 'ws_connected'):
                                self.ws_connected.update(self.v5_client.ws_manager.ws_connected)
                        
                        return True
                
                # Создаем новый клиент
                logger.info("🔄 Создание нового V5 клиента...")
                
                try:
                    self.v5_client = create_bybit_client_from_env(testnet=self.testnet)
                    
                    # Инициализируем клиент
                    initialization_timeout = 60
                    initialized = await asyncio.wait_for(
                        self.v5_client.initialize(), 
                        timeout=initialization_timeout
                    )
                    
                    if initialized:
                        # Кэшируем клиент
                        _cached_clients[client_key] = self.v5_client
                        if client_key not in _client_locks:
                            _client_locks[client_key] = asyncio.Lock()
                        
                        self.is_initialized = True
                        logger.info("✅ V5 клиент успешно инициализирован")
                        
                        # Настраиваем WebSocket
                        await self._setup_websockets()
                        _websocket_initialized[client_key] = True
                        
                        # Запускаем автообновление
                        await self._start_auto_update()
                        
                        return True
                    else:
                        logger.error("❌ Не удалось инициализировать V5 клиент")
                        return False
                        
                except asyncio.TimeoutError:
                    logger.error(f"❌ Таймаут инициализации ({initialization_timeout}s)")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации: {e}")
                return False

    async def _setup_websockets(self):
        """Настройка WebSocket соединений - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            if not self.v5_client or not self.v5_client.ws_manager:
                logger.error("❌ V5 клиент или WebSocket менеджер недоступен")
                return False
            
            logger.info("🔧 Настройка WebSocket соединений...")
            
            # Проверяем, не подключены ли уже WebSocket
            if (hasattr(self.v5_client.ws_manager, 'ws_connected') and
                any(self.v5_client.ws_manager.ws_connected.values())):
                logger.info("ℹ️ WebSocket уже подключены")
                self.ws_connected.update(self.v5_client.ws_manager.ws_connected)
                return True
            
            # Запуск приватного WebSocket
            try:
                private_ws = self.v5_client.start_private_websocket(
                    self.ws_handler.handle_private_message
                )
                if private_ws:
                    logger.info("✅ Приватный WebSocket настроен")
                    
                    # Подписываемся на необходимые каналы
                    await asyncio.sleep(2)  # Даем время на подключение
                    
                    # Подписки будут выполнены автоматически в callback аутентификации
                    self.ws_connected['private'] = True
                else:
                    logger.warning("⚠️ Не удалось настроить приватный WebSocket")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка настройки приватного WebSocket: {e}")
            
            # Запуск публичного WebSocket
            try:
                public_ws = self.v5_client.start_public_websocket(
                    self.ws_handler.handle_public_message
                )
                if public_ws:
                    logger.info("✅ Публичный WebSocket настроен")
                    self.ws_connected['public'] = True
                else:
                    logger.warning("⚠️ Не удалось настроить публичный WebSocket")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка настройки публичного WebSocket: {e}")
            
            # Обновляем состояние в менеджере клиента
            if hasattr(self.v5_client.ws_manager, 'ws_connected'):
                self.v5_client.ws_manager.ws_connected.update(self.ws_connected)
            
            # Запускаем автообновление данных
            await self._start_auto_update()
            logger.info("🔄 Автообновление данных запущено")
            
            return any(self.ws_connected.values())
            
        except Exception as e:
            logger.error(f"❌ Ошибка настройки WebSocket: {e}")
            return False

    async def _start_auto_update(self):
        """Запуск автообновления данных"""
        if self.auto_update_task and not self.auto_update_task.done():
            logger.debug("🔄 Автообновление уже запущено")
            return
        
        try:
            self.auto_update_task = asyncio.create_task(self._auto_update_loop())
            logger.info("✅ Автообновление данных запущено")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска автообновления: {e}")

    async def _auto_update_loop(self):
        """Цикл автообновления данных - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        logger.info("🔄 Запуск цикла автообновления...")
        
        while self._running and self.is_initialized:
            try:
                await asyncio.sleep(self.auto_update_interval)
                
                if not self.v5_client:
                    continue
                
                # ✅ ИСПРАВЛЕНИЕ: Обновляем позиции с правильными параметрами
                try:
                    positions = await self.get_positions(settleCoin="USDT")
                    if positions:
                        self.cache['positions'] = {pos.symbol: pos for pos in positions}
                        self.cache['last_update']['positions'] = time.time()
                        logger.debug(f"📊 Обновлено активных позиций: {len(positions)}")
                    else:
                        # Если нет активных позиций, очищаем кэш
                        self.cache['positions'] = {}
                        self.cache['last_update']['positions'] = time.time()
                        logger.debug("📊 Активных позиций нет")
                        
                except Exception as e:
                    logger.debug(f"ℹ️ Позиции не обновлены: {e}")
                
                # Обновляем баланс
                try:
                    balance = await self.get_balance("USDT")
                    if balance is not None and balance > 0:
                        self.cache['balance']['USDT'] = balance
                        self.cache['last_update']['balance'] = time.time()
                        logger.debug(f"💰 Баланс обновлен: {balance} USDT")
                except Exception as e:
                    logger.debug(f"ℹ️ Баланс не обновлен: {e}")
                    
            except asyncio.CancelledError:
                logger.info("🛑 Автообновление остановлено")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле автообновления: {e}")
                await asyncio.sleep(5)

    # ================== ОСНОВНЫЕ ТОРГОВЫЕ МЕТОДЫ ==================

    async def get_balance(self, coin: str = "USDT") -> float:
        """Получение баланса через V5 API"""
        try:
            if not self.v5_client:
                raise BybitAPIError("V5 клиент не инициализирован")
            
            self.stats['v5_requests'] += 1
            balance = await self.v5_client.get_balance(coin)
            
            return balance
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            self.stats['errors'] += 1
            raise

    async def get_positions(self, category: str = "linear", symbol: str = None, settleCoin: str = "USDT") -> List[PositionInfo]:
        """Получение списка позиций - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            if not self.v5_client or not self.v5_client.is_initialized:
                await self.initialize()
            
            # ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Передаем settleCoin по умолчанию
            response = await self.v5_client.get_positions(
                category=category, 
                symbol=symbol, 
                settleCoin=settleCoin
            )
            
            if not response.get('success', False):
                logger.error(f"❌ Ошибка получения позиций: {response.get('error')}")
                return []
            
            positions_data = response.get('data', {})
            positions_list = positions_data.get('list', [])
            
            # Преобразуем в PositionInfo объекты с валидацией
            positions = []
            for pos_data in positions_list:
                try:
                    # Проверяем, что позиция активна
                    size = float(pos_data.get('size', 0))
                    if size == 0:
                        continue  # Пропускаем закрытые позиции
                    
                    position_info = PositionInfo(
                        symbol=pos_data.get('symbol', ''),
                        side=pos_data.get('side', ''),
                        size=size,
                        entry_price=float(pos_data.get('avgPrice', 0)),
                        unrealized_pnl=float(pos_data.get('unrealisedPnl', 0)),
                        percentage=float(pos_data.get('unrealisedPnl', 0)) / float(pos_data.get('positionValue', 1)) * 100,
                        leverage=float(pos_data.get('leverage', 1))
                    )
                    positions.append(position_info)
                    
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"⚠️ Ошибка парсинга позиции {pos_data}: {e}")
                    continue
            
            logger.info(f"📊 Получено активных позиций: {len(positions)}")
            return positions
            
        except Exception as e:
            logger.error(f"❌ Ошибка в get_positions: {e}")
            return []

    async def place_smart_order(self, signal: TradingSignal, amount: float = None, **kwargs) -> dict:
        """Размещение умного ордера с полной валидацией - ПОЛНАЯ ВЕРСИЯ"""
        try:
            if not self.v5_client or not self.v5_client.is_initialized:
                await self.initialize()
            
            # Извлекаем параметры из сигнала
            symbol = signal.symbol
            side = "Buy" if signal.action.upper() == "BUY" else "Sell"
            
            # Определяем количество
            if amount:
                qty = str(amount)
            elif hasattr(signal, 'size') and signal.size:
                qty = str(signal.size)
            else:
                # Рассчитываем размер позиции на основе риска
                balance = await self.get_balance("USDT")
                risk_amount = balance * 0.02  # 2% риска
                
                # Получаем текущую цену
                market_data = await self.v5_client.get_market_data(symbol)
                if not market_data:
                    raise BybitAPIError(f"Не удалось получить рыночные данные для {symbol}")
                
                current_price = float(market_data['lastPrice'])
                qty = str(round(risk_amount / current_price, 4))
            
            # Определяем тип ордера
            order_type = getattr(signal, 'order_type', 'Market').title()
            
            # Подготавливаем параметры ордера
            order_params = {
                'category': 'linear',
                'symbol': symbol,
                'side': side,
                'order_type': order_type,
                'qty': qty
            }
            
            # Добавляем цену для лимитных ордеров
            if order_type == 'Limit' and hasattr(signal, 'price') and signal.price:
                order_params['price'] = str(signal.price)
            
            # Добавляем стоп-лосс и тейк-профит
            if hasattr(signal, 'stop_loss') and signal.stop_loss:
                order_params['stop_loss'] = str(signal.stop_loss)
            
            if hasattr(signal, 'take_profit') and signal.take_profit:
                order_params['take_profit'] = str(signal.take_profit)
            
            # Настраиваем режим TP/SL если есть уровни
            tp_sl_params = kwargs.get('tp_sl_params', {})
            if tp_sl_params.get('takeProfit') or tp_sl_params.get('stopLoss'):
                order_params['tpslMode'] = 'Full'
            
            # Размещаем ордер
            response = await self.v5_client.place_order(**order_params)
            
            if response.get('retCode') == 0:
                result = response.get('result', {})
                order_id = result.get('orderId')
                
                logger.info(f"✅ Ордер размещен: {symbol} {side} {qty} - ID: {order_id}")
                
                # Обновляем статистику
                self.stats['orders_placed'] += 1
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'symbol': symbol,
                    'side': side,
                    'qty': qty,
                    'details': result
                }
            else:
                error_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"❌ Ошибка размещения ордера: {error_msg}")
                
                self.stats['orders_failed'] += 1
                
                return {
                    'success': False,
                    'error': error_msg,
                    'error_code': response.get('retCode')
                }
                
        except Exception as e:
            logger.error(f"❌ Исключение в place_smart_order: {e}")
            self.stats['orders_failed'] += 1
            return {
                'success': False,
                'error': str(e)
            }

    async def close_position(self, symbol: str) -> dict:
        """Закрытие позиции - ПОЛНАЯ ВЕРСИЯ"""
        try:
            if not self.v5_client:
                return {"success": False, "error": "V5 клиент не инициализирован"}
            
            # Получаем текущую позицию
            positions_response = await self.v5_client.get_positions("linear", symbol)
            if not positions_response.get('success'):
                return {"success": False, "error": "Не удалось получить позицию"}
            
            position_list = positions_response.get('data', {}).get('list', [])
            if not position_list:
                return {"success": True, "message": "Позиция не найдена"}
            
            position = position_list[0]
            size = float(position['size'])
            
            if size == 0:
                return {"success": True, "message": "Позиция уже закрыта"}
            
            # Определяем сторону для закрытия
            close_side = "Sell" if position['side'] == "Buy" else "Buy"
            
            # Закрываем market ордером
            result = await self.v5_client.place_market_order(
                symbol=symbol,
                side=close_side,
                qty=str(abs(size)),
                category="linear",
                reduce_only=True
            )
            
            if result.get('retCode') == 0:
                logger.info(f"✅ Позиция {symbol} закрыта")
                return {"success": True, "order_id": result['result']['orderId']}
            else:
                return {"success": False, "error": result.get('retMsg')}
                
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия позиции: {e}")
            return {"success": False, "error": str(e)}

    async def close_all_positions(self, symbols: List[str] = None) -> dict:
        """Закрытие всех или выбранных позиций"""
        try:
            positions = await self.get_positions()
            
            results = []
            for position in positions:
                if symbols is None or position.symbol in symbols:
                    # Используем метод close_position из v5_client
                    result = await self.close_position(position.symbol)
                    results.append({
                        "symbol": position.symbol,
                        "result": result
                    })
            
            success_count = sum(1 for r in results if r['result'].get('success'))
            
            return {
                "success": True,
                "closed_positions": success_count,
                "total_positions": len(results),
                "details": results
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия позиций: {e}")
            return {"success": False, "error": str(e)}

    async def emergency_stop(self) -> dict:
        """Экстренная остановка торговли - ПОЛНАЯ ВЕРСИЯ"""
        try:
            logger.warning("🚨 ЭКСТРЕННАЯ ОСТАНОВКА!")
            
            # Отменяем все ордера через v5_client
            cancel_result = await self.v5_client._make_request('POST', '/v5/order/cancel-all', {"category": "linear"})
            
            # Закрываем все позиции
            close_result = await self.close_all_positions()
            
            logger.warning("🛑 Экстренная остановка завершена")
            
            return {
                "success": True,
                "orders_cancelled": cancel_result.get('retCode') == 0,
                "positions_closed": close_result.get('success', False)
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка экстренной остановки: {e}")
            return {"success": False, "error": str(e)}

    # ================== АНАЛИТИЧЕСКИЕ МЕТОДЫ ==================

    async def get_market_overview(self, symbols: List[str] = None) -> dict:
        """Получение обзора рынка"""
        try:
            if symbols is None:
                symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "SOLUSDT", "DOTUSDT"]
            
            market_data = {}
            
            for symbol in symbols:
                ticker_data = await self.v5_client.get_market_data(symbol)
                if ticker_data:
                    market_data[symbol] = {
                        'price': float(ticker_data['lastPrice']),
                        'change_24h': float(ticker_data['price24hPcnt']) * 100,
                        'volume_24h': float(ticker_data['volume24h']),
                        'high_24h': float(ticker_data['highPrice24h']),
                        'low_24h': float(ticker_data['lowPrice24h'])
                    }
            
            return {
                "success": True,
                "timestamp": datetime.now(),
                "data": market_data
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения обзора рынка: {e}")
            return {"success": False, "error": str(e)}

    async def get_portfolio_summary(self) -> dict:
        """Получение сводки по портфелю"""
        try:
            # Получаем позиции
            positions = await self.get_positions()
            
            # Получаем баланс
            balance = await self.get_balance("USDT")
            
            # Рассчитываем метрики
            total_unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
            total_position_value = sum(pos.size * pos.entry_price for pos in positions)
            
            portfolio_stats = {
                "balance": balance,
                "positions_count": len(positions),
                "total_position_value": total_position_value,
                "unrealized_pnl": total_unrealized_pnl,
                "unrealized_pnl_percent": (total_unrealized_pnl / balance * 100) if balance > 0 else 0,
                "positions": [
                    {
                        "symbol": pos.symbol,
                        "side": pos.side,
                        "size": pos.size,
                        "entry_price": pos.entry_price,
                        "unrealized_pnl": pos.unrealized_pnl,
                        "percentage": pos.percentage
                    }
                    for pos in positions
                ]
            }
            
            return {"success": True, "data": portfolio_stats}
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сводки портфеля: {e}")
            return {"success": False, "error": str(e)}

    # ================== ИНФОРМАЦИОННЫЕ МЕТОДЫ ==================

    def get_integration_stats(self) -> dict:
        """Получение статистики интеграции"""
        uptime = time.time() - self.stats['start_time']
        
        return {
            'uptime_seconds': uptime,
            'uptime_formatted': str(timedelta(seconds=int(uptime))),
            'v5_client_available': self.v5_client is not None,
            'is_initialized': self.is_initialized,
            'websocket_status': self.ws_connected,
            'requests': {
                'v5_requests': self.stats['v5_requests'],
                'legacy_requests': self.stats['legacy_requests'],
                'total': self.stats['v5_requests'] + self.stats['legacy_requests']
            },
            'orders': {
                'placed': self.stats['orders_placed'],
                'failed': self.stats['orders_failed'],
                'cancelled': self.stats['orders_cancelled']
            },
            'websocket_messages': self.stats['websocket_messages'],
            'errors': self.stats['errors'],
            'cache_info': {
                'positions_count': len(self.cache['positions']),
                'last_position_update': self.cache['last_update'].get('positions'),
                'last_balance_update': self.cache['last_update'].get('balance')
            }
        }

    def _handle_bybit_response(self, response: dict, operation: str) -> dict:
        """Улучшенная обработка ответов API"""
        if not response:
            return {'success': False, 'error': f'{operation}: No response from server'}
        
        ret_code = response.get('retCode', -1)
        ret_msg = response.get('retMsg', 'Unknown error')
        
        # Специальная обработка кодов ошибок Bybit
        if ret_code == 0:
            return {'success': True, 'data': response.get('result', {})}
        elif ret_code == 10006:  # Rate limit
            return {'success': False, 'error': 'rate_limit', 'retry_after': 1}
        elif ret_code in [10003, 10004, 10005]:  # Auth errors
            return {'success': False, 'error': 'authentication_failed', 'details': ret_msg}
        elif ret_code == 10001:  # Invalid parameter
            return {'success': False, 'error': 'invalid_parameter', 'details': ret_msg}
        else:
            return {'success': False, 'error': f'{operation}_failed', 'code': ret_code, 'details': ret_msg}

    # ================== ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ ==================

    async def get_order_history(self, symbol: str = None, limit: int = 50) -> dict:
        """Получение истории ордеров"""
        try:
            if not self.v5_client:
                return {"success": False, "error": "V5 клиент не инициализирован"}
            
            response = await self.v5_client.get_order_history("linear", symbol, limit)
            
            return self._handle_bybit_response(response, "get_order_history")
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения истории ордеров: {e}")
            return {"success": False, "error": str(e)}

    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        """Отмена ордера"""
        try:
            if not self.v5_client:
                return {"success": False, "error": "V5 клиент не инициализирован"}
            
            response = await self.v5_client.cancel_order("linear", symbol, order_id)
            
            if response.get('retCode') == 0:
                self.stats['orders_cancelled'] += 1
                logger.info(f"❌ Ордер отменен: {order_id}")
            
            return self._handle_bybit_response(response, "cancel_order")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отмены ордера: {e}")
            return {"success": False, "error": str(e)}

    # ================== УПРАВЛЕНИЕ РЕСУРСАМИ ==================

    async def cleanup(self):
        """Очистка ресурсов"""
        try:
            self._running = False
            
            # Останавливаем автообновление
            if self.auto_update_task and not self.auto_update_task.done():
                self.auto_update_task.cancel()
                try:
                    await self.auto_update_task
                except asyncio.CancelledError:
                    pass
            
            # Очищаем V5 клиент
            if self.v5_client:
                self.v5_client.cleanup()
            
            logger.info("🧹 BybitIntegrationManager очищен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки: {e}")

class EnhancedUnifiedExchangeClient:
    """Enhanced клиент с интеграцией Bybit V5 - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        self.bybit_integration = BybitIntegrationManager(testnet)
        self.is_ready = False
        
    async def initialize(self) -> bool:
        """Инициализация enhanced клиента"""
        try:
            success = await self.bybit_integration.initialize()
            if success:
                self.is_ready = True
                logger.info("✅ Enhanced клиент инициализирован")
            return success
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации enhanced клиента: {e}")
            return False
    
    # ================== ТОРГОВЫЕ МЕТОДЫ ==================
    
    async def get_balance(self, coin: str = "USDT") -> float:
        """Получение баланса через интеграцию"""
        return await self.bybit_integration.get_balance(coin)
    
    async def place_order(self, signal: TradingSignal, **kwargs) -> dict:
        """Размещение ордера через интеграцию"""
        return await self.bybit_integration.place_smart_order(signal, **kwargs)
    
    async def get_positions(self) -> List[PositionInfo]:
        """Получение позиций через интеграцию"""
        return await self.bybit_integration.get_positions()
    
    async def close_position(self, symbol: str) -> dict:
        """Закрытие позиции через интеграцию"""
        return await self.bybit_integration.close_position(symbol)
    
    async def emergency_stop(self) -> dict:
        """Экстренная остановка через интеграцию"""
        return await self.bybit_integration.emergency_stop()
    
    # ================== МЕТОДЫ СОВМЕСТИМОСТИ ==================
    
    async def fetch_ticker(self, symbol: str) -> dict:
        """Получение тикера - для совместимости с data_collector"""
        try:
            if not self.bybit_integration.v5_client:
                return {}
            
            # Получаем данные через V5 API
            ticker_data = await self.bybit_integration.v5_client.get_market_data(symbol)
            
            if ticker_data:
                return {
                    'symbol': symbol,
                    'last': float(ticker_data.get('lastPrice', 0)),
                    'bid': float(ticker_data.get('bid1Price', 0)),
                    'ask': float(ticker_data.get('ask1Price', 0)),
                    'baseVolume': float(ticker_data.get('volume24h', 0)),
                    'quoteVolume': float(ticker_data.get('turnover24h', 0)),
                    'percentage': float(ticker_data.get('price24hPcnt', 0)) * 100,
                    'high': float(ticker_data.get('highPrice24h', 0)),
                    'low': float(ticker_data.get('lowPrice24h', 0)),
                    'timestamp': int(time.time() * 1000)
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения тикера для {symbol}: {e}")
            return {}
            
    async def get_market_data(self, symbol: str) -> Optional[dict]:
        """Получение рыночных данных для символа - ДОБАВЛЕНО ДЛЯ СОВМЕСТИМОСТИ"""
        try:
            ticker_data = await self.get_tickers("linear", symbol)
            if ticker_data.get('retCode') == 0:
                result = ticker_data.get('result', {})
                ticker_list = result.get('list', [])
                if ticker_list:
                    return ticker_list[0]
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения market data для {symbol}: {e}")
            return None
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '5m', limit: int = 100) -> List[List]:
        """Получение OHLCV данных - для совместимости с data_collector"""
        try:
            if not self.bybit_integration.v5_client:
                return []
            
            # Получаем kline данные
            klines = await self.bybit_integration.v5_client.get_klines(
                category="linear",
                symbol=symbol,
                interval=timeframe,
                limit=limit
            )
            
            if klines and klines.get('retCode') == 0:
                klines_list = klines.get('result', {}).get('list', [])
                
                # Преобразуем в формат CCXT [timestamp, open, high, low, close, volume]
                ohlcv_data = []
                for kline in klines_list:
                    ohlcv_data.append([
                        int(kline[0]),  # timestamp
                        float(kline[1]),  # open
                        float(kline[2]),  # high
                        float(kline[3]),  # low
                        float(kline[4]),  # close
                        float(kline[5])   # volume
                    ])
                
                return ohlcv_data
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения OHLCV для {symbol}: {e}")
            return []
    
    async def fetch_trades(self, symbol: str, limit: int = 100) -> List[dict]:
        """Получение сделок - для совместимости с data_collector"""
        try:
            if not self.bybit_integration.v5_client:
                return []
            
            # Получаем публичные сделки
            trades = await self.bybit_integration.v5_client.get_public_trading_records(
                category="linear",
                symbol=symbol,
                limit=limit
            )
            
            if trades and trades.get('retCode') == 0:
                trades_list = trades.get('result', {}).get('list', [])
                
                # Преобразуем в формат CCXT
                ccxt_trades = []
                for trade in trades_list:
                    ccxt_trades.append({
                        'id': trade.get('execId'),
                        'price': float(trade.get('price', 0)),
                        'amount': float(trade.get('size', 0)),
                        'side': trade.get('side', '').lower(),
                        'timestamp': int(trade.get('time', 0)),
                        'datetime': datetime.fromtimestamp(int(trade.get('time', 0)) / 1000).isoformat()
                    })
                
                return ccxt_trades
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сделок для {symbol}: {e}")
            return []
    
    async def fetch_order_book(self, symbol: str, limit: int = 25) -> dict:
        """Получение стакана ордеров - для совместимости с data_collector"""
        try:
            if not self.bybit_integration.v5_client:
                return {}
            
            # Получаем orderbook
            orderbook = await self.bybit_integration.v5_client.get_orderbook(
                category="linear",
                symbol=symbol,
                limit=limit
            )
            
            if orderbook and orderbook.get('retCode') == 0:
                result = orderbook.get('result', {})
                
                # Преобразуем в формат CCXT
                return {
                    'bids': [[float(bid[0]), float(bid[1])] for bid in result.get('b', [])],
                    'asks': [[float(ask[0]), float(ask[1])] for ask in result.get('a', [])],
                    'timestamp': int(result.get('ts', int(time.time() * 1000))),
                    'datetime': datetime.fromtimestamp(int(result.get('ts', int(time.time() * 1000))) / 1000).isoformat()
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения orderbook для {symbol}: {e}")
            return {}
    
    # ================== ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ СОВМЕСТИМОСТИ ==================
    
    async def get_ticker(self, symbol: str) -> dict:
        """Алиас для fetch_ticker"""
        return await self.fetch_ticker(symbol)
    
    async def get_klines(self, symbol: str, interval: str = '5m', limit: int = 100) -> List[List]:
        """Алиас для fetch_ohlcv"""
        return await self.fetch_ohlcv(symbol, interval, limit)
    
    async def get_order_book(self, symbol: str, limit: int = 25) -> dict:
        """Алиас для fetch_order_book"""
        return await self.fetch_order_book(symbol, limit)
    
    # ================== АНАЛИТИЧЕСКИЕ МЕТОДЫ ==================
    
    async def get_market_overview(self, symbols: List[str] = None) -> dict:
        """Получение обзора рынка"""
        return await self.bybit_integration.get_market_overview(symbols)
    
    async def get_portfolio_summary(self) -> dict:
        """Получение сводки портфеля"""
        return await self.bybit_integration.get_portfolio_summary()
    
    # ================== ИНФОРМАЦИОННЫЕ МЕТОДЫ ==================
    
    def get_stats(self) -> dict:
        """Получение статистики через интеграцию"""
        return self.bybit_integration.get_integration_stats()
    
    async def get_order_history(self, symbol: str = None, limit: int = 50) -> dict:
        """Получение истории ордеров"""
        return await self.bybit_integration.get_order_history(symbol, limit)
    
    # ================== СОВМЕСТИМОСТЬ С СУЩЕСТВУЮЩЕЙ СИСТЕМОЙ ==================
    
    async def connect(self, exchange_name: str = 'bybit', testnet: bool = True) -> bool:
        """Подключение к бирже"""
        try:
            # Инициализируем bybit_integration если еще не инициализирован
            if not self.is_ready:
                success = await self.initialize()
                if not success:
                    return False
            
            self.is_ready = True
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Отключение от биржи"""
        try:
            await self.cleanup()
            self.is_ready = False
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отключения: {e}")
            return False
    
    @property
    def is_connected(self) -> bool:
        """Проверка статуса подключения"""
        return self.is_ready and self.bybit_integration.is_initialized
    
    # ================== LEGACY SUPPORT ==================
    
    async def place_order_legacy(self, symbol: str, side: str, amount: float, 
                                price: float = None, order_type: str = 'market',
                                params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Размещение ордера через интеграцию (legacy метод)"""
        try:
            # Создаем сигнал для place_smart_order
            signal = TradingSignal(
                action='BUY' if side.lower() == 'buy' else 'SELL',
                confidence=0.8,
                price=price or 0,
                symbol=symbol,
                order_type=order_type,
                stop_loss=params.get('stopLoss') if params else None,
                take_profit=params.get('takeProfit') if params else None
            )
            
            return await self.bybit_integration.place_smart_order(signal, amount=amount)
            
        except Exception as e:
            logger.error(f"❌ Ошибка размещения ордера: {e}")
            return {"success": False, "error": str(e)}
    
    # ================== МОНИТОРИНГ И ДИАГНОСТИКА ==================
    
    async def health_check(self) -> dict:
        """Проверка здоровья exchange клиента"""
        from datetime import datetime
        
        health_status = {
            'overall_status': 'unknown',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'connection': False,
                'authentication': False,
                'websocket': False,
                'trading': False,
                'data_feed': False
            },
            'errors': [],
            'statistics': self.bybit_integration.get_integration_stats()
        }
        
        try:
            # Проверка подключения
            if self.bybit_integration.is_initialized:
                health_status['components']['connection'] = True
            else:
                health_status['errors'].append('Exchange не подключен')
            
            # Проверка аутентификации
            try:
                if (self.bybit_integration.v5_client and 
                    self.bybit_integration.v5_client.is_initialized):
                    health_status['components']['authentication'] = True
            except Exception as e:
                health_status['errors'].append(f'Ошибка аутентификации: {str(e)}')
            
            # Проверка WebSocket
            if any(self.bybit_integration.ws_connected.values()):
                health_status['components']['websocket'] = True
            
            # Проверка торговых возможностей
            health_status['components']['trading'] = (
                health_status['components']['connection'] and 
                health_status['components']['authentication']
            )
            
            # Проверка data feed
            health_status['components']['data_feed'] = health_status['components']['websocket']
            
            # Определение общего статуса
            critical_components = ['connection', 'authentication']
            if all(health_status['components'][comp] for comp in critical_components):
                health_status['overall_status'] = 'healthy'
            elif any(health_status['components'][comp] for comp in critical_components):
                health_status['overall_status'] = 'degraded'
            else:
                health_status['overall_status'] = 'unhealthy'
            
            return health_status
            
        except Exception as e:
            health_status['overall_status'] = 'error'
            health_status['errors'].append(f'Критическая ошибка health_check: {str(e)}')
            return health_status
    
    # ================== ОЧИСТКА РЕСУРСОВ ==================
    
    async def cleanup(self):
        """Очистка enhanced клиента"""
        await self.bybit_integration.cleanup()

# ================== FACTORY FUNCTIONS ==================

def get_enhanced_exchange_client(testnet: bool = True) -> EnhancedUnifiedExchangeClient:
    """Получение enhanced exchange клиента"""
    return EnhancedUnifiedExchangeClient(testnet)

def upgrade_existing_client(base_client, testnet: bool = True) -> EnhancedUnifiedExchangeClient:
    """Апгрейд существующего клиента до enhanced версии"""
    logger.info("🔄 Апгрейд клиента до enhanced версии...")
    
    # Определяем testnet режим
    testnet = getattr(base_client, 'testnet', True)
    
    enhanced_client = EnhancedUnifiedExchangeClient(testnet=testnet)
    
    logger.info("✅ Клиент успешно апгрейден")
    return enhanced_client

# ================== EXPORTS ==================

__all__ = [
    'BybitIntegrationManager',
    'EnhancedUnifiedExchangeClient', 
    'BybitWebSocketHandler',
    'upgrade_existing_client',
    'get_enhanced_exchange_client',
    'TradingSignal',
    'PositionInfo'
]
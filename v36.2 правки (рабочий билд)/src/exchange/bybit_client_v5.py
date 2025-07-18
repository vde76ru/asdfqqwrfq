#!/usr/bin/env python3
"""
ИСПРАВЛЕННАЯ ИНТЕГРАЦИЯ BYBIT API v5 - PRODUCTION READY
==================================================
Файл: src/exchange/bybit_client_v5.py

✅ ПОЛНАЯ ВЕРСИЯ СО ВСЕМИ МЕТОДАМИ
✅ ИСПРАВЛЕНЫ ВСЕ ПРОБЛЕМЫ С WEBSOCKET:
✅ Устранено дублирование подключений
✅ Правильное управление heartbeat
✅ Корректная проверка существующих соединений
✅ Соблюдение лимитов Bybit API
"""

import ccxt
import time
import logging
import os
import asyncio
import hmac
import hashlib
import json
import threading
import websocket
import aiohttp
import random
from typing import Optional, Dict, Any, List, Callable, Union
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Безопасные импорты
try:
    from ..core.unified_config import unified_config
    UNIFIED_CONFIG_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ unified_config недоступен, используем переменные окружения")
    unified_config = None
    UNIFIED_CONFIG_AVAILABLE = False

@dataclass
class BybitCredentials:
    """Учетные данные Bybit"""
    api_key: str
    api_secret: str
    testnet: bool = True
    recv_window: int = 5000

@dataclass
class BybitEndpoints:
    """Эндпоинты Bybit API"""
    rest_base: str
    ws_public: str
    ws_private: str

class BybitAPIError(Exception):
    """Исключение для ошибок API Bybit"""
    def __init__(self, message: str, error_code: int = None, response: dict = None):
        self.message = message
        self.error_code = error_code
        self.response = response
        super().__init__(self.message)

class BybitWebSocketManager:
    """Менеджер WebSocket соединений - ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    def __init__(self, credentials: BybitCredentials, endpoints: BybitEndpoints):
        self.credentials = credentials
        self.endpoints = endpoints
        self.connections = {}
        self.callbacks = {}
        self.reconnect_attempts = {}
        self.max_reconnect_attempts = 10
        self.ping_interval = 20
        self.is_initialized = True
        
        # Флаги состояния WebSocket
        self.ws_connected = {'public': False, 'private': False}
        self.last_message_time = {'public': time.time(), 'private': time.time()}
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Глобальный контроль heartbeat
        self._heartbeat_started = False
        self._heartbeat_task = None
        self._heartbeat_lock = threading.Lock()
        
        # Флаги для предотвращения дублирования подключений
        self._connection_locks = {'public': threading.Lock(), 'private': threading.Lock()}
        self._connecting = {'public': False, 'private': False}
        
        logger.info("✅ BybitWebSocketManager инициализирован")

    def connect_private(self, callback: Callable):
        """Подключение к приватному каналу - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        with self._connection_locks['private']:
            # КРИТИЧЕСКАЯ ПРОВЕРКА: предотвращение дублирования
            if self._connecting['private']:
                logger.warning("⚠️ Приватный WebSocket уже подключается, ожидаем...")
                return self.connections.get('private')
            
            if 'private' in self.connections and self.connections['private'] and self.ws_connected.get('private'):
                logger.info("ℹ️ Приватный WebSocket уже подключен и активен")
                return self.connections['private']
            
            self._connecting['private'] = True
            
        try:
            logger.info("🔐 Инициализация приватного WebSocket...")
            
            # Генерируем подпись для аутентификации
            expires = str(int(time.time() * 1000) + 10000)
            signature = self._generate_signature(expires)
            
            auth_msg = {
                "op": "auth",
                "args": [{
                    "apiKey": self.credentials.api_key,
                    "expires": expires,
                    "signature": signature
                }]
            }
            
            # Сохраняем ссылку на менеджер для доступа из вложенных функций
            manager = self
            
            def on_message(ws, message):
                try:
                    # ВАЖНО: Обновляем время последнего сообщения
                    manager.last_message_time['private'] = time.time()
                    
                    data = json.loads(message)
                    
                    # Обработка ping от Bybit
                    if data.get('op') == 'ping':
                        pong_msg = {'op': 'pong', 'args': [str(int(time.time() * 1000))]}
                        ws.send(json.dumps(pong_msg))
                        return
                    
                    # Обработка успешной аутентификации
                    if data.get('success'):
                        logger.info("✅ WebSocket аутентификация успешна")
                        manager.ws_connected['private'] = True
                        # Подписываемся на каналы после успешной аутентификации
                        subscribe_msg = {
                            "op": "subscribe",
                            "args": ["position", "order", "wallet"]
                        }
                        ws.send(json.dumps(subscribe_msg))
                        logger.info("📡 Подписка на position, order, wallet")
                    
                    # Передаем сообщение в callback
                    if callback:
                        callback(data)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки WS сообщения: {e}")
            
            def on_error(ws, error):
                logger.error(f"❌ Private WebSocket ошибка: {error}")
                manager.ws_connected['private'] = False
                manager._connecting['private'] = False
                manager._schedule_reconnect('private')
            
            def on_close(ws, close_status_code, close_msg):
                logger.warning(f"⚠️ Private WebSocket закрыт: {close_msg}")
                manager.ws_connected['private'] = False
                manager._connecting['private'] = False
            
            def on_open(ws):
                logger.info("🔐 WebSocket соединение открыто")
                manager.last_message_time['private'] = time.time()
                # Отправляем аутентификацию
                ws.send(json.dumps(auth_msg))
            
            ws = websocket.WebSocketApp(
                self.endpoints.ws_private,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            self.connections['private'] = ws
            self.callbacks['private'] = callback
            
            # Запуск в отдельном потоке
            def run_ws():
                try:
                    ws.run_forever(ping_interval=self.ping_interval)
                finally:
                    manager._connecting['private'] = False
            
            thread = threading.Thread(target=run_ws, daemon=True)
            thread.start()
            
            # Запуск heartbeat (ТОЛЬКО ОДИН РАЗ)
            self._ensure_heartbeat_started()
            
            # Сбрасываем флаг подключения после успешного старта
            self._connecting['private'] = False
            
            return ws
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания приватного WebSocket: {e}")
            self._connecting['private'] = False
            return None
    
    def connect_public(self, callback: Callable):
        """Подключение к публичному каналу - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        with self._connection_locks['public']:
            # КРИТИЧЕСКАЯ ПРОВЕРКА: предотвращение дублирования
            if self._connecting['public']:
                logger.warning("⚠️ Публичный WebSocket уже подключается, ожидаем...")
                return self.connections.get('public')
            
            if 'public' in self.connections and self.connections['public'] and self.ws_connected.get('public'):
                logger.info("ℹ️ Публичный WebSocket уже подключен и активен")
                return self.connections['public']
            
            self._connecting['public'] = True
            
        try:
            logger.info("📡 Инициализация публичного WebSocket...")
            
            # Сохраняем ссылку на менеджер для доступа из вложенных функций
            manager = self
            
            def on_message(ws, message):
                try:
                    # ВАЖНО: Обновляем время последнего сообщения
                    manager.last_message_time['public'] = time.time()
                    
                    data = json.loads(message)
                    
                    # Обработка ping от Bybit
                    if data.get('op') == 'ping':
                        pong_msg = {'op': 'pong', 'args': [str(int(time.time() * 1000))]}
                        ws.send(json.dumps(pong_msg))
                        return
                    
                    # Передаем сообщение в callback
                    if callback:
                        callback(data)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки публичного WS сообщения: {e}")
            
            def on_error(ws, error):
                logger.error(f"❌ Public WebSocket ошибка: {error}")
                manager.ws_connected['public'] = False
                manager._connecting['public'] = False
                manager._schedule_reconnect('public')
            
            def on_close(ws, close_status_code, close_msg):
                logger.warning(f"⚠️ Public WebSocket закрыт: {close_msg}")
                manager.ws_connected['public'] = False
                manager._connecting['public'] = False
            
            def on_open(ws):
                logger.info("📡 Публичное WebSocket соединение открыто")
                manager.ws_connected['public'] = True
                manager.last_message_time['public'] = time.time()
            
            ws = websocket.WebSocketApp(
                self.endpoints.ws_public + "/linear",
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            self.connections['public'] = ws
            self.callbacks['public'] = callback
            
            # Запуск в отдельном потоке
            def run_ws():
                try:
                    ws.run_forever(ping_interval=self.ping_interval)
                finally:
                    manager._connecting['public'] = False
            
            thread = threading.Thread(target=run_ws, daemon=True)
            thread.start()
            
            # Запуск heartbeat (ТОЛЬКО ОДИН РАЗ)
            self._ensure_heartbeat_started()
            
            # Сбрасываем флаг подключения после успешного старта
            self._connecting['public'] = False
            
            return ws
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания публичного WebSocket: {e}")
            self._connecting['public'] = False
            return None

    def _ensure_heartbeat_started(self):
        """Обеспечение запуска heartbeat только один раз - ОКОНЧАТЕЛЬНОЕ ИСПРАВЛЕНИЕ"""
        with self._heartbeat_lock:
            # Проверяем, что heartbeat еще не запущен
            if self._heartbeat_started:
                logger.debug("💓 Heartbeat уже запущен, пропускаем")
                return
            
            # Проверяем, что нет активного task
            if self._heartbeat_task and not self._heartbeat_task.done():
                logger.debug("💓 Heartbeat task уже выполняется, пропускаем")
                return
            
            try:
                # Устанавливаем флаг ДО создания task
                self._heartbeat_started = True
                
                # Создаем новый event loop для heartbeat если его нет
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        raise RuntimeError("Loop is closed")
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                self._heartbeat_task = asyncio.create_task(self._websocket_heartbeat())
                logger.info("💓 WebSocket heartbeat запущен")
                
            except Exception as e:
                # Сбрасываем флаг в случае ошибки
                self._heartbeat_started = False
                logger.error(f"❌ Ошибка запуска heartbeat: {e}")

    def subscribe(self, channel: str, topics: List[str], ws_type: str = 'public'):
        """Подписка на каналы"""
        if ws_type not in self.connections or not self.ws_connected.get(ws_type):
            logger.error(f"❌ WebSocket {ws_type} не подключен")
            return False
        
        ws = self.connections[ws_type]
        
        try:
            for topic in topics:
                subscribe_msg = {
                    "op": "subscribe",
                    "args": [f"{channel}.{topic}"] if topic else [channel]
                }
                ws.send(json.dumps(subscribe_msg))
                logger.info(f"📡 Подписка на {channel}.{topic if topic else ''}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подписки: {e}")
            return False
    
    def _schedule_reconnect(self, ws_type: str):
        """Планирование переподключения с учетом rate limiting"""
        attempts = self.reconnect_attempts.get(ws_type, 0)
        
        if attempts >= self.max_reconnect_attempts:
            logger.error(f"❌ Достигнут лимит попыток переподключения для {ws_type}")
            return
            
        self.reconnect_attempts[ws_type] = attempts + 1
        
        # Экспоненциальная задержка с учетом rate limiting Bybit
        base_delay = 5
        max_delay = 300
        delay = min(max_delay, base_delay * (2 ** attempts))
        
        # Добавляем случайный джиттер
        jitter = random.uniform(0, delay * 0.1)
        total_delay = delay + jitter
        
        logger.info(f"🔄 Переподключение {ws_type} через {total_delay:.1f}s (попытка {attempts + 1}/{self.max_reconnect_attempts})")
        
        def delayed_reconnect():
            try:
                self._reconnect(ws_type)
            except Exception as e:
                logger.error(f"❌ Ошибка в delayed_reconnect: {e}")
        
        timer = threading.Timer(total_delay, delayed_reconnect)
        timer.daemon = True
        timer.start()
    
    def _reconnect(self, ws_type: str):
        """Переподключение WebSocket"""
        try:
            logger.info(f"🔄 Переподключение {ws_type}...")
            
            # Закрываем старое соединение
            if ws_type in self.connections and self.connections[ws_type]:
                try:
                    self.connections[ws_type].close()
                except:
                    pass
                del self.connections[ws_type]
            
            self.ws_connected[ws_type] = False
            
            # Создаем новое соединение
            callback = self.callbacks.get(ws_type)
            if callback:
                if ws_type == 'private':
                    self.connect_private(callback)
                elif ws_type == 'public':
                    self.connect_public(callback)
            
        except Exception as e:
            logger.error(f"❌ Ошибка переподключения {ws_type}: {e}")

    async def _websocket_heartbeat(self):
        """Улучшенный heartbeat для WebSocket соединений"""
        logger.info("💓 WebSocket heartbeat запущен")
        
        try:
            while self._heartbeat_started:
                await asyncio.sleep(self.ping_interval)
                
                current_time = time.time()
                
                for ws_type, ws in self.connections.items():
                    if ws and self.ws_connected.get(ws_type):
                        try:
                            # Проверяем время последнего сообщения
                            last_msg_time = self.last_message_time.get(ws_type, 0)
                            time_since_last_msg = current_time - last_msg_time
                            
                            # Если нет сообщений больше 60 секунд - переподключаемся
                            if time_since_last_msg > 60:
                                logger.warning(f"⚠️ Нет сообщений от {ws_type} WebSocket более 60 секунд")
                                self._schedule_reconnect(ws_type)
                                continue
                            
                            # Отправляем ping
                            ping_msg = {"op": "ping"}
                            ws.send(json.dumps(ping_msg))
                            logger.debug(f"📡 Ping отправлен на {ws_type}")
                            
                        except Exception as e:
                            logger.error(f"❌ Ошибка heartbeat для {ws_type}: {e}")
                            self._schedule_reconnect(ws_type)
                            
        except asyncio.CancelledError:
            logger.info("💔 WebSocket heartbeat остановлен")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в heartbeat: {e}")
        finally:
            self._heartbeat_started = False

    def disconnect(self):
        """Отключение WebSocket соединений"""
        try:
            # Остановка heartbeat
            with self._heartbeat_lock:
                self._heartbeat_started = False
                if self._heartbeat_task and not self._heartbeat_task.done():
                    self._heartbeat_task.cancel()
                    logger.info("💔 WebSocket heartbeat остановлен")
            
            # Закрытие соединений
            for ws_type, ws in self.connections.items():
                if ws:
                    try:
                        ws.close()
                    except:
                        pass
                self.ws_connected[ws_type] = False
                self._connecting[ws_type] = False
                
            self.connections.clear()
            logger.info("🔌 WebSocket соединения закрыты")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отключения WebSocket: {e}")
    
    def _generate_signature(self, expires: str) -> str:
        """Генерация подписи для аутентификации"""
        val = f"GET/realtime{expires}"
        signature = hmac.new(
            bytes(self.credentials.api_secret, "utf-8"),
            bytes(val, "utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

class BybitClientV5:
    """Production-ready клиент для Bybit API v5 - ПОЛНАЯ ВЕРСИЯ"""
    
    def __init__(self, api_key: str, secret: str, testnet: bool = True):
        self.credentials = BybitCredentials(api_key, secret, testnet)
        self.testnet = testnet
        self.exchange = None
        self.is_initialized = False
        
        # Статистика
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.last_request_time = None
        
        # Кэширование
        self.cache = {
            'balance': {},
            'positions': {},
            'orders': {},
            'tickers': {},
            'last_update': {}
        }
        
        # Настройка эндпоинтов
        if testnet:
            self.endpoints = BybitEndpoints(
                rest_base="https://api-testnet.bybit.com",
                ws_public="wss://stream-testnet.bybit.com/v5/public",
                ws_private="wss://stream-testnet.bybit.com/v5/private"
            )
        else:
            self.endpoints = BybitEndpoints(
                rest_base="https://api.bybit.com",
                ws_public="wss://stream.bybit.com/v5/public",
                ws_private="wss://stream.bybit.com/v5/private"
            )
        
        # Инициализируем WebSocket менеджер
        self.ws_manager = BybitWebSocketManager(self.credentials, self.endpoints)
        
        logger.info("🎯 BybitClientV5 инициализирован")

    async def initialize(self) -> bool:
        """Инициализация клиента"""
        try:
            # Настройка CCXT exchange
            self.exchange = ccxt.bybit({
                'apiKey': self.credentials.api_key,
                'secret': self.credentials.api_secret,
                'sandbox': self.testnet,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'linear',
                    'recvWindow': self.credentials.recv_window,
                }
            })
            
            logger.info("✅ CCXT exchange настроен")
            
            # Проверяем подключение
            try:
                server_time = await self._get_server_time()
                if server_time:
                    logger.info("✅ Подключение к API работает")
                    self.is_initialized = True
                    return True
                else:
                    logger.error("❌ Не удалось получить время сервера")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки подключения: {e}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            return False

    # ================== HTTP API METHODS ==================

    async def _make_request(self, method: str, endpoint: str, params: dict = None) -> dict:
        """Универсальный метод для HTTP запросов к API"""
        try:
            timestamp = str(int(time.time() * 1000))
            url = f"{self.endpoints.rest_base}{endpoint}"
            
            async with aiohttp.ClientSession() as session:
                if method == 'GET':
                    # Для GET запросов параметры в query string
                    query_string = ""
                    if params:
                        sorted_params = sorted(params.items())
                        query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
                    
                    signature = self._generate_signature(timestamp, method, endpoint, query_string)
                    url += f"?{query_string}"
                    
                    headers = self._get_headers(timestamp, signature)
                    
                    async with session.get(url, headers=headers) as response:
                        result = await response.json()
                        self._update_stats(result)
                        return result
                        
                else:  # POST, PUT, DELETE
                    # Для POST запросов параметры в JSON body
                    json_body = json.dumps(params or {})
                    signature = self._generate_signature(timestamp, method, endpoint, json_body)
                    
                    headers = self._get_headers(timestamp, signature)
                    
                    async with session.request(method, url, headers=headers, data=json_body) as response:
                        result = await response.json()
                        self._update_stats(result)
                        return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка API запроса {method} {endpoint}: {e}")
            self.error_count += 1
            return {
                'retCode': -1,
                'retMsg': str(e),
                'result': None
            }

    def _generate_signature(self, timestamp: str, method: str, endpoint: str, params: str) -> str:
        """Генерация подписи для HTTP запросов"""
        param_str = f"{timestamp}{self.credentials.api_key}{self.credentials.recv_window}{params}"
        signature = hmac.new(
            bytes(self.credentials.api_secret, "utf-8"),
            bytes(param_str, "utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _get_headers(self, timestamp: str, signature: str) -> dict:
        """Получение заголовков для HTTP запросов"""
        return {
            'X-BAPI-API-KEY': self.credentials.api_key,
            'X-BAPI-TIMESTAMP': timestamp,
            'X-BAPI-SIGN': signature,
            'X-BAPI-RECV-WINDOW': str(self.credentials.recv_window),
            'Content-Type': 'application/json'
        }

    def _update_stats(self, response: dict):
        """Обновление статистики запросов"""
        self.request_count += 1
        self.last_request_time = datetime.now()
        
        if response.get('retCode') == 0:
            self.success_count += 1
        else:
            self.error_count += 1

    async def _get_server_time(self) -> Optional[int]:
        """Получение времени сервера"""
        try:
            response = await self._make_request('GET', '/v5/market/time')
            if response.get('retCode') == 0:
                return int(response['result']['timeSecond'])
            return None
        except Exception:
            return None

    # ================== WALLET & ACCOUNT METHODS ==================

    async def get_wallet_balance(self, account_type: str = "UNIFIED", coin: str = None) -> dict:
        """Получение баланса кошелька"""
        params = {"accountType": account_type}
        if coin:
            params["coin"] = coin
        
        response = await self._make_request('GET', '/v5/account/wallet-balance', params)
        
        if response.get('retCode') == 0:
            self.cache['balance'] = response['result']
            logger.info(f"💰 Баланс обновлен: {account_type}")
        
        return response

    async def get_positions(self, category: str = "linear", symbol: str = None, settleCoin: str = None) -> dict:
        """Получение позиций - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            if not self.is_initialized:
                await self.initialize()
            
            # ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Bybit API v5 требует обязательный параметр
            params = {"category": category}
            
            if symbol:
                params["symbol"] = symbol
            elif settleCoin:
                params["settleCoin"] = settleCoin
            else:
                # ОБЯЗАТЕЛЬНО: Для получения всех позиций нужен settleCoin
                params["settleCoin"] = "USDT"
            
            response = await self._make_request("GET", "/v5/position/list", params)
            
            if response and response.get('retCode') == 0:
                logger.debug(f"📊 Позиции получены для category={category}")
                return {
                    'success': True,
                    'data': response.get('result', {})
                }
            else:
                error_msg = response.get('retMsg', 'Неизвестная ошибка') if response else 'Нет ответа'
                logger.warning(f"⚠️ Ошибка получения позиций: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            logger.error(f"❌ Исключение при получении позиций: {e}")
            return {
                'success': False,
                'error': str(e)
            }
                
        except Exception as e:
            logger.error(f"❌ Исключение при получении позиций: {e}")
            return {
                'success': False,
                'error': str(e)
            }


    async def set_leverage(self, category: str, symbol: str, buy_leverage: str, 
                          sell_leverage: str = None) -> dict:
        """Установка плеча"""
        params = {
            "category": category,
            "symbol": symbol,
            "buyLeverage": buy_leverage,
            "sellLeverage": sell_leverage or buy_leverage
        }
        
        response = await self._make_request('POST', '/v5/position/set-leverage', params)
        
        if response.get('retCode') == 0:
            logger.info(f"🔧 Плечо установлено {symbol}: {buy_leverage}x")
        
        return response

    # ================== ORDER METHODS ==================

    async def place_order(self, category: str, symbol: str, side: str, order_type: str,
                         qty: str, price: str = None, time_in_force: str = "GTC",
                         position_idx: int = 0, reduce_only: bool = False,
                         take_profit: str = None, stop_loss: str = None,
                         tp_sl_mode: str = "Full", **kwargs) -> dict:
        """Размещение ордера"""
        params = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": qty,
            "positionIdx": position_idx
        }
        
        if price:
            params["price"] = price
        if order_type == "Limit":
            params["timeInForce"] = time_in_force
        if reduce_only:
            params["reduceOnly"] = reduce_only
        if take_profit:
            params["takeProfit"] = take_profit
        if stop_loss:
            params["stopLoss"] = stop_loss
        if take_profit or stop_loss:
            params["tpslMode"] = tp_sl_mode
        
        # Добавляем дополнительные параметры
        params.update(kwargs)
        
        response = await self._make_request('POST', '/v5/order/create', params)
        
        if response.get('retCode') == 0:
            order_id = response['result']['orderId']
            logger.info(f"📝 Ордер создан: {symbol} {side} {qty} - ID: {order_id}")
        
        return response

    async def place_market_order(self, symbol: str, side: str, qty: str, 
                                category: str = "linear", **kwargs) -> dict:
        """Размещение market ордера"""
        return await self.place_order(
            category=category,
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            **kwargs
        )

    async def place_limit_order(self, symbol: str, side: str, qty: str, price: str,
                               category: str = "linear", **kwargs) -> dict:
        """Размещение limit ордера"""
        return await self.place_order(
            category=category,
            symbol=symbol,
            side=side,
            order_type="Limit",
            qty=qty,
            price=price,
            **kwargs
        )

    async def cancel_order(self, category: str, symbol: str, order_id: str = None, 
                          order_link_id: str = None) -> dict:
        """Отмена ордера"""
        params = {
            "category": category,
            "symbol": symbol
        }
        
        if order_id:
            params["orderId"] = order_id
        elif order_link_id:
            params["orderLinkId"] = order_link_id
        else:
            raise BybitAPIError("Необходим orderId или orderLinkId")
        
        response = await self._make_request('POST', '/v5/order/cancel', params)
        
        if response.get('retCode') == 0:
            logger.info(f"❌ Ордер отменен: {order_id or order_link_id}")
        
        return response

    async def get_order_history(self, category: str = "linear", symbol: str = None, 
                               limit: int = 50) -> dict:
        """Получение истории ордеров"""
        params = {
            "category": category,
            "limit": limit
        }
        if symbol:
            params["symbol"] = symbol
        
        return await self._make_request('GET', '/v5/order/history', params)

    # ================== MARKET DATA METHODS ==================

    async def get_tickers(self, category: str = "linear", symbol: str = None) -> dict:
        """Получение тикеров"""
        params = {"category": category}
        if symbol:
            params["symbol"] = symbol
        
        response = await self._make_request('GET', '/v5/market/tickers', params)
        
        if response.get('retCode') == 0:
            self.cache['tickers'] = response['result']
            self.cache['last_update']['tickers'] = time.time()
        
        return response

    async def get_market_data(self, symbol: str) -> Optional[dict]:
        """Получение рыночных данных для символа"""
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

    async def get_klines(self, category: str, symbol: str, 
                        interval: str, limit: int = 200) -> dict:
        """Получение исторических данных (свечей)"""
        params = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        return await self._make_request('GET', '/v5/market/kline', params)

    async def get_orderbook(self, category: str, symbol: str, 
                           limit: int = 25) -> dict:
        """Получение стакана ордеров"""
        params = {
            "category": category,
            "symbol": symbol,
            "limit": limit
        }
        response = await self._make_request('GET', '/v5/market/orderbook', params)
        
        if response.get('retCode') == 0:
            result = response.get('result', {})
            return {
                'bids': result.get('b', []),
                'asks': result.get('a', []),
                'symbol': result.get('s', symbol),
                'timestamp': result.get('ts', int(time.time() * 1000))
            }
        return {}

    async def get_public_trading_records(self, category: str, symbol: str, 
                                        limit: int = 100) -> dict:
        """Получение информации о публичных сделках"""
        params = {
            "category": category,
            "symbol": symbol,
            "limit": limit
        }
        return await self._make_request('GET', '/v5/market/recent-trade', params)

    # ================== WEBSOCKET METHODS ==================

    def start_private_websocket(self, callback: Callable):
        """Запуск приватного WebSocket"""
        if not self.ws_manager:
            logger.error("❌ WebSocket менеджер не инициализирован")
            return None
        
        return self.ws_manager.connect_private(callback)

    def start_public_websocket(self, callback: Callable):
        """Запуск публичного WebSocket"""
        if not self.ws_manager:
            logger.error("❌ WebSocket менеджер не инициализирован")
            return None
        
        return self.ws_manager.connect_public(callback)

    def subscribe_positions(self):
        """Подписка на обновления позиций"""
        if not self.ws_manager:
            logger.error("❌ WebSocket менеджер не доступен")
            return False
        return self.ws_manager.subscribe("position", [""], "private")

    def subscribe_orders(self):
        """Подписка на обновления ордеров"""
        if not self.ws_manager:
            logger.error("❌ WebSocket менеджер не доступен")
            return False
        return self.ws_manager.subscribe("order", [""], "private")

    def subscribe_wallet(self):
        """Подписка на обновления кошелька"""
        if not self.ws_manager:
            logger.error("❌ WebSocket менеджер не доступен")
            return False
        return self.ws_manager.subscribe("wallet", [""], "private")

    def subscribe_ticker(self, symbol: str):
        """Подписка на тикер"""
        if not self.ws_manager:
            logger.error("❌ WebSocket менеджер не доступен")
            return False
        return self.ws_manager.subscribe("tickers", [symbol], "public")

    def subscribe_orderbook(self, symbol: str, depth: int = 50):
        """Подписка на стакан ордеров"""
        if not self.ws_manager:
            logger.error("❌ WebSocket менеджер не доступен")
            return False
        return self.ws_manager.subscribe("orderbook", [f"{depth}.{symbol}"], "public")

    # ================== UTILITY METHODS ==================

    async def get_balance(self, coin: str = 'USDT') -> float:
        """Упрощенное получение баланса"""
        try:
            if not self.exchange:
                raise BybitAPIError("Exchange не инициализирован")
            
            balance = await asyncio.to_thread(self.exchange.fetch_balance)
            return float(balance.get(coin, {}).get('free', 0))
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            raise BybitAPIError(f"Ошибка получения баланса: {str(e)}")

    def get_stats(self) -> dict:
        """Получение статистики клиента"""
        return {
            'request_count': self.request_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': (self.success_count / max(self.request_count, 1)) * 100,
            'last_request': self.last_request_time.isoformat() if self.last_request_time else None,
            'cache_size': {
                'balance': len(self.cache.get('balance', {})),
                'positions': len(self.cache.get('positions', {})),
                'tickers': len(self.cache.get('tickers', {}))
            }
        }

    def cleanup(self):
        """Очистка ресурсов"""
        if self.ws_manager:
            self.ws_manager.disconnect()
        logger.info("🧹 BybitClientV5 очищен")

# ================== FACTORY FUNCTIONS ==================

def create_bybit_client_from_env(testnet: bool = True) -> BybitClientV5:
    """Создание клиента из конфигурации - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Получаем конфигурацию
        if UNIFIED_CONFIG_AVAILABLE and unified_config:
            logger.info("📋 API ключи получены из unified_config")
            
            # ИСПРАВЛЕНИЕ: Правильный доступ к атрибутам unified_config
            api_key = getattr(unified_config, 'BYBIT_API_KEY', '')
            api_secret = getattr(unified_config, 'BYBIT_API_SECRET', '')
            testnet = getattr(unified_config, 'BYBIT_TESTNET', True)
            
            # Альтернативный способ - через метод get_bybit_exchange_config (если он есть)
            if not api_key or not api_secret:
                try:
                    bybit_config = unified_config.get_bybit_exchange_config()
                    api_key = bybit_config.get('apiKey', '')
                    api_secret = bybit_config.get('secret', '')
                    testnet = bybit_config.get('sandbox', True)
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось получить конфигурацию через get_bybit_exchange_config: {e}")
                    
        else:
            # Используем переменные окружения
            api_key = os.getenv('BYBIT_API_KEY', '')
            api_secret = os.getenv('BYBIT_API_SECRET', '')
            testnet = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
        
        if not api_key or not api_secret:
            raise ValueError("❌ API ключи не найдены в конфигурации или переменных окружения")
        
        logger.info(f"✅ API ключи настроены для {'testnet' if testnet else 'mainnet'}")
        
        return BybitClientV5(api_key, api_secret, testnet)
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания клиента: {e}")
        raise

# ================== EXPORTS ==================

__all__ = [
    'BybitClientV5',
    'BybitWebSocketManager',
    'BybitCredentials', 
    'BybitEndpoints',
    'BybitAPIError',
    'create_bybit_client_from_env'
]
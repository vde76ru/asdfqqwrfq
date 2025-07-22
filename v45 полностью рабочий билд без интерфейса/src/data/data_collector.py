"""
Реальный сборщик рыночных данных для торгового бота
Файл: src/data/data_collector.py
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from collections import defaultdict
from ..core.models import Candle, Signal, VolumeAnomaly
import traceback

logger = logging.getLogger(__name__)

class DataCollector:
    """Реальный сборщик рыночных данных"""
    
    def __init__(self, exchange_client, db_session=None):
        self.exchange = exchange_client
        self.db = db_session
        self.is_running = False
        self.is_initialized = True
        self.collected_data = defaultdict(dict)
        self.collection_tasks = {}
        self.update_interval = 60  # секунд
        self.active_pairs = []
        
        logger.info("✅ DataCollector инициализирован")
    
    async def start(self):
        """Запуск сборщика данных"""
        self.is_running = True
        logger.info("✅ DataCollector запущен")
        
        # Запускаем фоновые задачи сбора
        asyncio.create_task(self._continuous_collection())
        return True
    
    async def stop(self):
        """Остановка сборщика данных"""
        self.is_running = False
        
        # Отменяем все задачи
        for task in self.collection_tasks.values():
            if not task.done():
                task.cancel()
        
        logger.info("✅ DataCollector остановлен")
        return True
    
    async def collect_historical_data(self, symbol: str, timeframe: str = '1h', limit: int = 300):
        """
        Сбор исторических данных для символа - ИСПРАВЛЕНО
        """
        try:
            logger.info(f"🔄 Диагностика для {symbol}:")
            logger.info(f"   Exchange type: {type(self.exchange).__name__}")
            logger.info(f"   Has get_klines: {hasattr(self.exchange, 'get_klines')}")
            logger.info(f"   Has ccxt_exchange: {hasattr(self.exchange, 'ccxt_exchange')}")
            
            logger.info(f"🔄 Запрос исторических данных для {symbol} ({timeframe}, limit={limit})")
            actual_limit = max(limit, 300)  # Гарантируем минимум 300 свечей
            logger.info(f"📊 Используем лимит: {actual_limit} свечей")
            
            # Условная проверка типа exchange клиента
            if hasattr(self.exchange, 'bybit_integration') and hasattr(self.exchange.bybit_integration, 'v5_client'):
                # Для Enhanced клиента с V5 используем category
                logger.debug(f"🔄 Используем V5 клиент для {symbol}")
                response = await self.exchange.bybit_integration.v5_client.get_klines(
                    category="linear",
                    symbol=symbol,
                    interval=self._convert_timeframe(timeframe),
                    limit=limit
                )
            elif hasattr(self.exchange, 'get_klines'):
                # Для обычного клиента без category
                logger.debug(f"🔄 Используем стандартный клиент для {symbol}")
                response = await self.exchange.get_klines(
                    symbol=symbol,
                    interval=self._convert_timeframe(timeframe),
                    limit=limit
                )
            elif hasattr(self.exchange, 'ccxt_exchange') and self.exchange.ccxt_exchange:
                # Fallback к CCXT
                logger.debug(f"🔄 Используем CCXT для {symbol}")
                ohlcv = await self.exchange.ccxt_exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe, # CCXT понимает '1h', '4h'
                    limit=limit,
                    params={'category': 'linear'}
                )
                # Преобразуем в ожидаемый формат
                response = {'retCode': 0, 'result': {'list': ohlcv}}
            else:
                logger.error(f"❌ Нет подходящего метода для загрузки данных {symbol}")
                return None
            
            # Обработка ответа
            if not response:
                logger.error(f"❌ Пустой ответ для {symbol}")
                return None
                
            # Проверяем успешность ответа
            if isinstance(response, dict):
                if response.get('retCode') == 0:
                    result = response.get('result', {})
                    klines_list = result.get('list', [])
                    
                    if klines_list and len(klines_list) > 0:
                        logger.info(f"✅ Получено {len(klines_list)} свечей для {symbol}")
                        
                        # ✅ ИСПРАВЛЕНО: Сначала сохраняем в БД, потом преобразуем
                        if self.db:
                            await self._save_historical_candles_to_db(symbol, timeframe, klines_list)
                        
                        # Преобразуем в pandas DataFrame
                        df = self._convert_klines_to_dataframe(klines_list, symbol, timeframe)
                        
                        if df is not None and not df.empty:
                            # Сохраняем в кэш
                            self._cache_data(symbol, timeframe, df)
                            
                            logger.info(f"💾 Данные для {symbol} ({timeframe}) обработаны и сохранены")
                            return df
                        else:
                            logger.error(f"❌ Не удалось преобразовать данные для {symbol}")
                            return None
                    else:
                        logger.warning(f"⚠️ Пустой список свечей для {symbol}")
                        return None
                else:
                    ret_msg = response.get('retMsg', 'Unknown error')
                    logger.error(f"❌ Ошибка API для {symbol}: {ret_msg}")
                    return None
            else:
                logger.error(f"❌ Неожиданный формат ответа для {symbol}: {type(response)}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка загрузки данных {symbol}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
            
    def _convert_klines_to_dataframe(self, klines_list: list, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Преобразование списка свечей от API в pandas DataFrame.
        Bybit V5 API (linear) возвращает: [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]
        CCXT возвращает: [timestamp, open, high, low, close, volume]
        """
        if not klines_list:
            return None
        
        # Определяем колонки в зависимости от формата данных
        if len(klines_list[0]) == 7:
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
        else:
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
        try:
            df = pd.DataFrame(klines_list, columns=columns)
            
            # ИСПРАВЛЕНИЕ: Проверяем тип timestamp перед преобразованием
            if df['timestamp'].dtype == 'object':  # Если это строка
                # Проверяем формат строки
                sample_timestamp = str(df['timestamp'].iloc[0])
                
                if '-' in sample_timestamp and ':' in sample_timestamp:
                    # Это дата в формате строки типа '2025-07-21 00:35:00'
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                else:
                    # Пробуем как числовой timestamp
                    df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:
                # Если это числовой timestamp в миллисекундах
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(np.int64), unit='ms')
            
            # Преобразование остальных колонок
            numeric_cols = [col for col in ['open', 'high', 'low', 'close', 'volume', 'turnover'] if col in df.columns]
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna()
            
            # Сортировка по времени
            df = df.sort_values(by='timestamp').reset_index(drop=True)
            df.set_index('timestamp', inplace=True)
            
            logger.debug(f"✅ Данные для {symbol} ({timeframe}) успешно преобразованы в DataFrame. Свечей: {len(df)}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Ошибка преобразования klines в DataFrame для {symbol}: {e}")
            logger.error(f"Тип timestamp: {type(klines_list[0][0]) if klines_list else 'Нет данных'}")
            logger.error(f"Пример timestamp: {klines_list[0][0] if klines_list else 'Нет данных'}")
            return None

    def _cache_data(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """
        ✅ ДОБАВЛЕННЫЙ МЕТОД
        Кэширование данных DataFrame в памяти.
        """
        if self.collected_data[symbol] is None:
            self.collected_data[symbol] = {}
        self.collected_data[symbol][timeframe] = df
        logger.debug(f"💾 Данные для {symbol} ({timeframe}) кэшированы в памяти.")
            
    def _convert_timeframe(self, timeframe: str) -> str:
        """Конвертация timeframe в формат Bybit"""
        # Bybit использует числовой формат для интервалов
        conversion = {
            '1m': '1',
            '5m': '5', 
            '15m': '15',
            '30m': '30',
            '1h': '60',
            '4h': '240',
            '1d': 'D',
            '1w': 'W',
            '1M': 'M'
        }
        return conversion.get(timeframe, timeframe)
    
    async def _save_historical_candles_to_db(self, symbol: str, timeframe: str, candles: list):
        """Сохранение свечей в БД согласно структуре таблицы candles"""
        if not self.db or not candles:
            return
            
        try:
            if callable(self.db):
                db_session = self.db()
            else:
                db_session = self.db
                
            
            saved_count = 0
            candles_to_save = []
            
            for candle_data in candles:
                try:
                    timestamp_ms = int(candle_data[0])
                    open_time = datetime.fromtimestamp(timestamp_ms / 1000)
                    
                    # Рассчитываем close_time
                    timeframe_deltas = {
                        '1m': timedelta(minutes=1),
                        '5m': timedelta(minutes=5),
                        '15m': timedelta(minutes=15),
                        '30m': timedelta(minutes=30),
                        '1h': timedelta(hours=1),
                        '4h': timedelta(hours=4),
                        '1d': timedelta(days=1)
                    }
                    
                    close_time = open_time + timeframe_deltas.get(timeframe, timedelta(hours=1))
                    
                    # ✅ СОГЛАСНО ВАШЕЙ БД: interval и open_time
                    existing = db_session.query(Candle.id).filter(
                        Candle.symbol == symbol,
                        Candle.interval == timeframe,  # ✅ ПРАВИЛЬНОЕ ПОЛЕ
                        Candle.open_time == open_time  # ✅ ПРАВИЛЬНОЕ ПОЛЕ
                    ).first()
                    
                    if not existing:
                        candle = Candle(
                            symbol=symbol,
                            interval=timeframe,        # ✅ ПРАВИЛЬНОЕ ПОЛЕ
                            open_time=open_time,       # ✅ ПРАВИЛЬНОЕ ПОЛЕ
                            close_time=close_time,     # ✅ ЕСТЬ В ВАШЕЙ БД
                            open=float(candle_data[1]),
                            high=float(candle_data[2]),
                            low=float(candle_data[3]),
                            close=float(candle_data[4]),
                            volume=float(candle_data[5])
                        )
                        candles_to_save.append(candle)
                        
                except Exception as e:
                    logger.debug(f"Ошибка обработки свечи: {e}")
                    continue
            
            # Сохраняем пакетом
            if candles_to_save:
                db_session.add_all(candles_to_save)
                db_session.commit()
                saved_count = len(candles_to_save)
                logger.info(f"💾 Сохранено {saved_count} новых свечей для {symbol}")
            
            if callable(self.db):
                db_session.close()
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения свечей: {e}")
            if 'db_session' in locals():
                db_session.rollback()
                if callable(self.db):
                    db_session.close()
        
    async def _continuous_collection(self):
        """Непрерывный сбор данных"""
        while self.is_running:
            try:
                # Получаем список активных пар
                active_pairs = await self._get_active_pairs()
                
                # Собираем данные для каждой пары
                tasks = []
                for symbol in active_pairs:
                    task = asyncio.create_task(self.collect_market_data(symbol))
                    tasks.append(task)
                
                # Ждем завершения всех задач
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Сохраняем в БД если есть подключение
                if self.db:
                    await self._save_to_database()
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в continuous_collection: {e}")
                await asyncio.sleep(10)
    
    async def collect_market_data(self, symbol: str, data: dict = None) -> Dict[str, Any]:
        """Сбор рыночных данных для символа"""
        try:
            # Если данные переданы извне (для совместимости)
            if data is not None:  # ✅ ИСПРАВЛЕНО: проверка на None вместо if data
                self.collected_data[symbol] = {
                    'data': data,
                    'timestamp': datetime.utcnow()
                }
                logger.debug(f"📊 Сохранены внешние данные для {symbol}")
                return data
            
            # Иначе собираем сами
            collected = {}
            
            # 1. Получаем текущую цену и тикер
            ticker = await self.exchange.fetch_ticker(symbol)
            if ticker:
                collected['ticker'] = {
                    'symbol': symbol,
                    'last': float(ticker.get('last', 0)),  # ✅ ИСПРАВЛЕНО: преобразование в float
                    'bid': float(ticker.get('bid', 0)),
                    'ask': float(ticker.get('ask', 0)),
                    'volume': float(ticker.get('baseVolume', 0)),
                    'quote_volume': float(ticker.get('quoteVolume', 0)),
                    'change': float(ticker.get('percentage', 0)),
                    'timestamp': datetime.utcnow()
                }
            
            # 2. Получаем стакан ордеров
            orderbook = await self.exchange.fetch_order_book(symbol, limit=20)
            if orderbook:
                collected['orderbook'] = {
                    'bids': orderbook.get('bids', [])[:10],
                    'asks': orderbook.get('asks', [])[:10],
                    'timestamp': orderbook.get('timestamp', datetime.utcnow())
                }
                
                # Рассчитываем спред и глубину
                if orderbook['bids'] and orderbook['asks']:
                    best_bid = float(orderbook['bids'][0][0])  # ✅ ИСПРАВЛЕНО: преобразование в float
                    best_ask = float(orderbook['asks'][0][0])
                    collected['spread'] = (best_ask - best_bid) / best_bid * 100
                    collected['bid_depth'] = sum(float(bid[1]) for bid in orderbook['bids'][:5])
                    collected['ask_depth'] = sum(float(ask[1]) for ask in orderbook['asks'][:5])
            
            # 3. Получаем последние сделки
            trades = await self.exchange.fetch_trades(symbol, limit=100)
            if trades:
                # ✅ ИСПРАВЛЕНО: безопасное получение суммы с преобразованием типов
                buy_volume = sum(float(t.get('amount', 0)) for t in trades if t.get('side') == 'buy')
                sell_volume = sum(float(t.get('amount', 0)) for t in trades if t.get('side') == 'sell')
                total_price = sum(float(t.get('price', 0)) for t in trades)
                
                collected['recent_trades'] = {
                    'count': len(trades),
                    'buy_volume': buy_volume,
                    'sell_volume': sell_volume,
                    'avg_price': total_price / len(trades) if trades else 0,
                    'timestamp': datetime.utcnow()
                }
            
            # 4. Получаем свечи для технического анализа
            ohlcv = await self.exchange.fetch_ohlcv(symbol, '5m', limit=200)
            if ohlcv:
                # ✅ ИСПРАВЛЕНО: преобразование timestamp и безопасная работа с данными
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                # Преобразуем колонки в числовые типы
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Преобразуем timestamp
                if df['timestamp'].dtype == 'object':
                    df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Удаляем строки с NaN после преобразования
                df = df.dropna()
                
                if len(df) >= 20:  # Проверяем, что есть достаточно данных
                    collected['candles'] = df.to_dict('records')  # Последние 20 свечей
                    collected['technical'] = {
                        'sma_20': float(df['close'].rolling(20).mean().iloc[-1]),
                        'volume_avg': float(df['volume'].rolling(20).mean().iloc[-1]),
                        'volatility': float(df['close'].pct_change().std() * 100),
                        'high_24h': float(df['high'].max()),
                        'low_24h': float(df['low'].min())
                    }
            
            # Сохраняем в кеш
            self.collected_data[symbol] = {
                'data': collected,
                'timestamp': datetime.utcnow()
            }
            
            logger.debug(f"📊 Собраны данные для {symbol}")
            return collected
            
        except Exception as e:
            logger.error(f"❌ Ошибка сбора данных для {symbol}: {e}")
            return {}
    
    async def collect_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """Сбор данных стакана"""
        try:
            orderbook = await self.exchange.fetch_order_book(symbol, limit=depth)
            return orderbook
        except Exception as e:
            logger.error(f"❌ Ошибка сбора стакана {symbol}: {e}")
            return {}
    
    async def _get_active_pairs(self) -> List[str]:
        """Получение списка активных торговых пар"""
        # Если список уже задан
        if self.active_pairs:
            return self.active_pairs
        
        # Получаем из конфигурации
        try:
            from ..core.unified_config import unified_config
            return unified_config.TRADING_PAIRS or ['BTCUSDT', 'ETHUSDT']
        except:
            return ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'BNBUSDT', 'SOLUSDT']
    
    def set_active_pairs(self, pairs: List[str]):
        """Установка списка активных пар"""
        self.active_pairs = pairs
        logger.info(f"📊 Установлены активные пары: {pairs}")
    
    async def _save_to_database(self):
        """Сохранение текущих данных в БД"""
        if not self.db:
            return
        
        try:
            # Проверяем, что db - это функция для создания сессии
            if callable(self.db):
                db_session = self.db()
            else:
                db_session = self.db
                
            from ..core.models import MarketCondition
            
            # Сохраняем рыночные условия для каждой пары
            for symbol, data_wrapper in self.collected_data.items():
                if 'data' in data_wrapper and 'ticker' in data_wrapper['data']:
                    ticker = data_wrapper['data']['ticker']
                    
                    # ✅ ИСПРАВЛЕНО: создаем объект ТОЛЬКО с теми полями, которые ЕСТЬ в БД
                    market_condition = MarketCondition(
                        symbol=symbol,
                        timeframe='5m',
                        condition_type='price_level',
                        condition_value=str(ticker['last']),
                        strength=ticker['change'] / 100 if ticker['change'] else 0,
                        indicators={
                            'volume': ticker['volume'],
                            'bid': ticker['bid'],
                            'ask': ticker['ask'],
                            'spread': data_wrapper['data'].get('spread', 0)
                        },
                        timestamp=datetime.utcnow()
                    )
                    
                    # НЕ пытаемся сохранить несуществующие поля!
                    db_session.add(market_condition)
            
            db_session.commit()
            
            # Закрываем сессию если создавали её
            if callable(self.db):
                db_session.close()
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в БД: {e}")
            if 'db_session' in locals():
                db_session.rollback()
                if callable(self.db):
                    db_session.close()
    
    def get_data(self, symbol: str) -> Dict[str, Any]:
        """Получение собранных данных"""
        return self.collected_data.get(symbol, {})
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса сборщика"""
        return {
            'running': self.is_running,
            'initialized': self.is_initialized,
            'data_count': len(self.collected_data),
            'symbols': list(self.collected_data.keys()),
            'last_update': max(
                (d['timestamp'] for d in self.collected_data.values() if 'timestamp' in d),
                default=None
            )
        }
        
    def get_latest_candles(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> Optional[pd.DataFrame]:
        """
        Получение последних свечей для символа из базы данных
        """
        try:
            # ИСПРАВЛЕНО: правильное использование self.db
            if callable(self.db):
                db_session = self.db()
            else:
                db_session = self.db
                
            try:
                # Преобразуем timeframe в числовое значение
                timeframe_mapping = {
                    '1m': 1,
                    '5m': 5,
                    '15m': 15,
                    '30m': 30,
                    '1h': 60,
                    '4h': 240,
                    '1d': 1440
                }
                
                interval_minutes = timeframe_mapping.get(timeframe, 60)
                
                # Запрос к БД
                candles = db_session.query(Candle).filter(
                    Candle.symbol == symbol,
                    Candle.interval == timeframe
                ).order_by(Candle.open_time.desc()).limit(limit).all()
                
                if not candles:
                    return None
                
                # Преобразуем в DataFrame
                data = []
                for candle in reversed(candles):
                    data.append({
                        'timestamp': candle.open_time,
                        'open': float(candle.open),
                        'high': float(candle.high),
                        'low': float(candle.low),
                        'close': float(candle.close),
                        'volume': float(candle.volume)
                    })
                
                df = pd.DataFrame(data)
                df.set_index('timestamp', inplace=True)
                
                return df
                
            finally:
                if callable(self.db):
                    db_session.close()
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения свечей из БД: {e}")
            return None

    
    async def get_latest_candles_async(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> Optional[pd.DataFrame]:
        """
        Асинхронная версия get_latest_candles
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм
            limit: Количество свечей
            
        Returns:
            pd.DataFrame: DataFrame со свечами или None
        """
        try:
            # Выполняем синхронную операцию в executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                self.get_latest_candles, 
                symbol, 
                timeframe, 
                limit
            )
        except Exception as e:
            logger.error(f"❌ Ошибка async получения свечей для {symbol}: {e}")
            return None
    
    def get_symbol_data(self, symbol: str, timeframe: str = '1h') -> Optional[pd.DataFrame]:
        """
        Альтернативное название для get_latest_candles для совместимости
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм
            
        Returns:
            pd.DataFrame: DataFrame со свечами или None
        """
        return self.get_latest_candles(symbol, timeframe, limit=200)
    
    def get_all_data(self) -> Dict[str, Any]:
        """Получение всех собранных данных"""
        return dict(self.collected_data)
#!/usr/bin/env python3
"""
Продюсер для сбора рыночных данных с Bybit
Файл: src/api_clients/bybit_data_producer.py

✅ ИСПРАВЛЕНИЯ:
- Интервалы теперь читаются из конфигурации
- Улучшена настройка через .env файл
- Добавлены fallback значения

Собирает данные о стакане ордеров и аномальных объемах
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import numpy as np
import json

try:
    from pybit.unified_trading import HTTP
    PYBIT_AVAILABLE = True
except ImportError:
    PYBIT_AVAILABLE = False
    HTTP = None

from ..core.database import SessionLocal
from ..core.models import OrderBookSnapshot, VolumeAnomaly
from ..core.unified_config import unified_config as config
from ..exchange.unified_exchange import UnifiedExchangeClient

logger = logging.getLogger(__name__)


class BybitDataProducer:
    """
    Продюсер для сбора рыночных данных с Bybit
    - Снимки стакана ордеров с расчетом OFI
    - Детекция аномальных объемов
    - Мониторинг потока сделок
    
    ✅ НАСТРОЙКА ИНТЕРВАЛОВ ЧЕРЕЗ КОНФИГУРАЦИЮ
    """
    
    # Настройки по умолчанию (fallback значения)
    DEFAULT_ORDERBOOK_DEPTH = 50
    DEFAULT_SNAPSHOT_INTERVAL = 60  # секунд
    DEFAULT_VOLUME_WINDOW = 24  # часов
    VOLUME_ANOMALY_THRESHOLD = 3.0  # стандартных отклонения
    
    def __init__(self, testnet: bool = True):
        """
        Инициализация продюсера
        
        Args:
            testnet: Использовать тестовую сеть
        """
        self.testnet = testnet
        self.is_running = False
        
        # Инициализация клиентов
        self.exchange_client = UnifiedExchangeClient()
        self.http_client = None
        
        if PYBIT_AVAILABLE:
            self._init_pybit_client()
        else:
            logger.warning("⚠️ pybit не установлен, используем альтернативный клиент")
            
        # Кэш данных
        self.volume_history = {}  # История объемов по символам
        self.last_orderbook = {}  # Последний стакан по символам
        self.ofi_history = {}     # История OFI для анализа
        
        # Отслеживаемые символы из конфигурации
        self.symbols = getattr(config, 'TRACKED_SYMBOLS', [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT'
        ])
        
        # ✅ ИНТЕРВАЛЫ ИЗ КОНФИГУРАЦИИ
        self.snapshot_interval = getattr(config, 'ORDERBOOK_SNAPSHOT_INTERVAL', self.DEFAULT_SNAPSHOT_INTERVAL)
        self.volume_check_interval = getattr(config, 'VOLUME_CHECK_INTERVAL', 300)  # 5 минут
        self.trades_update_interval = getattr(config, 'TRADES_UPDATE_INTERVAL', 3600)  # 1 час
        
        logger.info(f"📊 Настроенные интервалы:")
        logger.info(f"   📸 Снимки стакана: {self.snapshot_interval}с")
        logger.info(f"   📈 Проверка объемов: {self.volume_check_interval}с")
        logger.info(f"   📡 Обновление сделок: {self.trades_update_interval}с")
        
    def _init_pybit_client(self):
        """Инициализация Pybit клиента"""
        try:
            if self.testnet:
                self.http_client = HTTP(
                    testnet=True,
                    api_key=getattr(config, 'BYBIT_TESTNET_API_KEY', ''),
                    api_secret=getattr(config, 'BYBIT_TESTNET_API_SECRET', '')
                )
            else:
                self.http_client = HTTP(
                    testnet=False,
                    api_key=getattr(config, 'BYBIT_API_KEY', ''),
                    api_secret=getattr(config, 'BYBIT_API_SECRET', '')
                )
            logger.info("✅ Pybit клиент инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Pybit: {e}")
            self.http_client = None
            
    async def start(self):
        """Запуск продюсера"""
        logger.info(f"🚀 Запуск BybitDataProducer (testnet={self.testnet})...")
        
        # Подключаемся к бирже через UnifiedExchangeClient
        connected = await self.exchange_client.connect('bybit', self.testnet)
        if not connected:
            logger.error("❌ Не удалось подключиться к Bybit")
            return
            
        self.is_running = True
        
        # Инициализируем историю объемов
        await self._init_volume_history()
        
        # Запускаем параллельные задачи
        tasks = [
            asyncio.create_task(self._orderbook_snapshot_loop()),
            asyncio.create_task(self._volume_monitor_loop()),
            asyncio.create_task(self._trades_stream_monitor())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("🛑 Задачи BybitDataProducer отменены")
        except Exception as e:
            logger.error(f"❌ Ошибка в BybitDataProducer: {e}")
        
    async def stop(self):
        """Остановка продюсера"""
        logger.info("🛑 Остановка BybitDataProducer...")
        self.is_running = False
        await self.exchange_client.disconnect()
        
    async def _init_volume_history(self):
        """Инициализация истории объемов для каждого символа"""
        logger.info("📊 Загрузка исторических данных объемов...")
        
        for symbol in self.symbols:
            try:
                # Получаем свечи за последние 24 часа
                klines = await self.exchange_client.get_klines(
                    symbol=symbol,
                    interval='1h',
                    limit=24
                )
                
                if klines and 'data' in klines:
                    volumes = [float(k[5]) for k in klines['data']]  # volume
                    self.volume_history[symbol] = volumes
                    logger.debug(f"✅ Загружена история для {symbol}: {len(volumes)} свечей")
                else:
                    self.volume_history[symbol] = []
                    
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки истории {symbol}: {e}")
                self.volume_history[symbol] = []
                
    async def _orderbook_snapshot_loop(self):
        """
        Цикл создания снимков стакана ордеров
        ✅ ИНТЕРВАЛ ИЗ КОНФИГУРАЦИИ
        """
        logger.info("📸 Запуск цикла снимков стакана...")
        
        # ✅ ИСПРАВЛЕНИЕ: Используем интервал из конфигурации
        interval = getattr(config, 'ORDERBOOK_SNAPSHOT_INTERVAL', self.DEFAULT_SNAPSHOT_INTERVAL)
        logger.info(f"⏱️ Интервал снимков стакана: {interval}с")
        
        while self.is_running:
            try:
                for symbol in self.symbols:
                    await self._capture_orderbook_snapshot(symbol)
                    
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                logger.info("🛑 Цикл снимков стакана остановлен")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле стакана: {e}")
                await asyncio.sleep(10)
                
    async def _capture_orderbook_snapshot(self, symbol: str):
        """Создание снимка стакана ордеров"""
        try:
            # Получаем стакан
            orderbook = await self.exchange_client.get_order_book(
                symbol=symbol,
                limit=self.DEFAULT_ORDERBOOK_DEPTH
            )
            
            if not orderbook or 'error' in orderbook:
                return
                
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            if not bids or not asks:
                return
                
            # Рассчитываем метрики
            bid_volume = sum(float(bid[1]) for bid in bids)
            ask_volume = sum(float(ask[1]) for ask in asks)
            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            spread = best_ask - best_bid
            mid_price = (best_bid + best_ask) / 2
            imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0
            
            # Рассчитываем OFI (Order Flow Imbalance)
            ofi = self._calculate_ofi(symbol, bids, asks)
            
            # Сохраняем снимок
            await self._save_orderbook_snapshot({
                'symbol': symbol,
                'bids': bids[:20],  # Сохраняем топ-20 уровней
                'asks': asks[:20],
                'bid_volume': bid_volume,
                'ask_volume': ask_volume,
                'spread': spread,
                'mid_price': mid_price,
                'imbalance': imbalance,
                'ofi': ofi,
                'timestamp': datetime.utcnow()
            })
            
            # Обновляем кэш
            self.last_orderbook[symbol] = {
                'bids': bids,
                'asks': asks,
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка снимка стакана {symbol}: {e}")
            
    def _calculate_ofi(self, symbol: str, bids: List, asks: List) -> float:
        """
        Расчет Order Flow Imbalance
        OFI = Σ(ΔBid_i * Price_i) - Σ(ΔAsk_i * Price_i)
        """
        ofi = 0.0
        
        if symbol in self.last_orderbook:
            last_bids = {float(b[0]): float(b[1]) for b in self.last_orderbook[symbol]['bids']}
            last_asks = {float(a[0]): float(a[1]) for a in self.last_orderbook[symbol]['asks']}
            
            # Рассчитываем изменения в bid
            for bid in bids[:10]:  # Топ-10 уровней
                price = float(bid[0])
                size = float(bid[1])
                last_size = last_bids.get(price, 0)
                delta = size - last_size
                ofi += delta * price
                
            # Рассчитываем изменения в ask
            for ask in asks[:10]:
                price = float(ask[0])
                size = float(ask[1])
                last_size = last_asks.get(price, 0)
                delta = size - last_size
                ofi -= delta * price
                
        # Сохраняем историю OFI
        if symbol not in self.ofi_history:
            self.ofi_history[symbol] = []
        self.ofi_history[symbol].append(ofi)
        
        # Ограничиваем размер истории
        if len(self.ofi_history[symbol]) > 100:
            self.ofi_history[symbol] = self.ofi_history[symbol][-100:]
            
        return ofi
        
    async def _volume_monitor_loop(self):
        """
        Цикл мониторинга объемов
        ✅ ИНТЕРВАЛ ИЗ КОНФИГУРАЦИИ
        """
        logger.info("📈 Запуск мониторинга объемов...")
        
        # ✅ ИСПОЛЬЗУЕМ ИНТЕРВАЛ ИЗ КОНФИГУРАЦИИ
        check_interval = getattr(config, 'VOLUME_CHECK_INTERVAL', 300)  # 5 минут по умолчанию
        logger.info(f"⏱️ Интервал проверки объемов: {check_interval}с")
        
        while self.is_running:
            try:
                for symbol in self.symbols:
                    await self._check_volume_anomaly(symbol)
                    
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                logger.info("🛑 Мониторинг объемов остановлен")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга объемов: {e}")
                await asyncio.sleep(30)
                
    async def _check_volume_anomaly(self, symbol: str):
        """Проверка на аномальные объемы"""
        try:
            # Получаем текущий тикер
            ticker = await self.exchange_client.get_ticker(symbol)
            
            if not ticker or 'error' in ticker:
                return
                
            current_volume = float(ticker.get('volume24h', 0))
            current_price = float(ticker.get('last', 0))
            price_change = float(ticker.get('percentage', 0))
            
            # Получаем историю объемов
            if symbol not in self.volume_history or len(self.volume_history[symbol]) < 10:
                return
                
            volumes = self.volume_history[symbol]
            avg_volume = np.mean(volumes)
            std_volume = np.std(volumes)
            
            if std_volume == 0:
                return
                
            # Z-score для определения аномалии
            z_score = (current_volume - avg_volume) / std_volume
            
            # Детектируем различные типы аномалий
            anomaly_type = None
            if abs(z_score) > self.VOLUME_ANOMALY_THRESHOLD:
                if z_score > 0:
                    if price_change > 2:
                        anomaly_type = 'unusual_buy'
                    else:
                        anomaly_type = 'spike'
                else:
                    if price_change < -2:
                        anomaly_type = 'unusual_sell'
                    else:
                        anomaly_type = 'divergence'
                        
            if anomaly_type:
                await self._save_volume_anomaly({
                    'symbol': symbol,
                    'anomaly_type': anomaly_type,
                    'volume': current_volume,
                    'avg_volume': avg_volume,
                    'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 0,
                    'price': current_price,
                    'price_change': price_change,
                    'z_score': z_score,
                    'timestamp': datetime.utcnow()
                })
                
                logger.warning(f"🚨 Аномалия объема {symbol}: {anomaly_type} "
                             f"(z-score: {z_score:.2f}, ratio: {current_volume/avg_volume:.2f})")
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки аномалии {symbol}: {e}")
            
    async def _trades_stream_monitor(self):
        """
        Мониторинг потока сделок
        ✅ ИНТЕРВАЛ ИЗ КОНФИГУРАЦИИ
        """
        logger.info("📡 Мониторинг потока сделок запущен (polling mode)")
        
        # ✅ ИСПОЛЬЗУЕМ ИНТЕРВАЛ ИЗ КОНФИГУРАЦИИ
        update_interval = getattr(config, 'TRADES_UPDATE_INTERVAL', 3600)  # 1 час по умолчанию
        logger.info(f"⏱️ Интервал обновления сделок: {update_interval}с")
        
        # В production здесь должен быть WebSocket
        # Сейчас используем polling для демонстрации
        
        while self.is_running:
            try:
                # Обновляем историю объемов
                await self._init_volume_history()
                await asyncio.sleep(update_interval)
                
            except asyncio.CancelledError:
                logger.info("🛑 Мониторинг сделок остановлен")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в мониторинге сделок: {e}")
                await asyncio.sleep(60)
                
    async def _save_orderbook_snapshot(self, snapshot_data: Dict):
        """Сохранение снимка стакана в БД"""
        db = SessionLocal()
        
        try:
            snapshot = OrderBookSnapshot(
                symbol=snapshot_data['symbol'],
                exchange='bybit',
                timestamp=snapshot_data['timestamp'],
                bids=json.dumps(snapshot_data['bids']),
                asks=json.dumps(snapshot_data['asks']),
                bid_volume=Decimal(str(snapshot_data['bid_volume'])),
                ask_volume=Decimal(str(snapshot_data['ask_volume'])),
                spread=Decimal(str(snapshot_data['spread'])),
                mid_price=Decimal(str(snapshot_data['mid_price'])),
                imbalance=Decimal(str(snapshot_data['imbalance'])),
                ofi=Decimal(str(snapshot_data['ofi']))
            )
            
            db.add(snapshot)
            db.commit()
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения снимка стакана: {e}")
            db.rollback()
        finally:
            db.close()
            
    async def _save_volume_anomaly(self, anomaly_data: Dict):
        """Сохранение аномалии объема в БД"""
        db = SessionLocal()
        
        try:
            anomaly = VolumeAnomaly(
                symbol=anomaly_data['symbol'],
                exchange='bybit',
                anomaly_type=anomaly_data['anomaly_type'],
                timestamp=anomaly_data['timestamp'],
                volume=Decimal(str(anomaly_data['volume'])),
                avg_volume=Decimal(str(anomaly_data['avg_volume'])),
                volume_ratio=Decimal(str(anomaly_data['volume_ratio'])),
                price=Decimal(str(anomaly_data['price'])),
                price_change=Decimal(str(anomaly_data['price_change'])),
                details=json.dumps({
                    'z_score': anomaly_data['z_score'],
                    'volume_volatility': float(np.std(self.volume_history.get(anomaly_data['symbol'], [0])))
                })
            )
            
            db.add(anomaly)
            db.commit()
            logger.info(f"✅ Сохранена аномалия объема для {anomaly_data['symbol']}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения аномалии: {e}")
            db.rollback()
        finally:
            db.close()
            
    def get_market_metrics(self, symbol: str) -> Dict[str, Any]:
        """Получение текущих рыночных метрик для символа"""
        metrics = {
            'ofi_trend': 'neutral',
            'volume_status': 'normal',
            'orderbook_imbalance': 0.0,
            'recent_anomalies': 0
        }
        
        # Анализ тренда OFI
        if symbol in self.ofi_history and len(self.ofi_history[symbol]) >= 5:
            recent_ofi = self.ofi_history[symbol][-5:]
            ofi_mean = np.mean(recent_ofi)
            
            if ofi_mean > 1000:
                metrics['ofi_trend'] = 'bullish'
            elif ofi_mean < -1000:
                metrics['ofi_trend'] = 'bearish'
                
        # Статус объема
        if symbol in self.volume_history and len(self.volume_history[symbol]) > 10:
            volumes = self.volume_history[symbol]
            current_volume = volumes[-1] if volumes else 0
            avg_volume = np.mean(volumes[:-1]) if len(volumes) > 1 else 0
            
            if avg_volume > 0:
                if current_volume > avg_volume * 1.5:
                    metrics['volume_status'] = 'high'
                elif current_volume < avg_volume * 0.5:
                    metrics['volume_status'] = 'low'
                
        # Дисбаланс стакана
        if symbol in self.last_orderbook:
            orderbook = self.last_orderbook[symbol]
            bid_volume = sum(float(b[1]) for b in orderbook['bids'][:10])
            ask_volume = sum(float(a[1]) for a in orderbook['asks'][:10])
            
            if bid_volume + ask_volume > 0:
                metrics['orderbook_imbalance'] = (bid_volume - ask_volume) / (bid_volume + ask_volume)
                
        return metrics

    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики работы продюсера"""
        return {
            'symbols_tracked': len(self.symbols),
            'volume_history_size': sum(len(v) for v in self.volume_history.values()),
            'ofi_history_size': sum(len(v) for v in self.ofi_history.values()),
            'orderbook_cache_size': len(self.last_orderbook),
            'is_running': self.is_running,
            'intervals': {
                'snapshot': self.snapshot_interval,
                'volume_check': self.volume_check_interval,
                'trades_update': self.trades_update_interval
            }
        }


# Функция для запуска продюсера
async def main():
    """Пример запуска продюсера"""
    producer = BybitDataProducer(testnet=True)
    
    try:
        await producer.start()
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
    finally:
        await producer.stop()


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())
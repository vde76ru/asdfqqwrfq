# Файл: src/strategies/order_book_analysis.py
# ОПИСАНИЕ: Стратегия анализа биржевого стакана для детекции манипуляций и генерации торговых сигналов.
# ИСПРАВЛЕНО: Унифицирована логика для работы как в автономном режиме, так и под управлением BotManager.
# Добавлено получение exchange_client из глобального bot_manager для автономного режима.

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio
import json
from decimal import Decimal
import numpy as np
from sqlalchemy import and_, desc

# --- ИСПРАВЛЕНИЕ: Добавляем импорт bot_manager для доступа к exchange_client ---
try:
    from ..bot.manager import bot_manager
except (ImportError, ModuleNotFoundError):
    # Если bot_manager не может быть импортирован (например, при тестировании),
    # устанавливаем его в None, чтобы избежать падения.
    bot_manager = None

from ..core.database import SessionLocal
from ..core.models import (
    OrderBookSnapshot,
    Signal,
    SignalTypeEnum
)

logger = logging.getLogger(__name__)


class OrderBookAnalysisStrategy:
    """Стратегия анализа биржевого стакана для выявления манипуляций"""

    def __init__(self, config: Dict = None, exchange_client: Any = None): # <-- Добавляем exchange_client
        self.config = config or {}
        self.exchange_client = exchange_client # <-- Сохраняем его
        self.name = "order_book_analysis"
        self.is_running = False

        # Параметры стратегии
        self.wall_threshold = self.config.get('wall_threshold', 5.0)
        self.spoofing_time_window = self.config.get('spoofing_time_window', 300)
        self.absorption_volume_ratio = self.config.get('absorption_volume_ratio', 3.0)
        self.imbalance_threshold = self.config.get('imbalance_threshold', 2.0)
        self.lookback_minutes = self.config.get('lookback_minutes', 30)
        self.min_signal_strength = self.config.get('min_signal_strength', 0.5)

        logger.info(f"Стратегия {self.name} инициализирована")

    # --- Методы для автономного запуска (сохранены по вашей просьбе) ---
    async def start(self):
        """Запуск стратегии в автономном режиме"""
        if not bot_manager:
            logger.error(f"Не удалось запустить автономный режим для {self.name}: bot_manager не найден.")
            return

        logger.info(f"Запуск стратегии {self.name} в автономном режиме")
        self.is_running = True
        try:
            while self.is_running:
                await self.run()
                await asyncio.sleep(60)  # Анализ каждую минуту
        except asyncio.CancelledError:
            logger.info(f"Автономный цикл стратегии {self.name} был отменен.")
        except Exception as e:
            logger.error(f"Ошибка в основном цикле стратегии {self.name}: {e}")
        finally:
            self.is_running = False
            logger.info(f"Автономный режим стратегии {self.name} остановлен.")

    async def stop(self):
        """Остановка автономного режима стратегии"""
        logger.info(f"Остановка стратегии {self.name}")
        self.is_running = False

    async def run(self):
        """Основной цикл анализа для автономного режима"""
        logger.debug(f"{self.name}: запуск автономного цикла анализа...")
        db_session = SessionLocal()
        try:
            # ИСПРАВЛЕНИЕ: Получаем exchange_client из bot_manager
            if not bot_manager or not bot_manager.exchange_client:
                logger.warning(f"Пропуск цикла {self.name}: exchange_client не инициализирован в bot_manager.")
                return

            exchange_client = bot_manager.exchange_client
            symbols = await self._get_active_symbols(db_session)

            if not symbols:
                logger.debug(f"В автономном цикле {self.name} не найдено активных символов для анализа.")
                return

            for symbol in symbols:
                # Вызываем основной метод анализа для каждого символа
                await self.analyze(symbol, exchange_client=exchange_client)

        except Exception as e:
            logger.error(f"Ошибка в цикле run стратегии {self.name}: {e}")
            db_session.rollback()
        finally:
            db_session.close()

    # --- Основной метод анализа, вызываемый из BotManager или автономного режима ---
    async def analyze(self, symbol: str, exchange_client=None) -> Optional[Dict]:
        """
        Анализ одного символа для поиска торговых сигналов.

        Args:
            symbol: Торговая пара для анализа
            exchange_client: Клиент биржи для получения данных

        Returns:
            Словарь с сигналом в формате для BotManager или None
        """
        if exchange_client is None:
            exchange_client = self.exchange_client 
        
        if not exchange_client:
            logger.warning(f"⚠️ В {self.name} не был передан exchange_client для анализа {symbol}")
            return None

        db_session = SessionLocal()
        try:
            # 1. Получаем снимки стакана из БД для анализа паттернов
            snapshots = await self._get_order_book_snapshots(db_session, symbol)

            # 2. Анализируем паттерны (стены, спуфинг и т.д.)
            signal_data = None
            if len(snapshots) > 1:
                signal_data = await self._detect_walls(snapshots[-1])
                if not signal_data:
                    signal_data = await self._detect_spoofing(snapshots)
                if not signal_data:
                    signal_data = await self._detect_absorption(snapshots)
                if not signal_data:
                    signal_data = await self._detect_imbalance(snapshots[-1])

            # 3. Если паттерн найден, сохраняем и возвращаем сигнал
            if signal_data and signal_data.get('strength', 0) > self.min_signal_strength:
                await self._save_signal(db_session, signal_data)
                db_session.commit()
                
                logger.info(f"✅ {self.name}: найден сигнал {signal_data['signal_type'].name} для {symbol} (уверенность: {signal_data['strength']:.2f})")
                
                # Возвращаем сигнал в формате для BotManager
                return {
                    'action': signal_data['signal_type'].name,  # BUY или SELL
                    'confidence': signal_data['strength'],
                    'take_profit': None,
                    'stop_loss': None,
                    'reason': f"{signal_data['strategy']}: {signal_data.get('metadata', {}).get('wall_type', 'imbalance')}"
                }
            else:
                logger.debug(f"Для {symbol} не найдено значимых паттернов в стакане.")

        except Exception as e:
            logger.error(f"❌ Ошибка анализа {symbol} в стратегии {self.name}: {e}")
            db_session.rollback()
        finally:
            db_session.close()

        return None

    # --- Вспомогательные методы ---

    async def _get_orderbook_safely(self, symbol: str, exchange_client) -> Optional[Dict]:
        """Безопасное получение стакана ордеров"""
        try:
            if hasattr(exchange_client, 'fetch_order_book'):
                return await exchange_client.fetch_order_book(symbol, limit=50)
            elif hasattr(exchange_client, 'get_order_book'):
                return await exchange_client.get_order_book(symbol, limit=50)
            elif hasattr(exchange_client, 'get_orderbook'):
                return await exchange_client.get_orderbook(symbol, limit=50)
            else:
                logger.warning(f"⚠️ Нет подходящего метода для получения стакана в exchange_client для {symbol}")
                return None
        except Exception as e:
            logger.debug(f"Не удалось получить стакан для {symbol}: {e}")
            return None

    async def _detect_walls(self, snapshot: OrderBookSnapshot) -> Optional[Dict]:
        """Детекция стен в стакане"""
        try:
            bids = json.loads(snapshot.bids) if snapshot.bids else []
            asks = json.loads(snapshot.asks) if snapshot.asks else []
            total_bid_volume = sum(float(bid[1]) for bid in bids)
            total_ask_volume = sum(float(ask[1]) for ask in asks)
            total_volume = total_bid_volume + total_ask_volume
            if total_volume == 0: return None

            for i, bid in enumerate(bids[:10]):
                bid_size = float(bid[1])
                if (bid_size / total_volume) * 100 > self.wall_threshold:
                    return { 'symbol': snapshot.symbol, 'signal_type': SignalTypeEnum.SELL, 'strength': min(1.0, bid_size / total_volume), 'strategy': 'order_book_walls', 'metadata': { 'wall_type': 'bid', 'wall_price': float(bid[0]), 'wall_size': bid_size, 'wall_percentage': (bid_size / total_volume) * 100, 'level': i + 1 } }

            for i, ask in enumerate(asks[:10]):
                ask_size = float(ask[1])
                if (ask_size / total_volume) * 100 > self.wall_threshold:
                    return { 'symbol': snapshot.symbol, 'signal_type': SignalTypeEnum.BUY, 'strength': min(1.0, ask_size / total_volume), 'strategy': 'order_book_walls', 'metadata': { 'wall_type': 'ask', 'wall_price': float(ask[0]), 'wall_size': ask_size, 'wall_percentage': (ask_size / total_volume) * 100, 'level': i + 1 } }
        except Exception as e:
            logger.error(f"Ошибка при детекции стен: {e}")
        return None

    async def _detect_spoofing(self, snapshots: List[OrderBookSnapshot]) -> Optional[Dict]:
        """Детекция спуфинга - появление и исчезновение крупных ордеров"""
        try:
            if len(snapshots) < 2: return None
            prev_snapshot, curr_snapshot = snapshots[-2], snapshots[-1]
            time_diff = (curr_snapshot.timestamp - prev_snapshot.timestamp).total_seconds()
            if time_diff > self.spoofing_time_window: return None

            prev_orders = {'bids': json.loads(prev_snapshot.bids), 'asks': json.loads(prev_snapshot.asks)}
            curr_orders = {'bids': json.loads(curr_snapshot.bids), 'asks': json.loads(curr_snapshot.asks)}
            disappeared_orders = self._find_disappeared_orders(prev_orders, curr_orders)

            if disappeared_orders:
                total_disappeared_volume = sum(order['volume'] for order in disappeared_orders)
                bid_disappeared = sum(order['volume'] for order in disappeared_orders if order['side'] == 'bid')
                ask_disappeared = sum(order['volume'] for order in disappeared_orders if order['side'] == 'ask')
                signal_type = SignalTypeEnum.SELL if bid_disappeared > ask_disappeared else SignalTypeEnum.BUY
                strength = min(1.0, total_disappeared_volume / (float(prev_snapshot.bid_volume) + float(prev_snapshot.ask_volume)))
                return { 'symbol': curr_snapshot.symbol, 'signal_type': signal_type, 'strength': strength, 'strategy': 'order_book_spoofing', 'metadata': { 'disappeared_orders': len(disappeared_orders), 'disappeared_volume': total_disappeared_volume, 'bid_disappeared': bid_disappeared, 'ask_disappeared': ask_disappeared, 'time_diff_seconds': time_diff } }
        except Exception as e:
            logger.error(f"Ошибка при детекции спуфинга: {e}")
        return None

    def _find_disappeared_orders(self, prev: Dict, curr: Dict) -> List[Dict]:
        """Поиск исчезнувших крупных ордеров, работая со списками."""
        disappeared = []
        prev_bids, prev_asks = prev.get('bids', []), prev.get('asks', [])
        curr_bids_prices = {float(b[0]) for b in curr.get('bids', [])}
        curr_asks_prices = {float(a[0]) for a in curr.get('asks', [])}
        prev_total_volume = sum(float(b[1]) for b in prev_bids) + sum(float(a[1]) for a in prev_asks)
        if prev_total_volume == 0: return []
        volume_threshold = prev_total_volume * 0.01

        for prev_bid in prev_bids[:10]:
            price, volume = float(prev_bid[0]), float(prev_bid[1])
            if volume > volume_threshold and price not in curr_bids_prices:
                disappeared.append({'side': 'bid', 'price': price, 'volume': volume})
        for prev_ask in prev_asks[:10]:
            price, volume = float(prev_ask[0]), float(prev_ask[1])
            if volume > volume_threshold and price not in curr_asks_prices:
                disappeared.append({'side': 'ask', 'price': price, 'volume': volume})
        return disappeared

    async def _detect_absorption(self, snapshots: List[OrderBookSnapshot]) -> Optional[Dict]:
        """Детекция абсорбции - поглощение крупных ордеров"""
        try:
            if len(snapshots) < 3: return None
            volume_changes = []
            for i in range(1, len(snapshots)):
                prev, curr = snapshots[i-1], snapshots[i]
                bid_change = float(curr.bid_volume) - float(prev.bid_volume)
                ask_change = float(curr.ask_volume) - float(prev.ask_volume)
                volume_changes.append({'bid_change': bid_change, 'ask_change': ask_change, 'total_change': abs(bid_change) + abs(ask_change)})

            avg_change = np.mean([v['total_change'] for v in volume_changes])
            last_change = volume_changes[-1]
            if avg_change > 0 and last_change['total_change'] > avg_change * self.absorption_volume_ratio:
                if last_change['bid_change'] < 0 and abs(last_change['bid_change']) > abs(last_change['ask_change']):
                    signal_type = SignalTypeEnum.SELL
                elif last_change['ask_change'] < 0 and abs(last_change['ask_change']) > abs(last_change['bid_change']):
                    signal_type = SignalTypeEnum.BUY
                else:
                    return None
                strength = min(1.0, last_change['total_change'] / (avg_change * self.absorption_volume_ratio))
                return { 'symbol': snapshots[-1].symbol, 'signal_type': signal_type, 'strength': strength, 'strategy': 'order_book_absorption', 'metadata': { 'bid_volume_change': last_change['bid_change'], 'ask_volume_change': last_change['ask_change'], 'avg_volume_change': avg_change, 'absorption_ratio': last_change['total_change'] / avg_change } }
        except Exception as e:
            logger.error(f"Ошибка при детекции абсорбции: {e}")
        return None

    async def _detect_imbalance(self, snapshot: OrderBookSnapshot) -> Optional[Dict]:
        """Детекция дисбаланса bid/ask"""
        try:
            if snapshot.bid_volume is None or snapshot.ask_volume is None: return None
            bid_volume_float = float(snapshot.bid_volume)
            ask_volume_float = float(snapshot.ask_volume)
            if ask_volume_float == 0: return None
            bid_ask_ratio = bid_volume_float / ask_volume_float

            if bid_ask_ratio > self.imbalance_threshold:
                signal_type = SignalTypeEnum.BUY
                strength = min(1.0, (bid_ask_ratio - 1) / (self.imbalance_threshold - 1))
            elif bid_ask_ratio < 1 / self.imbalance_threshold:
                signal_type = SignalTypeEnum.SELL
                strength = min(1.0, (1 - bid_ask_ratio) / (1 - 1/self.imbalance_threshold))
            else:
                return None
            return { 'symbol': snapshot.symbol, 'signal_type': signal_type, 'strength': strength, 'strategy': 'order_book_imbalance', 'metadata': { 'bid_volume': float(snapshot.bid_volume), 'ask_volume': float(snapshot.ask_volume), 'bid_ask_ratio': bid_ask_ratio, 'imbalance_threshold': self.imbalance_threshold } }
        except Exception as e:
            logger.error(f"Ошибка при детекции дисбаланса: {e}")
        return None

    async def _get_active_symbols(self, db_session) -> List[str]:
        """Получение списка активных символов"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            symbols = db_session.query(OrderBookSnapshot.symbol).filter(OrderBookSnapshot.timestamp > cutoff_time).distinct().all()
            return [symbol[0] for symbol in symbols]
        except Exception as e:
            logger.error(f"Ошибка при получении активных символов: {e}")
            return []

    async def _get_order_book_snapshots(self, db_session, symbol: str) -> List[OrderBookSnapshot]:
        """Получение снимков стакана"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=self.lookback_minutes)
            snapshots = db_session.query(OrderBookSnapshot).filter(and_(OrderBookSnapshot.symbol == symbol, OrderBookSnapshot.timestamp > cutoff_time)).order_by(OrderBookSnapshot.timestamp.asc()).limit(20).all()
            return list(snapshots)
        except Exception as e:
            logger.error(f"Ошибка при получении снимков стакана: {e}")
            return []

    async def _save_signal(self, db_session, signal: Dict):
        """Сохранение сигнала в БД"""
        try:
            action_map = { SignalTypeEnum.BUY: 'BUY', SignalTypeEnum.SELL: 'SELL', SignalTypeEnum.NEUTRAL: 'HOLD' }
            def convert_decimals(obj):
                if isinstance(obj, list): return [convert_decimals(i) for i in obj]
                if isinstance(obj, dict): return {k: convert_decimals(v) for k, v in obj.items()}
                if isinstance(obj, Decimal): return float(obj)
                return obj

            new_signal = Signal(
                symbol=signal['symbol'],
                strategy=signal['strategy'],
                action=action_map.get(signal['signal_type'], 'HOLD'),
                price=0.0, # Цена должна быть добавлена на более высоком уровне (в BotManager)
                confidence=signal['strength'],
                reason=f"OrderBook: {signal['strategy']}",
                indicators=convert_decimals(signal.get('metadata', {}))
            )
            db_session.add(new_signal)
            logger.debug(f"Подготовлен к сохранению сигнал {new_signal.action} для {new_signal.symbol} от стратегии {new_signal.strategy}")
        except Exception as e:
            logger.error(f"Ошибка при подготовке сигнала к сохранению: {e}")
            db_session.rollback()


"""
Стратегия анализа биржевого стакана для детекции манипуляций и генерации торговых сигналов
Файл: src/strategies/order_book_analysis.py
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import asyncio
import numpy as np
from decimal import Decimal
import json
from sqlalchemy import and_, desc

from ..core.database import SessionLocal
from ..core.signal_models import OrderBookSnapshot, SignalExtended, SignalType

logger = logging.getLogger(__name__)


class OrderBookAnalysisStrategy:
    """Стратегия анализа биржевого стакана для выявления манипуляций"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.name = "order_book_analysis"
        self.is_running = False
        
        # Параметры стратегии
        self.wall_threshold = self.config.get('wall_threshold', 5.0)  # % от общего объема для определения стены
        self.spoofing_time_window = self.config.get('spoofing_time_window', 300)  # секунд
        self.absorption_volume_ratio = self.config.get('absorption_volume_ratio', 3.0)  # соотношение объемов
        self.imbalance_threshold = self.config.get('imbalance_threshold', 2.0)  # порог дисбаланса bid/ask
        self.lookback_minutes = self.config.get('lookback_minutes', 30)
        
        logger.info(f"Стратегия {self.name} инициализирована")
    
    async def start(self):
        """Запуск стратегии"""
        logger.info(f"Запуск стратегии {self.name}")
        self.is_running = True
        
        try:
            while self.is_running:
                await self.run()
                await asyncio.sleep(60)  # Анализ каждую минуту
        except Exception as e:
            logger.error(f"Ошибка в основном цикле стратегии: {e}")
        finally:
            self.is_running = False
    
    async def stop(self):
        """Остановка стратегии"""
        logger.info(f"Остановка стратегии {self.name}")
        self.is_running = False
    
    async def run(self):
        """Основной цикл анализа"""
        logger.info("OrderBookAnalysisStrategy: Запуск цикла анализа биржевого стакана")
        
        with SessionLocal() as db:
            try:
                # Получаем список активных символов
                symbols = await self._get_active_symbols(db)
                
                # Анализируем каждый символ
                for symbol in symbols:
                    await self.analyze_symbol(db, symbol)
                
            except Exception as e:
                logger.error(f"OrderBookAnalysisStrategy: Ошибка в основном цикле: {e}")
    
    async def analyze_symbol(self, db_session, symbol: str):
        """Анализ конкретного символа"""
        try:
            # Получаем последние снимки стакана
            snapshots = await self._get_order_book_snapshots(db_session, symbol)
            
            if len(snapshots) < 2:
                return
            
            # Детекция различных паттернов
            signals = []
            
            # 1. Поиск стен (buy/sell walls)
            wall_signal = await self._detect_walls(symbol, snapshots[-1])
            if wall_signal:
                signals.append(wall_signal)
            
            # 2. Детекция спуфинга
            spoofing_signal = await self._detect_spoofing(symbol, snapshots)
            if spoofing_signal:
                signals.append(spoofing_signal)
            
            # 3. Анализ поглощения (absorption)
            absorption_signal = await self._detect_absorption(symbol, snapshots)
            if absorption_signal:
                signals.append(absorption_signal)
            
            # 4. Дисбаланс bid/ask
            imbalance_signal = await self._detect_imbalance(symbol, snapshots[-1])
            if imbalance_signal:
                signals.append(imbalance_signal)
            
            # Сохраняем сигналы
            for signal in signals:
                await self._save_signal(db_session, signal)
            
            if signals:
                db_session.commit()
            
        except Exception as e:
            logger.error(f"OrderBookAnalysisStrategy: Ошибка при анализе {symbol}: {e}")
            db_session.rollback()
    
    async def _detect_walls(self, symbol: str, snapshot: OrderBookSnapshot) -> Optional[Dict]:
        """Детекция стен в стакане"""
        try:
            # Парсим JSON данные стакана
            snapshot_data = json.loads(snapshot.snapshot_data) if isinstance(snapshot.snapshot_data, str) else snapshot.snapshot_data
            bids = snapshot_data.get('bids', [])
            asks = snapshot_data.get('asks', [])
            
            # Считаем общие объемы
            total_bid_volume = snapshot.bid_volume
            total_ask_volume = snapshot.ask_volume
            
            # Ищем стены среди bids
            for bid in bids[:5]:  # Проверяем первые 5 уровней
                bid_volume = float(bid.get('quantity', 0))
                if total_bid_volume > 0 and (bid_volume / total_bid_volume * 100) > self.wall_threshold:
                    return {
                        'symbol': symbol,
                        'signal_type': SignalType.SELL,  # Стена покупок = сопротивление
                        'strength': min(1.0, bid_volume / total_bid_volume),
                        'strategy': 'order_book_walls',
                        'metadata': {
                            'wall_type': 'bid_wall',
                            'wall_price': float(bid.get('price', 0)),
                            'wall_volume': bid_volume,
                            'wall_percentage': bid_volume / total_bid_volume * 100
                        }
                    }
            
            # Ищем стены среди asks
            for ask in asks[:5]:
                ask_volume = float(ask.get('quantity', 0))
                if total_ask_volume > 0 and (ask_volume / total_ask_volume * 100) > self.wall_threshold:
                    return {
                        'symbol': symbol,
                        'signal_type': SignalType.BUY,  # Стена продаж = поддержка
                        'strength': min(1.0, ask_volume / total_ask_volume),
                        'strategy': 'order_book_walls',
                        'metadata': {
                            'wall_type': 'ask_wall',
                            'wall_price': float(ask.get('price', 0)),
                            'wall_volume': ask_volume,
                            'wall_percentage': ask_volume / total_ask_volume * 100
                        }
                    }
            
        except Exception as e:
            logger.error(f"Ошибка при детекции стен: {e}")
        
        return None
    
    async def _detect_spoofing(self, symbol: str, snapshots: List[OrderBookSnapshot]) -> Optional[Dict]:
        """Детекция спуфинга - исчезновение крупных ордеров"""
        if len(snapshots) < 2:
            return None
        
        try:
            prev_snapshot = snapshots[-2]
            curr_snapshot = snapshots[-1]
            
            # Парсим данные
            prev_data = json.loads(prev_snapshot.snapshot_data) if isinstance(prev_snapshot.snapshot_data, str) else prev_snapshot.snapshot_data
            curr_data = json.loads(curr_snapshot.snapshot_data) if isinstance(curr_snapshot.snapshot_data, str) else curr_snapshot.snapshot_data
            
            # Находим исчезнувшие крупные ордера
            disappeared = self._find_disappeared_orders(prev_data, curr_data)
            
            if disappeared:
                # Спуфинг обнаружен
                total_disappeared_volume = sum(order['volume'] for order in disappeared)
                
                # Определяем направление сигнала
                bid_disappeared = sum(order['volume'] for order in disappeared if order['side'] == 'bid')
                ask_disappeared = sum(order['volume'] for order in disappeared if order['side'] == 'ask')
                
                if bid_disappeared > ask_disappeared:
                    # Исчезли bid'ы - возможно манипуляция для снижения цены
                    signal_type = SignalType.SELL
                else:
                    # Исчезли ask'и - возможно манипуляция для повышения цены
                    signal_type = SignalType.BUY
                
                return {
                    'symbol': symbol,
                    'signal_type': signal_type,
                    'strength': min(1.0, total_disappeared_volume / (prev_snapshot.bid_volume + prev_snapshot.ask_volume)),
                    'strategy': 'order_book_spoofing',
                    'metadata': {
                        'disappeared_orders': len(disappeared),
                        'disappeared_volume': total_disappeared_volume,
                        'bid_disappeared': bid_disappeared,
                        'ask_disappeared': ask_disappeared,
                        'time_diff_seconds': (curr_snapshot.timestamp - prev_snapshot.timestamp).total_seconds()
                    }
                }
            
        except Exception as e:
            logger.error(f"Ошибка при детекции спуфинга: {e}")
        
        return None
    
    def _find_disappeared_orders(self, prev: Dict, curr: Dict) -> List[Dict]:
        """Поиск исчезнувших крупных ордеров"""
        disappeared = []
        
        # Порог для определения "крупного" ордера (1% от общего объема)
        prev_total_volume = sum(float(bid.get('quantity', 0)) for bid in prev.get('bids', [])) + \
                           sum(float(ask.get('quantity', 0)) for ask in prev.get('asks', []))
        volume_threshold = prev_total_volume * 0.01
        
        # Проверяем bids
        for prev_bid in prev.get('bids', [])[:10]:
            if float(prev_bid.get('quantity', 0)) > volume_threshold:
                found = False
                for curr_bid in curr.get('bids', [])[:10]:
                    if abs(float(curr_bid.get('price', 0)) - float(prev_bid.get('price', 0))) < 0.0001:
                        if float(curr_bid.get('quantity', 0)) >= float(prev_bid.get('quantity', 0)) * 0.8:
                            found = True
                            break
                
                if not found:
                    disappeared.append({
                        'side': 'bid',
                        'price': float(prev_bid.get('price', 0)),
                        'volume': float(prev_bid.get('quantity', 0))
                    })
        
        # Проверяем asks
        for prev_ask in prev.get('asks', [])[:10]:
            if float(prev_ask.get('quantity', 0)) > volume_threshold:
                found = False
                for curr_ask in curr.get('asks', [])[:10]:
                    if abs(float(curr_ask.get('price', 0)) - float(prev_ask.get('price', 0))) < 0.0001:
                        if float(curr_ask.get('quantity', 0)) >= float(prev_ask.get('quantity', 0)) * 0.8:
                            found = True
                            break
                
                if not found:
                    disappeared.append({
                        'side': 'ask',
                        'price': float(prev_ask.get('price', 0)),
                        'volume': float(prev_ask.get('quantity', 0))
                    })
        
        return disappeared
    
    async def _detect_absorption(self, symbol: str, snapshots: List[OrderBookSnapshot]) -> Optional[Dict]:
        """Детекция поглощения ликвидности"""
        if len(snapshots) < 2:
            return None
        
        try:
            prev = snapshots[-2]
            curr = snapshots[-1]
            
            # Считаем изменения объемов
            bid_change_ratio = curr.bid_volume / prev.bid_volume if prev.bid_volume > 0 else 1
            ask_change_ratio = curr.ask_volume / prev.ask_volume if prev.ask_volume > 0 else 1
            
            # Проверяем поглощение
            if ask_change_ratio < 0.5 and bid_change_ratio > 0.9:
                # Активное поглощение asks (покупка)
                return {
                    'symbol': symbol,
                    'signal_type': SignalType.BUY,
                    'strength': min(1.0, (1 - ask_change_ratio) * 1.5),
                    'strategy': 'order_book_absorption',
                    'metadata': {
                        'absorption_type': 'ask_absorption',
                        'ask_volume_change': ask_change_ratio,
                        'bid_volume_change': bid_change_ratio,
                        'absorbed_volume': prev.ask_volume - curr.ask_volume
                    }
                }
            elif bid_change_ratio < 0.5 and ask_change_ratio > 0.9:
                # Активное поглощение bids (продажа)
                return {
                    'symbol': symbol,
                    'signal_type': SignalType.SELL,
                    'strength': min(1.0, (1 - bid_change_ratio) * 1.5),
                    'strategy': 'order_book_absorption',
                    'metadata': {
                        'absorption_type': 'bid_absorption',
                        'ask_volume_change': ask_change_ratio,
                        'bid_volume_change': bid_change_ratio,
                        'absorbed_volume': prev.bid_volume - curr.bid_volume
                    }
                }
            
        except Exception as e:
            logger.error(f"Ошибка при детекции поглощения: {e}")
        
        return None
    
    async def _detect_imbalance(self, symbol: str, snapshot: OrderBookSnapshot) -> Optional[Dict]:
        """Детекция дисбаланса bid/ask"""
        try:
            if snapshot.ask_volume == 0:
                return None
            
            imbalance_ratio = snapshot.bid_volume / snapshot.ask_volume
            
            # Проверяем дисбаланс
            if imbalance_ratio > self.imbalance_threshold:
                # Больше покупателей
                return {
                    'symbol': symbol,
                    'signal_type': SignalType.BUY,
                    'strength': min(1.0, (imbalance_ratio - 1) / self.imbalance_threshold),
                    'strategy': 'order_book_imbalance',
                    'metadata': {
                        'imbalance_ratio': imbalance_ratio,
                        'bid_volume': snapshot.bid_volume,
                        'ask_volume': snapshot.ask_volume,
                        'order_flow_imbalance': snapshot.order_flow_imbalance
                    }
                }
            elif imbalance_ratio < (1 / self.imbalance_threshold):
                # Больше продавцов
                return {
                    'symbol': symbol,
                    'signal_type': SignalType.SELL,
                    'strength': min(1.0, (1 / imbalance_ratio - 1) / self.imbalance_threshold),
                    'strategy': 'order_book_imbalance',
                    'metadata': {
                        'imbalance_ratio': imbalance_ratio,
                        'bid_volume': snapshot.bid_volume,
                        'ask_volume': snapshot.ask_volume,
                        'order_flow_imbalance': snapshot.order_flow_imbalance
                    }
                }
            
        except Exception as e:
            logger.error(f"Ошибка при детекции дисбаланса: {e}")
        
        return None
    
    async def _get_active_symbols(self, db_session) -> List[str]:
        """Получение списка активных символов"""
        try:
            # Получаем уникальные символы за последний час
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            symbols = db_session.query(OrderBookSnapshot.symbol).filter(
                OrderBookSnapshot.timestamp > cutoff_time
            ).distinct().all()
            
            return [symbol[0] for symbol in symbols]
        
        except Exception as e:
            logger.error(f"Ошибка при получении активных символов: {e}")
            return []
    
    async def _get_order_book_snapshots(self, db_session, symbol: str) -> List[OrderBookSnapshot]:
        """Получение снимков стакана"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=self.lookback_minutes)
            
            snapshots = db_session.query(OrderBookSnapshot).filter(
                and_(
                    OrderBookSnapshot.symbol == symbol,
                    OrderBookSnapshot.timestamp > cutoff_time
                )
            ).order_by(OrderBookSnapshot.timestamp.asc()).limit(20).all()
            
            return list(snapshots)
        
        except Exception as e:
            logger.error(f"Ошибка при получении снимков стакана: {e}")
            return []
    
    async def _save_signal(self, db_session, signal: Dict):
        """Сохранение сигнала в БД"""
        try:
            new_signal = SignalExtended(
                symbol=signal['symbol'],
                signal_type=signal['signal_type'],
                strength=signal['strength'],
                strategy=signal['strategy'],
                metadata=json.dumps(signal['metadata']),
                created_at=datetime.utcnow()
            )
            
            db_session.add(new_signal)
            
            logger.info(
                f"OrderBookAnalysisStrategy: Сохранен сигнал {signal['signal_type'].value} "
                f"для {signal['symbol']} от стратегии {signal['strategy']}"
            )
        
        except Exception as e:
            logger.error(f"Ошибка при сохранении сигнала: {e}")

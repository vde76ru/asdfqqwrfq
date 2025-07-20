"""
Стратегия анализа биржевого стакана для детекции манипуляций и генерации торговых сигналов
Файл: src/strategies/order_book_analysis.py
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import asyncio
import numpy as np
from decimal import Decimal
import json
from sqlalchemy import and_, desc

# ИСПРАВЛЕНО: Правильные импорты из core.models
from ..core.database import SessionLocal
from ..core.models import (
    OrderBookSnapshot, 
    Signal,  # Вместо SignalExtended
    SignalTypeEnum  # Правильное имя enum вместо SignalType
    
)

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
        try:
            db_session = SessionLocal()
            try:
                # Получаем список активных символов
                symbols = await self._get_active_symbols(db_session)
                
                for symbol in symbols:
                    # Анализируем каждый символ
                    await self._analyze_symbol(db_session, symbol)
                
                # Коммитим изменения
                db_session.commit()
                
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                db_session.rollback()
            finally:
                db_session.close()
                
        except Exception as e:
            logger.error(f"Критическая ошибка стратегии: {e}")
    
    async def analyze_symbol(self, symbol: str, exchange_client=None) -> List[Dict[str, Any]]:
        """
        Анализ символа для поиска торговых сигналов
        
        Args:
            symbol: Торговая пара для анализа
            exchange_client: Клиент биржи для получения данных
            
        Returns:
            List[Dict]: Список найденных сигналов
        """
        try:
            signals = []
            
            # Получаем стакан ордеров
            if not exchange_client:
                logger.warning(f"⚠️ Нет exchange_client для анализа {symbol}")
                return signals
            
            # Получаем стакан заявок
            orderbook = await self._get_orderbook_safely(symbol, exchange_client)
            if not orderbook:
                return signals
            
            # Анализируем стакан
            analysis = await self._analyze_orderbook(symbol, orderbook)
            if not analysis:
                return signals
            
            # Создаем сигналы на основе анализа
            if analysis.get('signal_strength', 0) > self.min_signal_strength:
                signal = {
                    'symbol': symbol,
                    'strategy': self.name,
                    'action': analysis.get('recommended_action', 'hold'),
                    'strength': analysis.get('signal_strength', 0),
                    'confidence': analysis.get('confidence', 0),
                    'timestamp': datetime.utcnow(),
                    'analysis': analysis,
                    'type': 'orderbook_signal'
                }
                
                signals.append(signal)
                logger.debug(f"📊 {symbol}: {signal['action']} сигнал (сила: {signal['strength']:.2f})")
            
            return signals
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа {symbol}: {e}")
            return []
            
    async def _get_orderbook_safely(self, symbol: str, exchange_client) -> Optional[Dict]:
        """
        Безопасное получение стакана ордеров
        
        Args:
            symbol: Торговая пара
            exchange_client: Клиент биржи
            
        Returns:
            Dict: Данные стакана или None
        """
        try:
            # Проверяем различные методы получения стакана
            if hasattr(exchange_client, 'get_order_book'):
                return await exchange_client.get_order_book(symbol, limit=50)
            elif hasattr(exchange_client, 'get_orderbook'):
                return await exchange_client.get_orderbook(symbol, limit=50)
            elif hasattr(exchange_client, 'fetch_order_book'):
                return await exchange_client.fetch_order_book(symbol, limit=50)
            else:
                logger.warning(f"⚠️ Нет метода для получения стакана для {symbol}")
                return None
                
        except Exception as e:
            logger.debug(f"⚠️ Не удалось получить стакан для {symbol}: {e}")
            return None
    
    async def _analyze_orderbook(self, symbol: str, orderbook: Dict) -> Optional[Dict]:
        """
        Анализ стакана ордеров
        
        Args:
            symbol: Торговая пара
            orderbook: Данные стакана
            
        Returns:
            Dict: Результаты анализа
        """
        try:
            if not orderbook or 'bids' not in orderbook or 'asks' not in orderbook:
                return None
            
            bids = orderbook['bids'][:20]  # Топ 20 заявок на покупку
            asks = orderbook['asks'][:20]  # Топ 20 заявок на продажу
            
            if not bids or not asks:
                return None
            
            # Базовые метрики
            best_bid = float(bids[0][0]) if bids else 0
            best_ask = float(asks[0][0]) if asks else 0
            spread = best_ask - best_bid if best_bid and best_ask else 0
            spread_pct = (spread / best_ask * 100) if best_ask else 0
            
            # Анализ объемов
            bid_volume = sum(float(bid[1]) for bid in bids[:5])  # Топ 5 уровней
            ask_volume = sum(float(ask[1]) for ask in asks[:5])
            
            volume_imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0
            
            # Определяем силу сигнала
            signal_strength = 0
            recommended_action = 'hold'
            confidence = 0
            
            # Логика определения сигналов
            if volume_imbalance > 0.3 and spread_pct < 0.1:  # Много покупателей, узкий спред
                signal_strength = min(volume_imbalance * 2, 1.0)
                recommended_action = 'buy'
                confidence = signal_strength * 0.8
            elif volume_imbalance < -0.3 and spread_pct < 0.1:  # Много продавцов, узкий спред
                signal_strength = min(abs(volume_imbalance) * 2, 1.0)
                recommended_action = 'sell'
                confidence = signal_strength * 0.8
            
            return {
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread': spread,
                'spread_pct': spread_pct,
                'bid_volume': bid_volume,
                'ask_volume': ask_volume,
                'volume_imbalance': volume_imbalance,
                'signal_strength': signal_strength,
                'recommended_action': recommended_action,
                'confidence': confidence,
                'analysis_time': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа стакана для {symbol}: {e}")
            return None
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """
        Получение информации о стратегии
        
        Returns:
            Dict: Информация о стратегии
        """
        return {
            'name': self.name,
            'type': 'orderbook_analysis',
            'min_signal_strength': getattr(self, 'min_signal_strength', 0.5),
            'description': 'Анализ стакана ордеров для поиска торговых возможностей',
            'parameters': {
                'orderbook_depth': 20,
                'volume_levels': 5,
                'min_confidence': 0.6
            }
        }

    
    async def _detect_walls(self, snapshot: OrderBookSnapshot) -> Optional[Dict]:
        """Детекция стен в стакане"""
        try:
            # ✅ ИСПРАВЛЕНО: Данные в полях bids и asks, а не в order_book_data
            bids = json.loads(snapshot.bids) if snapshot.bids else []
            asks = json.loads(snapshot.asks) if snapshot.asks else []
    
            # ✅ ИСПРАВЛЕНО: Приводим все к float для вычислений
            total_bid_volume = sum(float(bid[1]) for bid in bids)
            total_ask_volume = sum(float(ask[1]) for ask in asks)
            total_volume = total_bid_volume + total_ask_volume
            
            if total_volume == 0:
                return None
            
            # Ищем крупные ордера (стены)
            for i, bid in enumerate(bids[:10]):
                bid_size = float(bid[1])
                if (bid_size / total_volume) * 100 > self.wall_threshold:
                    return {
                        'symbol': snapshot.symbol,
                        'signal_type': SignalTypeEnum.SELL,
                        'strength': min(1.0, bid_size / total_volume),
                        'strategy': 'order_book_walls',
                        'metadata': {
                            'wall_type': 'bid',
                            'wall_price': float(bid[0]),
                            'wall_size': bid_size,
                            'wall_percentage': (bid_size / total_volume) * 100,
                            'level': i + 1
                        }
                    }
            
            for i, ask in enumerate(asks[:10]):
                ask_size = float(ask[1])
                if (ask_size / total_volume) * 100 > self.wall_threshold:
                    return {
                        'symbol': snapshot.symbol,
                        'signal_type': SignalTypeEnum.BUY,
                        'strength': min(1.0, ask_size / total_volume),
                        'strategy': 'order_book_walls',
                        'metadata': {
                            'wall_type': 'ask',
                            'wall_price': float(ask[0]),
                            'wall_size': ask_size,
                            'wall_percentage': (ask_size / total_volume) * 100,
                            'level': i + 1
                        }
                    }
        except Exception as e:
            logger.error(f"Ошибка при детекции стен: {e}")
        
        return None

    
    async def _detect_spoofing(self, snapshots: List[OrderBookSnapshot]) -> Optional[Dict]:
        """Детекция спуфинга - появление и исчезновение крупных ордеров"""
        try:
            if len(snapshots) < 2:
                return None
            
            # Сравниваем последние два снимка
            prev_snapshot = snapshots[-2]
            curr_snapshot = snapshots[-1]
            
            # Проверяем временную разницу
            time_diff = (curr_snapshot.timestamp - prev_snapshot.timestamp).total_seconds()
            if time_diff > self.spoofing_time_window:
                return None
            
            prev_orders = {'bids': json.loads(prev_snapshot.bids), 'asks': json.loads(prev_snapshot.asks)}
            curr_orders = {'bids': json.loads(curr_snapshot.bids), 'asks': json.loads(curr_snapshot.asks)}
            
            # Ищем исчезнувшие крупные ордера
            disappeared_orders = self._find_disappeared_orders(prev_orders, curr_orders)
            
            if disappeared_orders:
                total_disappeared_volume = sum(order['volume'] for order in disappeared_orders)
                
                # Если исчез большой объем - это может быть спуфинг
                bid_disappeared = sum(order['volume'] for order in disappeared_orders if order['side'] == 'bid')
                ask_disappeared = sum(order['volume'] for order in disappeared_orders if order['side'] == 'ask')
                
                # Определяем направление сигнала
                if bid_disappeared > ask_disappeared:
                    signal_type = SignalTypeEnum.SELL  # Исчезли покупки - цена может пойти вниз
                else:
                    signal_type = SignalTypeEnum.BUY
                
                return {
                    'symbol': curr_snapshot.symbol,
                    'signal_type': signal_type,
                    'strength': min(1.0, total_disappeared_volume / (float(prev_snapshot.bid_volume) + float(prev_snapshot.ask_volume))),
                    'strategy': 'order_book_spoofing',
                    'metadata': {
                        'disappeared_orders': len(disappeared_orders),
                        'disappeared_volume': total_disappeared_volume,
                        'bid_disappeared': bid_disappeared,
                        'ask_disappeared': ask_disappeared,
                        'time_diff_seconds': time_diff
                    }
                }
            
        except Exception as e:
            logger.error(f"Ошибка при детекции спуфинга: {e}")
        
        return None
    
    def _find_disappeared_orders(self, prev: Dict, curr: Dict) -> List[Dict]:
        """Поиск исчезнувших крупных ордеров, работая со списками."""
        disappeared = []
        
        prev_bids = prev.get('bids', [])
        prev_asks = prev.get('asks', [])
        curr_bids_prices = {float(b[0]) for b in curr.get('bids', [])}
        curr_asks_prices = {float(a[0]) for a in curr.get('asks', [])}

        prev_total_volume = sum(float(b[1]) for b in prev_bids) + sum(float(a[1]) for a in prev_asks)
        if prev_total_volume == 0:
            return []
            
        volume_threshold = prev_total_volume * 0.01

        # Проверяем bids
        for prev_bid in prev_bids[:10]:
            price, volume = float(prev_bid[0]), float(prev_bid[1])
            if volume > volume_threshold and price not in curr_bids_prices:
                disappeared.append({'side': 'bid', 'price': price, 'volume': volume})

        # Проверяем asks
        for prev_ask in prev_asks[:10]:
            price, volume = float(prev_ask[0]), float(prev_ask[1])
            if volume > volume_threshold and price not in curr_asks_prices:
                disappeared.append({'side': 'ask', 'price': price, 'volume': volume})
                
        return disappeared

    
    async def _detect_absorption(self, snapshots: List[OrderBookSnapshot]) -> Optional[Dict]:
        """Детекция абсорбции - поглощение крупных ордеров"""
        try:
            if len(snapshots) < 3:
                return None
            
            # Анализируем изменение объемов
            volume_changes = []
            for i in range(1, len(snapshots)):
                prev = snapshots[i-1]
                curr = snapshots[i]
                
                bid_change = float(curr.bid_volume) - float(prev.bid_volume)
                ask_change = float(curr.ask_volume) - float(prev.ask_volume)
                
                volume_changes.append({
                    'bid_change': bid_change,
                    'ask_change': ask_change,
                    'total_change': abs(bid_change) + abs(ask_change)
                })
            
            # Ищем резкие изменения объемов
            avg_change = np.mean([v['total_change'] for v in volume_changes])
            
            last_change = volume_changes[-1]
            if last_change['total_change'] > avg_change * self.absorption_volume_ratio:
                # Определяем направление
                if last_change['bid_change'] < 0 and abs(last_change['bid_change']) > abs(last_change['ask_change']):
                    # Поглощение покупок - сигнал к продаже
                    signal_type = SignalTypeEnum.SELL
                elif last_change['ask_change'] < 0 and abs(last_change['ask_change']) > abs(last_change['bid_change']):
                    # Поглощение продаж - сигнал к покупке
                    signal_type = SignalTypeEnum.BUY
                else:
                    return None
                
                return {
                    'symbol': snapshots[-1].symbol,
                    'signal_type': signal_type,
                    'strength': min(1.0, last_change['total_change'] / (avg_change * self.absorption_volume_ratio)),
                    'strategy': 'order_book_absorption',
                    'metadata': {
                        'bid_volume_change': last_change['bid_change'],
                        'ask_volume_change': last_change['ask_change'],
                        'avg_volume_change': avg_change,
                        'absorption_ratio': last_change['total_change'] / avg_change if avg_change > 0 else 0
                    }
                }
        
        except Exception as e:
            logger.error(f"Ошибка при детекции абсорбции: {e}")
        
        return None
    
    async def _detect_imbalance(self, snapshot: OrderBookSnapshot) -> Optional[Dict]:
        """Детекция дисбаланса bid/ask"""
        try:
            if snapshot.bid_volume == 0 or snapshot.ask_volume == 0:
                return None

            # Рассчитываем соотношение
            bid_volume_float = float(snapshot.bid_volume)
            ask_volume_float = float(snapshot.ask_volume)
            if ask_volume_float == 0:
                return None # Избегаем деления на ноль
            bid_ask_ratio = bid_volume_float / ask_volume_float
            
            # Проверяем на дисбаланс
            if bid_ask_ratio > self.imbalance_threshold:
                # Больше покупателей - сигнал к покупке
                signal_type = SignalTypeEnum.BUY
                strength = min(1.0, (bid_ask_ratio - 1) / (self.imbalance_threshold - 1))
            elif bid_ask_ratio < 1 / self.imbalance_threshold:
                # Больше продавцов - сигнал к продаже
                signal_type = SignalTypeEnum.SELL
                strength = min(1.0, (1 - bid_ask_ratio) / (1 - 1/self.imbalance_threshold))
            else:
                return None
            
            return {
                'symbol': snapshot.symbol,
                'signal_type': signal_type,
                'strength': strength,
                'strategy': 'order_book_imbalance',
                'metadata': {
                    'bid_volume': snapshot.bid_volume,
                    'ask_volume': snapshot.ask_volume,
                    'bid_ask_ratio': bid_ask_ratio,
                    'imbalance_threshold': self.imbalance_threshold
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
            

    async def analyze(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Метод-обертка для совместимости с единым интерфейсом стратегий
        
        Args:
            symbol: Торговый символ для анализа
            
        Returns:
            Сигнал для указанного символа или None
        """
        try:
            # Создаем сессию БД для анализа
            with SessionLocal() as db_session:
                # Вызываем основной метод анализа
                await self.analyze_symbol(db_session, symbol)
                
                # Получаем последний сигнал для символа
                recent_signal = db_session.query(Signal).filter(
                    Signal.symbol == symbol,
                    Signal.strategy == self.name,
                    Signal.created_at >= datetime.utcnow() - timedelta(minutes=5)
                ).order_by(Signal.created_at.desc()).first()
                
                if recent_signal:
                    # Преобразуем в формат, ожидаемый BotManager
                    return {
                        'action': recent_signal.action,  # BUY, SELL, HOLD
                        'confidence': recent_signal.confidence,
                        'price_target': None,
                        'reason': recent_signal.reason
                    }
                
                # Если свежих сигналов нет, возвращаем нейтральный
                return {
                    'action': 'HOLD',
                    'confidence': 0.5,
                    'price_target': None,
                    'reason': 'No order book patterns detected'
                }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа {symbol} в OrderBookAnalysisStrategy: {e}")
            return None
    
    async def _save_signal(self, db_session, signal: Dict):
        """Сохранение сигнала в БД"""
        try:
            # Преобразуем SignalTypeEnum в action для модели Signal
            action_map = {
                SignalTypeEnum.BUY: 'BUY',
                SignalTypeEnum.SELL: 'SELL',
                SignalTypeEnum.NEUTRAL: 'HOLD'
            }
            
            def convert_decimals(obj):
                if isinstance(obj, list):
                    return [convert_decimals(i) for i in obj]
                if isinstance(obj, dict):
                    return {k: convert_decimals(v) for k, v in obj.items()}
                if isinstance(obj, Decimal):
                    return float(obj)
                return obj
    
            new_signal = Signal(
                symbol=signal['symbol'],
                strategy=signal['strategy'],
                action=action_map.get(signal['signal_type'], 'HOLD'),
                price=0.0,
                confidence=signal['strength'],
                reason=f"OrderBook: {signal['strategy']}",
                indicators=convert_decimals(signal['metadata'])
                # Поле created_at и timestamp заполнится автоматически
            )
            
            db_session.add(new_signal)
            
            logger.info(
                f"OrderBookAnalysisStrategy: Сохранен сигнал {signal['signal_type'].value} "
                f"для {signal['symbol']} от стратегии {signal['strategy']}"
            )
        
        except Exception as e:
            logger.error(f"Ошибка при сохранении сигнала: {e}")
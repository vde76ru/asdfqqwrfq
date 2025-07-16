#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Стратегия "Спящие гиганты" (Sleeping Giants).
Логика: Обнаружение активов с низкой волатильностью, в которые 
начинают "вливаться" аномальные объемы.

Файл: src/strategies/sleeping_giants.py
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import asyncio
from sqlalchemy import desc, and_
import json

# Импорт из core
from ..core.unified_config import config
from ..core.database import SessionLocal
from ..core.enums import SignalType
from ..db.models import Signal, VolumeAnomaly, OrderBookSnapshot, Price

# Импорт базовой стратегии
from .base_strategy import BaseStrategy

# Настройка логирования
logger = logging.getLogger(__name__)


@dataclass
class SleepingGiantSignal:
    """Структура сигнала от стратегии Sleeping Giants."""
    symbol: str
    signal_type: str  # 'buy', 'sell', 'neutral'
    confidence: float  # 0.0 - 1.0
    price: float
    volume_anomaly_score: float
    hurst_exponent: float
    vwap_deviation: float
    ofi_score: float
    volatility: float
    reason: str
    details: Dict[str, Any]
    timestamp: datetime


class HurstCalculator:
    """Калькулятор показателя Хёрста для определения характера временного ряда."""
    
    @staticmethod
    def calculate_hurst(time_series: np.ndarray, min_lag: int = 2, max_lag: int = 100) -> float:
        """
        Рассчитывает показатель Хёрста.
        
        H < 0.5: Антиперсистентный ряд (возврат к среднему)
        H = 0.5: Случайное блуждание
        H > 0.5: Персистентный ряд (трендовый)
        
        Args:
            time_series: Временной ряд цен
            min_lag: Минимальный лаг
            max_lag: Максимальный лаг
            
        Returns:
            float: Показатель Хёрста
        """
        if len(time_series) < max_lag * 2:
            max_lag = len(time_series) // 2
            
        if max_lag <= min_lag:
            return 0.5
            
        lags = range(min_lag, max_lag)
        tau = []
        
        for lag in lags:
            try:
                tau.append(np.sqrt(np.std(np.subtract(time_series[lag:], time_series[:-lag]))))
            except:
                continue
                
        if not tau:
            return 0.5
            
        # Линейная регрессия log(tau) от log(lag)
        try:
            poly = np.polyfit(np.log(list(lags)[:len(tau)]), np.log(tau), 1)
            return poly[0] * 2.0
        except:
            return 0.5


class SleepingGiantsStrategy(BaseStrategy):
    """
    Основной класс стратегии "Спящие гиганты".
    Ищет активы с низкой волатильностью и аномальными всплесками объема.
    """
    
    def __init__(self, 
                 volatility_threshold: float = 0.02,
                 volume_anomaly_threshold: float = 0.7,
                 hurst_threshold: float = 0.45,
                 ofi_threshold: float = 0.3,
                 min_confidence: float = 0.6):
        """
        Инициализация стратегии.
        
        Args:
            volatility_threshold: Порог волатильности для определения "флэта"
            volume_anomaly_threshold: Минимальный score аномалии объема
            hurst_threshold: Порог показателя Хёрста (< 0.45 = флэт)
            ofi_threshold: Порог дисбаланса потока ордеров
            min_confidence: Минимальная уверенность для генерации сигнала
        """
        super().__init__()
        self.volatility_threshold = volatility_threshold
        self.volume_anomaly_threshold = volume_anomaly_threshold
        self.hurst_threshold = hurst_threshold
        self.ofi_threshold = ofi_threshold
        self.min_confidence = min_confidence
        self.hurst_calculator = HurstCalculator()
        
        logger.info("Sleeping Giants Strategy initialized with params:")
        logger.info(f"  Volatility threshold: {volatility_threshold}")
        logger.info(f"  Volume anomaly threshold: {volume_anomaly_threshold}")
        logger.info(f"  Hurst threshold: {hurst_threshold}")
        logger.info(f"  OFI threshold: {ofi_threshold}")
    
    async def analyze(self) -> List[SleepingGiantSignal]:
        """
        Анализ рынка на предмет "спящих гигантов".
        Метод запрашивает данные из БД и генерирует сигналы.
        
        Returns:
            List[SleepingGiantSignal]: Список сгенерированных сигналов
        """
        signals = []
        
        with SessionLocal() as db:
            try:
                # Получаем активы с аномальными объемами за последний час
                recent_time = datetime.utcnow() - timedelta(hours=1)
                
                anomalies = db.query(VolumeAnomaly).filter(
                    and_(
                        VolumeAnomaly.detected_at >= recent_time,
                        VolumeAnomaly.anomaly_score >= self.volume_anomaly_threshold,
                        VolumeAnomaly.is_anomaly == True
                    )
                ).all()
                
                logger.info(f"Found {len(anomalies)} volume anomalies to analyze")
                
                for anomaly in anomalies:
                    signal = await self._analyze_symbol(db, anomaly)
                    if signal:
                        signals.append(signal)
                        # Сохраняем сигнал в БД
                        self._save_signal(db, signal)
                
                db.commit()
                
            except Exception as e:
                logger.error(f"Error in Sleeping Giants analysis: {e}")
                db.rollback()
        
        return signals
    
    async def _analyze_symbol(self, db_session, anomaly: VolumeAnomaly) -> Optional[SleepingGiantSignal]:
        """
        Анализ конкретного символа с аномальным объемом.
        
        Args:
            db_session: Сессия БД
            anomaly: Запись об аномалии объема
            
        Returns:
            Optional[SleepingGiantSignal]: Сигнал, если условия выполнены
        """
        try:
            symbol = anomaly.symbol
            
            # 1. Получаем последние снимки стакана
            recent_orderbooks = db_session.query(OrderBookSnapshot).filter(
                and_(
                    OrderBookSnapshot.symbol == symbol,
                    OrderBookSnapshot.timestamp >= datetime.utcnow() - timedelta(minutes=30)
                )
            ).order_by(desc(OrderBookSnapshot.timestamp)).limit(10).all()
            
            if not recent_orderbooks:
                logger.debug(f"No recent orderbook data for {symbol}")
                return None
            
            # 2. Анализируем дисбаланс в стакане
            latest_orderbook = recent_orderbooks[0]
            ofi_score = abs(latest_orderbook.order_flow_imbalance) if latest_orderbook.order_flow_imbalance else 0
            
            if ofi_score < self.ofi_threshold:
                logger.debug(f"OFI score {ofi_score} below threshold for {symbol}")
                return None
            
            # 3. Получаем историю цен для расчета волатильности и Хёрста
            price_history = db_session.query(Price).filter(
                and_(
                    Price.symbol == symbol,
                    Price.timestamp >= datetime.utcnow() - timedelta(hours=24)
                )
            ).order_by(Price.timestamp).all()
            
            if len(price_history) < 100:
                logger.debug(f"Insufficient price history for {symbol}")
                return None
            
            prices = np.array([p.close for p in price_history])
            
            # 4. Рассчитываем волатильность
            volatility = self._calculate_volatility(prices)
            
            if volatility > self.volatility_threshold:
                logger.debug(f"Volatility {volatility} above threshold for {symbol}")
                return None
            
            # 5. Рассчитываем показатель Хёрста
            hurst = self.hurst_calculator.calculate_hurst(prices)
            
            if hurst > self.hurst_threshold:
                logger.debug(f"Hurst {hurst} above threshold for {symbol}")
                return None
            
            # 6. Рассчитываем VWAP отклонение
            vwap = self._calculate_vwap(price_history)
            current_price = prices[-1]
            vwap_deviation = abs(current_price - vwap) / vwap if vwap > 0 else 0
            
            # 7. Определяем направление сигнала
            if latest_orderbook.order_flow_imbalance > 0:
                signal_type = 'buy'
                reason = f"Sleeping giant awakening: Low volatility ({volatility:.3f}), " \
                        f"high volume anomaly ({anomaly.anomaly_score:.2f}), " \
                        f"positive OFI ({ofi_score:.3f})"
            else:
                signal_type = 'sell'
                reason = f"Sleeping giant breakdown: Low volatility ({volatility:.3f}), " \
                        f"high volume anomaly ({anomaly.anomaly_score:.2f}), " \
                        f"negative OFI ({ofi_score:.3f})"
            
            # 8. Рассчитываем уверенность
            confidence = self._calculate_confidence(
                anomaly.anomaly_score,
                ofi_score,
                volatility,
                hurst,
                vwap_deviation
            )
            
            if confidence < self.min_confidence:
                logger.debug(f"Confidence {confidence} below threshold for {symbol}")
                return None
            
            # 9. Создаем сигнал
            signal = SleepingGiantSignal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                volume_anomaly_score=anomaly.anomaly_score,
                hurst_exponent=hurst,
                vwap_deviation=vwap_deviation,
                ofi_score=ofi_score,
                volatility=volatility,
                reason=reason,
                details={
                    'volume_24h': anomaly.volume_24h,
                    'volume_ratio_7d': anomaly.volume_ratio_7d,
                    'volume_ratio_30d': anomaly.volume_ratio_30d,
                    'bid_volume': latest_orderbook.bid_volume,
                    'ask_volume': latest_orderbook.ask_volume,
                    'bid_ask_ratio': latest_orderbook.bid_ask_ratio,
                    'large_orders': latest_orderbook.large_orders_detected
                },
                timestamp=datetime.utcnow()
            )
            
            logger.info(f"Generated Sleeping Giant signal for {symbol}: {signal_type} "
                       f"with confidence {confidence:.3f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error analyzing symbol {anomaly.symbol}: {e}")
            return None
    
    def _calculate_volatility(self, prices: np.ndarray, window: int = 24) -> float:
        """
        Рассчитывает волатильность цен.
        
        Args:
            prices: Массив цен
            window: Окно для расчета
            
        Returns:
            float: Волатильность
        """
        if len(prices) < window:
            return 1.0
        
        returns = np.diff(prices) / prices[:-1]
        return np.std(returns[-window:])
    
    def _calculate_vwap(self, price_history: List[Price]) -> float:
        """
        Рассчитывает VWAP (Volume Weighted Average Price).
        
        Args:
            price_history: История цен с объемами
            
        Returns:
            float: VWAP
        """
        if not price_history:
            return 0.0
        
        total_volume = sum(p.volume for p in price_history)
        if total_volume == 0:
            return sum(p.close for p in price_history) / len(price_history)
        
        vwap = sum(p.close * p.volume for p in price_history) / total_volume
        return vwap
    
    def _calculate_confidence(self, 
                            volume_anomaly_score: float,
                            ofi_score: float,
                            volatility: float,
                            hurst: float,
                            vwap_deviation: float) -> float:
        """
        Рассчитывает уверенность в сигнале.
        
        Returns:
            float: Уверенность от 0 до 1
        """
        # Веса для каждого компонента
        weights = {
            'volume': 0.3,
            'ofi': 0.25,
            'volatility': 0.2,
            'hurst': 0.15,
            'vwap': 0.1
        }
        
        # Нормализация компонентов
        volume_score = min(volume_anomaly_score, 1.0)
        ofi_normalized = min(ofi_score / 0.5, 1.0)  # Нормализуем к 0-1
        volatility_score = 1.0 - min(volatility / self.volatility_threshold, 1.0)
        hurst_score = 1.0 - min(hurst / self.hurst_threshold, 1.0)
        vwap_score = 1.0 - min(vwap_deviation / 0.05, 1.0)  # 5% максимальное отклонение
        
        # Взвешенная сумма
        confidence = (
            weights['volume'] * volume_score +
            weights['ofi'] * ofi_normalized +
            weights['volatility'] * volatility_score +
            weights['hurst'] * hurst_score +
            weights['vwap'] * vwap_score
        )
        
        return min(max(confidence, 0.0), 1.0)
    
    def _save_signal(self, db_session, signal: SleepingGiantSignal):
        """
        Сохраняет сигнал в базу данных.
        
        Args:
            db_session: Сессия БД
            signal: Сигнал для сохранения
        """
        try:
            # Преобразуем тип сигнала
            signal_type_map = {
                'buy': SignalType.BUY,
                'sell': SignalType.SELL,
                'neutral': SignalType.NEUTRAL
            }
            
            db_signal = Signal(
                symbol=signal.symbol,
                signal_type=signal_type_map.get(signal.signal_type, SignalType.NEUTRAL),
                action=signal.signal_type.upper(),  # Для обратной совместимости
                confidence=signal.confidence,
                price=signal.price,
                strategy='sleeping_giants',
                reason=signal.reason,
                details=signal.details,
                indicators={
                    'volume_anomaly_score': signal.volume_anomaly_score,
                    'hurst_exponent': signal.hurst_exponent,
                    'vwap_deviation': signal.vwap_deviation,
                    'ofi_score': signal.ofi_score,
                    'volatility': signal.volatility
                }
            )
            
            db_session.add(db_signal)
            logger.debug(f"Saved Sleeping Giant signal for {signal.symbol}")
            
        except Exception as e:
            logger.error(f"Error saving signal: {e}")
    
    def calculate_indicators(self, price_history: pd.DataFrame) -> Dict[str, float]:
        """
        Рассчитывает индикаторы для отображения.
        
        Args:
            price_history: DataFrame с историей цен
            
        Returns:
            Dict[str, float]: Словарь индикаторов
        """
        if price_history.empty:
            return {}
        
        prices = price_history['close'].values
        volumes = price_history['volume'].values
        
        # Рассчитываем индикаторы
        volatility = self._calculate_volatility(prices)
        hurst = self.hurst_calculator.calculate_hurst(prices)
        
        # VWAP
        vwap = np.sum(prices * volumes) / np.sum(volumes) if np.sum(volumes) > 0 else 0
        
        # Volume metrics
        avg_volume = np.mean(volumes)
        current_volume = volumes[-1] if len(volumes) > 0 else 0
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        return {
            'volatility': volatility,
            'hurst_exponent': hurst,
            'vwap': vwap,
            'avg_volume': avg_volume,
            'current_volume': current_volume,
            'volume_ratio': volume_ratio
        }


# Пример использования (для тестирования)
if __name__ == "__main__":
    async def test_strategy():
        strategy = SleepingGiantsStrategy()
        signals = await strategy.analyze()
        
        if signals:
            for signal in signals:
                print(f"Signal for {signal.symbol}:")
                print(f"  Type: {signal.signal_type}")
                print(f"  Confidence: {signal.confidence:.3f}")
                print(f"  Reason: {signal.reason}")
        else:
            print("No signals generated")
    
    asyncio.run(test_strategy())


# Обновление для файла src/bot/manager.py
# Добавьте следующий код в метод _init_signal_components после инициализации других стратегий

def _init_signal_components(self):
    """Инициализация компонентов системы сигналов"""
    try:
        # Инициализация продюсеров данных
        logger.info("🔧 Инициализация продюсеров данных...")
        
        # OnchainDataProducer
        try:
            from ..api_clients.onchain_data_producer import OnchainDataProducer
            self.onchain_producer = OnchainDataProducer()
            logger.info("✅ OnchainDataProducer инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось инициализировать OnchainDataProducer: {e}")
            self.onchain_producer = None
        
        # BybitDataProducer
        try:
            from ..api_clients.bybit_data_producer import BybitDataProducer
            self.bybit_producer = BybitDataProducer(testnet=self.testnet)
            logger.info("✅ BybitDataProducer инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось инициализировать BybitDataProducer: {e}")
            self.bybit_producer = None
        
        # Инициализация стратегий
        logger.info("🔧 Инициализация стратегий...")
        
        # WhaleHuntingStrategy
        try:
            from ..strategies.whale_hunting import WhaleHuntingStrategy
            self.whale_hunting_strategy = WhaleHuntingStrategy(
                min_usd_value=getattr(self.config, 'WHALE_MIN_USD_VALUE', 100000),
                exchange_flow_threshold=getattr(self.config, 'WHALE_EXCHANGE_FLOW_THRESHOLD', 500000)
            )
            logger.info("✅ WhaleHuntingStrategy инициализирована")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось инициализировать WhaleHuntingStrategy: {e}")
            self.whale_hunting_strategy = None
        
        # SleepingGiantsStrategy - НОВОЕ ДОБАВЛЕНИЕ
        try:
            from ..strategies.sleeping_giants import SleepingGiantsStrategy
            self.sleeping_giants_strategy = SleepingGiantsStrategy(
                volatility_threshold=getattr(self.config, 'SLEEPING_GIANTS_VOLATILITY_THRESHOLD', 0.02),
                volume_anomaly_threshold=getattr(self.config, 'SLEEPING_GIANTS_VOLUME_THRESHOLD', 0.7),
                hurst_threshold=getattr(self.config, 'SLEEPING_GIANTS_HURST_THRESHOLD', 0.45),
                ofi_threshold=getattr(self.config, 'SLEEPING_GIANTS_OFI_THRESHOLD', 0.3),
                min_confidence=getattr(self.config, 'SLEEPING_GIANTS_MIN_CONFIDENCE', 0.6)
            )
            logger.info("✅ SleepingGiantsStrategy инициализирована")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось инициализировать SleepingGiantsStrategy: {e}")
            self.sleeping_giants_strategy = None
        
        # SignalAggregator
        try:
            from ..strategies.signal_aggregator import SignalAggregator
            self.signal_aggregator = SignalAggregator()
            logger.info("✅ SignalAggregator инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось инициализировать SignalAggregator: {e}")
            self.signal_aggregator = None
        
        logger.info("✅ Компоненты системы сигналов инициализированы")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации компонентов сигналов: {e}")
        raise

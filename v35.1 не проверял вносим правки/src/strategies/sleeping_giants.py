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

# ИСПРАВЛЕНО: Правильные импорты из core.models
from ..core.unified_config import config
from ..core.database import SessionLocal
from ..core.models import (
    Signal, 
    VolumeAnomaly, 
    OrderBookSnapshot,
    SignalTypeEnum,  # Правильное имя enum
    MarketData  # Вместо Price используем MarketData
)

# Импорт базовой стратегии - проверим существование
try:
    from .base_strategy import BaseStrategy
except ImportError:
    from .base import BaseStrategy

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
                 volume_anomaly_threshold: float = 3.0,
                 hurst_threshold: float = 0.6,
                 ofi_threshold: float = 1000,
                 min_confidence: float = 0.7):
        """
        Инициализация стратегии
        """
        # Собираем конфиг для передачи в базовый класс
        strategy_config = {
            'volatility_threshold': volatility_threshold,
            'volume_anomaly_threshold': volume_anomaly_threshold,
            'hurst_threshold': hurst_threshold,
            'ofi_threshold': ofi_threshold,
            'min_confidence': min_confidence
        }
        
        # Вызываем конструктор родителя с ПРАВИЛЬНЫМИ аргументами
        super().__init__(strategy_name="sleeping_giants", config=strategy_config)

        # Параметры стратегии
        self.volatility_threshold = volatility_threshold
        self.volume_anomaly_threshold = volume_anomaly_threshold
        self.hurst_threshold = hurst_threshold
        self.ofi_threshold = ofi_threshold
        self.min_confidence = min_confidence
        
        # Внутренние переменные
        self.lookback_hours = 24
        self.volume_window = 6  # часов
        self.price_window = 100  # свечей
        
        logger.info(f"✅ {self.name} инициализирована (volatility_threshold={volatility_threshold})")
    
    async def analyze(self, symbol: str) -> Optional[SleepingGiantSignal]:
        """
        Анализ одного символа
        
        Args:
            symbol: Торговый символ (например, 'BTC/USDT')
            
        Returns:
            SleepingGiantSignal если найден сигнал, иначе None
        """
        try:
            with SessionLocal() as db:
                # 1. Проверка волатильности
                volatility = await self._calculate_volatility(db, symbol)
                if volatility > self.volatility_threshold:
                    return None
                
                # 2. Проверка аномалии объема
                volume_anomaly = await self._check_volume_anomaly(db, symbol)
                if not volume_anomaly or volume_anomaly.score < self.volume_anomaly_threshold:
                    return None
                
                # 3. Расчет показателя Хёрста
                prices = await self._get_price_series(db, symbol)
                if len(prices) < 50:
                    return None
                    
                hurst = HurstCalculator.calculate_hurst(prices)
                
                # 4. Расчет OFI (Order Flow Imbalance)
                ofi_score = await self._calculate_ofi(db, symbol)
                
                # 5. Расчет отклонения от VWAP
                vwap_deviation = await self._calculate_vwap_deviation(db, symbol)
                
                # 6. Генерация сигнала
                signal = self._generate_signal(
                    symbol=symbol,
                    volatility=volatility,
                    volume_anomaly_score=volume_anomaly.score,
                    hurst=hurst,
                    ofi_score=ofi_score,
                    vwap_deviation=vwap_deviation
                )
                
                # 7. Сохранение сигнала если он достаточно уверенный
                if signal and signal.confidence >= self.min_confidence:
                    await self._save_signal(db, signal)
                    return signal
                    
        except Exception as e:
            logger.error(f"Ошибка при анализе {symbol}: {e}", exc_info=True)
            
        return None
    
    async def _calculate_volatility(self, db, symbol: str) -> float:
        """Расчет волатильности за последние 24 часа"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=self.lookback_hours)
            
            # ✅ ИСПРАВЛЕНО: Запрос возвращает кортежи (tuples), а не объекты.
            # Также, в модели MarketData поле называется last_price.
            prices_tuples = db.query(MarketData.last_price).filter(
                and_(MarketData.symbol == symbol, MarketData.updated_at > cutoff_time)
            ).all()
            
            if len(prices_tuples) < 10:
                return float('inf')
            
            # ✅ ИСПРАВЛЕНО: Извлекаем значения из кортежей и преобразуем в float
            price_values = [float(p[0]) for p in prices_tuples if p and p[0] is not None]
            
            if len(price_values) < 2:
                 return float('inf')
    
            returns = np.diff(np.log(price_values))
            volatility = np.std(returns) * np.sqrt(365 * 24)
            return volatility
            
        except Exception as e:
            logger.error(f"Ошибка расчета волатильности для {symbol}: {e}")
            return float('inf')


    
    async def _check_volume_anomaly(self, db, symbol: str) -> Optional[VolumeAnomaly]:
        """Проверка наличия аномалий объема"""
        try:
            # Получаем последнюю аномалию
            anomaly = db.query(VolumeAnomaly).filter(
                VolumeAnomaly.symbol == symbol
            ).order_by(VolumeAnomaly.detected_at.desc()).first()
            
            if anomaly and (datetime.utcnow() - anomaly.detected_at).total_seconds() < 3600:
                return anomaly
                
        except Exception as e:
            logger.error(f"Ошибка проверки аномалии объема: {e}")
            
        return None
    
    async def _get_price_series(self, db, symbol: str) -> np.ndarray:
        """Получение временного ряда цен"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=self.lookback_hours)
            
            prices = db.query(MarketData.last_price).filter(
                and_(
                    MarketData.symbol == symbol,
                    MarketData.updated_at > cutoff_time
                )
            ).order_by(MarketData.updated_at.asc()).all()
            
            return np.array([float(p[0]) for p in prices])
            
        except Exception as e:
            logger.error(f"Ошибка получения ценового ряда: {e}")
            return np.array([])
    
    async def _calculate_ofi(self, db, symbol: str) -> float:
        """Расчет Order Flow Imbalance"""
        try:
            # Получаем последние снимки стакана
            snapshots = db.query(OrderBookSnapshot).filter(
                OrderBookSnapshot.symbol == symbol
            ).order_by(OrderBookSnapshot.timestamp.desc()).limit(10).all()
            
            if not snapshots:
                return 0.0
            
            total_ofi = 0.0
            for snapshot in snapshots:
                ofi = (snapshot.bid_volume - snapshot.ask_volume) / (snapshot.bid_volume + snapshot.ask_volume)
                total_ofi += ofi
            
            return total_ofi / len(snapshots)
            
        except Exception as e:
            logger.error(f"Ошибка расчета OFI: {e}")
            return 0.0
    
    async def _calculate_vwap_deviation(self, db, symbol: str) -> float:
        """Расчет отклонения от VWAP"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=6)
            
            # Получаем данные о ценах и объемах
            data = db.query(
                MarketData.last_price,
                MarketData.volume_24h
            ).filter(
                and_(
                    MarketData.symbol == symbol,
                    MarketData.updated_at > cutoff_time
                )
            ).all()
            
            if not data:
                return 0.0
            
            prices = np.array([float(d[0]) for d in data])
            volumes = np.array([float(d[1]) for d in data])
            
            # Расчет VWAP
            vwap = np.sum(prices * volumes) / np.sum(volumes)
            current_price = prices[-1]
            
            # Процентное отклонение
            deviation = (current_price - vwap) / vwap
            
            return deviation
            
        except Exception as e:
            logger.error(f"Ошибка расчета VWAP deviation: {e}")
            return 0.0
    
    def _generate_signal(self, **kwargs) -> Optional[SleepingGiantSignal]:
        """Генерация торгового сигнала на основе анализа"""
        try:
            # Извлечение параметров
            symbol = kwargs['symbol']
            volatility = kwargs['volatility']
            volume_anomaly_score = kwargs['volume_anomaly_score']
            hurst = kwargs['hurst']
            ofi_score = kwargs['ofi_score']
            vwap_deviation = kwargs['vwap_deviation']
            
            # Определение типа сигнала
            signal_type = 'neutral'
            confidence = 0.0
            reason_parts = []
            
            # Анализ показателей
            if volume_anomaly_score > self.volume_anomaly_threshold:
                confidence += 0.3
                reason_parts.append(f"объем выше нормы в {volume_anomaly_score:.1f}x")
            
            if hurst > self.hurst_threshold:
                confidence += 0.2
                reason_parts.append(f"тренд подтвержден (H={hurst:.2f})")
            
            if abs(ofi_score) > 0.3:
                confidence += 0.2
                if ofi_score > 0:
                    signal_type = 'buy'
                    reason_parts.append("покупательское давление")
                else:
                    signal_type = 'sell'
                    reason_parts.append("продавательское давление")
            
            if abs(vwap_deviation) > 0.02:
                confidence += 0.15
                if vwap_deviation < 0:
                    if signal_type != 'sell':
                        signal_type = 'buy'
                    reason_parts.append("цена ниже VWAP")
                else:
                    if signal_type != 'buy':
                        signal_type = 'sell'
                    reason_parts.append("цена выше VWAP")
            
            if volatility < self.volatility_threshold * 0.5:
                confidence += 0.15
                reason_parts.append("крайне низкая волатильность")
            
            # Создание сигнала
            if confidence >= self.min_confidence and signal_type != 'neutral':
                return SleepingGiantSignal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence=min(confidence, 1.0),
                    price=0.0,  # Будет установлена при сохранении
                    volume_anomaly_score=volume_anomaly_score,
                    hurst_exponent=hurst,
                    vwap_deviation=vwap_deviation,
                    ofi_score=ofi_score,
                    volatility=volatility,
                    reason=f"Спящий гигант: {', '.join(reason_parts)}",
                    details={
                        'volatility': volatility,
                        'volume_anomaly_score': volume_anomaly_score,
                        'hurst_exponent': hurst,
                        'ofi_score': ofi_score,
                        'vwap_deviation': vwap_deviation
                    },
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Ошибка генерации сигнала: {e}")
            
        return None
    
    async def _save_signal(self, db, signal: SleepingGiantSignal):
        """Сохранение сигнала в БД"""
        try:
            # Получаем текущую цену
            latest_price = db.query(MarketData.last_price).filter(
                MarketData.symbol == signal.symbol
            ).order_by(MarketData.updated_at.desc()).first()
            
            if latest_price:
                signal.price = float(latest_price[0])
            
            # Преобразуем signal_type в action для модели Signal
            action_map = {
                'buy': 'BUY',
                'sell': 'SELL',
                'neutral': 'HOLD'
            }
            
            # Создаем сигнал в БД
            db_signal = Signal(
                symbol=signal.symbol,
                strategy=self.name,
                action=action_map.get(signal.signal_type, 'HOLD'),
                price=signal.price,
                confidence=signal.confidence,
                reason=signal.reason,
                indicators=signal.details,
            )
            
            db.add(db_signal)
            db.commit()
            
            logger.info(
                f"💎 Сигнал сохранен: {signal.symbol} {signal.signal_type.upper()} "
                f"(confidence: {signal.confidence:.2%})"
            )
            
        except Exception as e:
            logger.error(f"Ошибка сохранения сигнала: {e}")
            db.rollback()
    
    async def run(self):
        """Основной цикл стратегии"""
        logger.info(f"🚀 Запуск стратегии {self.name}")
        
        while True:
            try:
                with SessionLocal() as db:
                    # Получаем список активных символов
                    symbols = await self._get_active_symbols(db)
                    
                    # Анализируем каждый символ
                    signals_generated = 0
                    for symbol in symbols:
                        signal = await self.analyze(symbol)
                        if signal:
                            signals_generated += 1
                    
                    if signals_generated > 0:
                        logger.info(f"💎 Сгенерировано {signals_generated} сигналов")
                
                # Ждем перед следующей итерацией
                await asyncio.sleep(config.SLEEPING_GIANTS_INTERVAL)
                
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _get_active_symbols(self, db) -> List[str]:
        """Получение списка активных символов"""
        try:
            # Получаем уникальные символы из последних аномалий объема
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            symbols = db.query(VolumeAnomaly.symbol).filter(
                VolumeAnomaly.detected_at > cutoff_time
            ).distinct().all()
            
            return [s[0] for s in symbols]
            
        except Exception as e:
            logger.error(f"Ошибка получения активных символов: {e}")
            return []
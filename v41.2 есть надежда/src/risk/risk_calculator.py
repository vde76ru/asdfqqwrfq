#!/usr/bin/env python3
"""
Калькулятор рисков для матрицы сигналов
Файл: src/risk/risk_calculator.py

Оценивает риск для каждой торговой пары на основе:
- Волатильности (ATR)
- Ширины канала Боллинджера
- Объема торгов
- Количества противоречивых сигналов
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass

from ..core.database import SessionLocal
from ..core.models import Candle, VolumeAnomaly
from ..data.indicators import UnifiedIndicators

logger = logging.getLogger(__name__)

@dataclass
class RiskAssessment:
    """Оценка риска для символа"""
    level: str  # Low, Medium, High, Extreme
    score: float  # 0.0 - 1.0
    details: str
    factors: Dict[str, float]


class RiskCalculator:
    """
    Калькулятор рисков для торговых пар
    """
    
    def __init__(self):
        self.indicators = UnifiedIndicators()
        logger.info("✅ RiskCalculator инициализирован")
    
    def assess_symbol_risk(self, symbol: str, strategies_data: List[Dict]) -> Dict:
        """
        Оценка риска для конкретного символа
        
        Args:
            symbol: Торговая пара
            strategies_data: Данные от всех стратегий
            
        Returns:
            Dict с оценкой риска
        """
        try:
            # Получаем рыночные данные
            db = SessionLocal()
            try:
                # Последние свечи для расчета индикаторов
                candles = db.query(Candle).filter(
                    Candle.symbol == symbol,
                    Candle.interval == '15m'
                ).order_by(Candle.open_time.desc()).limit(100).all()
                
                if len(candles) < 20:
                    return self._default_risk_assessment()
                
                # Преобразуем в DataFrame
                candles_data = []
                for candle in reversed(candles):
                    candles_data.append({
                        'open': float(candle.open),
                        'high': float(candle.high),
                        'low': float(candle.low),
                        'close': float(candle.close),
                        'volume': float(candle.volume),
                        'timestamp': candle.timestamp
                    })
                
                # Рассчитываем факторы риска
                risk_factors = self._calculate_risk_factors(
                    candles_data, symbol, strategies_data, db
                )
                
                # Определяем общий уровень риска
                risk_assessment = self._determine_risk_level(risk_factors)
                
                return {
                    'level': risk_assessment.level,
                    'score': risk_assessment.score,
                    'details': risk_assessment.details,
                    'factors': risk_assessment.factors
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка оценки риска для {symbol}: {e}")
            return self._default_risk_assessment()
    
    def _calculate_risk_factors(self, candles_data: List[Dict], symbol: str, 
                               strategies_data: List[Dict], db) -> Dict[str, float]:
        """Расчет факторов риска"""
        
        factors = {}
        
        # 1. Волатильность (ATR)
        if len(candles_data) >= 14:
            highs = [c['high'] for c in candles_data]
            lows = [c['low'] for c in candles_data]
            closes = [c['close'] for c in candles_data]
            
            atr = self._calculate_atr(highs, lows, closes)
            current_price = candles_data[-1]['close']
            atr_percent = (atr / current_price) * 100 if current_price > 0 else 0
            
            factors['volatility'] = min(atr_percent / 10, 1.0)  # Нормализация до 1.0
        else:
            factors['volatility'] = 0.5
        
        # 2. Ширина канала Боллинджера
        if len(candles_data) >= 20:
            closes = [c['close'] for c in candles_data]
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(closes)
            
            bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
            factors['bb_width'] = min(bb_width / 0.1, 1.0)  # Нормализация
        else:
            factors['bb_width'] = 0.5
        
        # 3. Аномалии объема
        volume_anomalies = db.query(VolumeAnomaly).filter(
            VolumeAnomaly.symbol == symbol,
            VolumeAnomaly.timestamp > datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        factors['volume_anomalies'] = min(volume_anomalies / 10, 1.0)
        
        # 4. Противоречивость сигналов
        buy_count = sum(1 for s in strategies_data if s['status'] == 'BUY')
        sell_count = sum(1 for s in strategies_data if s['status'] == 'SELL')
        total_strategies = len(strategies_data)
        
        if total_strategies > 0:
            # Максимальная противоречивость когда 50/50
            contradiction = abs(buy_count - sell_count) / total_strategies
            factors['signal_contradiction'] = 1.0 - contradiction
        else:
            factors['signal_contradiction'] = 0.5
        
        # 5. Сила тренда (определяем по EMA)
        if len(candles_data) >= 50:
            closes = [c['close'] for c in candles_data]
            ema_short = self._calculate_ema(closes, 12)
            ema_long = self._calculate_ema(closes, 26)
            
            if ema_long > 0:
                trend_strength = abs(ema_short - ema_long) / ema_long
                factors['trend_strength'] = 1.0 - min(trend_strength / 0.05, 1.0)
            else:
                factors['trend_strength'] = 0.5
        else:
            factors['trend_strength'] = 0.5
        
        return factors
    
    def _determine_risk_level(self, factors: Dict[str, float]) -> RiskAssessment:
        """Определение уровня риска на основе факторов"""
        
        # Веса факторов
        weights = {
            'volatility': 0.3,
            'bb_width': 0.2,
            'volume_anomalies': 0.2,
            'signal_contradiction': 0.2,
            'trend_strength': 0.1
        }
        
        # Взвешенный расчет общего риска
        total_risk = sum(
            factors.get(factor, 0.5) * weight 
            for factor, weight in weights.items()
        )
        
        # Определяем уровень
        if total_risk < 0.25:
            level = "Low"
            details = "Низкая волатильность, согласованные сигналы"
        elif total_risk < 0.5:
            level = "Medium"
            details = "Умеренная волатильность, стабильный тренд"
        elif total_risk < 0.75:
            level = "High"
            details = "Высокая волатильность, противоречивые сигналы"
        else:
            level = "Extreme"
            details = "Экстремальная волатильность, рыночная неопределенность"
        
        # Добавляем детали по основным факторам
        if factors.get('volatility', 0) > 0.7:
            details += ". Очень высокая волатильность (ATR)"
        if factors.get('signal_contradiction', 0) > 0.7:
            details += ". Сильное расхождение между стратегиями"
        if factors.get('volume_anomalies', 0) > 0.5:
            details += ". Обнаружены аномалии объема"
        
        return RiskAssessment(
            level=level,
            score=total_risk,
            details=details,
            factors=factors
        )
    
    def _calculate_atr(self, highs: List[float], lows: List[float], 
                      closes: List[float], period: int = 14) -> float:
        """Расчет Average True Range"""
        
        if len(highs) < period + 1:
            return 0.0
        
        true_ranges = []
        for i in range(1, len(highs)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            true_ranges.append(max(high_low, high_close, low_close))
        
        if len(true_ranges) >= period:
            return sum(true_ranges[-period:]) / period
        return 0.0
    
    def _calculate_bollinger_bands(self, closes: List[float], 
                                  period: int = 20, std_dev: int = 2) -> Tuple[float, float, float]:
        """Расчет полос Боллинджера"""
        
        if len(closes) < period:
            return 0.0, 0.0, 0.0
        
        recent_closes = closes[-period:]
        sma = sum(recent_closes) / period
        
        variance = sum((x - sma) ** 2 for x in recent_closes) / period
        std = variance ** 0.5
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        return upper, sma, lower
    
    def _calculate_ema(self, data: List[float], period: int) -> float:
        """Расчет экспоненциальной скользящей средней"""
        
        if len(data) < period:
            return 0.0
        
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _default_risk_assessment(self) -> Dict:
        """Оценка риска по умолчанию"""
        return {
            'level': 'Medium',
            'score': 0.5,
            'details': 'Недостаточно данных для точной оценки',
            'factors': {
                'volatility': 0.5,
                'bb_width': 0.5,
                'volume_anomalies': 0.0,
                'signal_contradiction': 0.5,
                'trend_strength': 0.5
            }
        }
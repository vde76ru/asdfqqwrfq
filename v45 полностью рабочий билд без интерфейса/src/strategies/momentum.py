"""
Momentum стратегия - ИСПРАВЛЕННАЯ ВЕРСЯ
Файл: src/strategies/momentum.py
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from datetime import datetime

try:
    from ta.momentum import RSIIndicator, ROCIndicator
    from ta.trend import EMAIndicator
    from ta.volatility import AverageTrueRange
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logging.warning("⚠️ TA-Lib не установлен, используем ручные реализации")

from .base import BaseStrategy
from ..common.types import UnifiedTradingSignal as TradingSignal

logger = logging.getLogger(__name__)

class MomentumStrategy(BaseStrategy):
    """
    Улучшенная momentum стратегия - ИСПРАВЛЕННАЯ ВЕРСЯ
    Торгует по направлению сильного движения с защитой от ошибок
    
    ИСПРАВЛЕНИЯ:
    - Правильная инициализация с новым BaseStrategy
    - Обработка отсутствия TA-Lib
    - Улучшенная обработка ошибок
    """
    
    # Константы стратегии
    PRICE_CHANGE_THRESHOLD_5D = 1.0
    PRICE_CHANGE_THRESHOLD_10D = 2.0
    ROC_BULLISH_THRESHOLD = 2.0
    ROC_BEARISH_THRESHOLD = -2.0
    VOLUME_RATIO_THRESHOLD = 1.5
    RSI_NEUTRAL = 50
    
    # Метаинформация для фабрики
    STRATEGY_TYPE = 'momentum'
    RISK_LEVEL = 'medium'
    TIMEFRAMES = ['1h', '4h', '1d']
    
    def __init__(self, strategy_name: str = "momentum", config: Optional[Dict] = None):
        """
        Инициализация momentum стратегии
        
        Args:
            strategy_name: Название стратегии
            config: Конфигурация стратегии
        """
        # ✅ ИСПРАВЛЕНИЕ: Правильный вызов родительского конструктора
        super().__init__(strategy_name, config)
        
        # Специфичные для momentum настройки
        self.rsi_period = self.config.get('rsi_period', 14)
        self.ema_fast = self.config.get('ema_fast', 9)
        self.ema_slow = self.config.get('ema_slow', 21)
        self.roc_period = self.config.get('roc_period', 10)
        self.min_momentum_score = self.config.get('min_momentum_score', 0.6)
        
        logger.debug(f"✅ MomentumStrategy инициализирована: {self.name}")
        
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """
        ✅ ИСПРАВЛЕНО: Восстановлена правильная логика анализа для Momentum стратегии.
        """
        current_price = df['close'].iloc[-1] if not df.empty else 0.0

        if not self.validate_dataframe(df):
            return TradingSignal(symbol=symbol, action='WAIT', confidence=0, price=current_price, reason='Недостаточно данных')
        
        try:
            # Рассчитываем индикаторы для momentum
            indicators = await self._calculate_indicators(df)
            
            # Проверяем корректность данных
            if not indicators:
                return TradingSignal(symbol=symbol, action='WAIT', confidence=0, price=current_price, reason='Ошибка расчета индикаторов')
            
            # Анализируем momentum
            momentum_score = self._analyze_momentum(indicators)
            
            # Принимаем решение на основе momentum
            return self._make_decision(momentum_score, indicators, df, symbol)
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа momentum для {symbol}: {e}")
            return TradingSignal(symbol=symbol, action='WAIT', confidence=0, price=current_price, reason=f'Ошибка анализа: {e}')

    async def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Улучшенный расчет индикаторов с защитой от ошибок"""
        
        try:
            current_price = df['close'].iloc[-1]
            indicators = {
                'current_price': current_price,
                'timestamp': datetime.utcnow()
            }
            
            # === PRICE MOMENTUM ===
            if len(df) >= 5:
                price_5d_ago = df['close'].iloc[-5]
                indicators['price_change_5d'] = ((current_price - price_5d_ago) / price_5d_ago) * 100 if price_5d_ago != 0 else 0
            else:
                indicators['price_change_5d'] = 0
            
            if len(df) >= 10:
                price_10d_ago = df['close'].iloc[-10]
                indicators['price_change_10d'] = ((current_price - price_10d_ago) / price_10d_ago) * 100 if price_10d_ago != 0 else 0
            else:
                indicators['price_change_10d'] = 0
                
            # === MOVING AVERAGES ===
            if TA_AVAILABLE and len(df) > self.ema_slow:
                ema_fast = EMAIndicator(close=df['close'], window=self.ema_fast).ema_indicator()
                indicators['ema_fast'] = ema_fast.iloc[-1]
                ema_slow = EMAIndicator(close=df['close'], window=self.ema_slow).ema_indicator()
                indicators['ema_slow'] = ema_slow.iloc[-1]
            else:
                indicators['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean().iloc[-1]
                indicators['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean().iloc[-1]
                
            indicators['ema_cross'] = 'bullish' if indicators['ema_fast'] > indicators['ema_slow'] else 'bearish'
            
            # === RSI ===
            if TA_AVAILABLE and len(df) > self.rsi_period:
                rsi = RSIIndicator(close=df['close'], window=self.rsi_period).rsi()
                indicators['rsi'] = rsi.iloc[-1]
            else:
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
                if loss.iloc[-1] == 0:
                    indicators['rsi'] = 100.0
                else:
                    rs = gain / loss
                    rsi_series = 100 - (100 / (1 + rs))
                    indicators['rsi'] = rsi_series.iloc[-1]

            # === ROC (Rate of Change) ===
            if TA_AVAILABLE and len(df) > self.roc_period:
                roc = ROCIndicator(close=df['close'], window=self.roc_period).roc()
                indicators['roc'] = roc.iloc[-1]
            else:
                if len(df) > self.roc_period:
                    price_then = df['close'].iloc[-self.roc_period -1]
                    roc_value = ((current_price - price_then) / price_then) * 100 if price_then != 0 else 0
                    indicators['roc'] = roc_value
                else:
                    indicators['roc'] = 0
                    
            # === ATR для расчета уровней ===
            if TA_AVAILABLE and len(df) > 14:
                atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()
                indicators['atr'] = atr.iloc[-1]
            else:
                high_low = df['high'] - df['low']
                high_close = abs(df['high'] - df['close'].shift())
                low_close = abs(df['low'] - df['close'].shift())
                true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                indicators['atr'] = true_range.ewm(alpha=1/14, adjust=False).mean().iloc[-1]
                
            # === VOLUME ANALYSIS ===
            if 'volume' in df.columns and len(df) > 20:
                avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
                current_volume = df['volume'].iloc[-1]
                indicators['volume_ratio'] = current_volume / avg_volume if avg_volume > 0 else 1
                
                vwap = (df['close'] * df['volume']).rolling(window=20).sum() / df['volume'].rolling(window=20).sum()
                indicators['vwap'] = vwap.iloc[-1]
                indicators['price_vs_vwap'] = ((current_price - indicators['vwap']) / indicators['vwap']) * 100 if indicators['vwap'] != 0 else 0
            else:
                indicators['volume_ratio'] = 1.0
                indicators['vwap'] = current_price
                indicators['price_vs_vwap'] = 0
                
            # Заполняем NaN значения, если они появились
            for key, value in indicators.items():
                if pd.isna(value):
                    logger.warning(f"Обнаружен NaN в индикаторе '{key}', заменяем на безопасное значение.")
                    if key == 'rsi': indicators[key] = 50.0
                    elif key in ['current_price', 'ema_fast', 'ema_slow', 'vwap']: indicators[key] = df['close'].iloc[-1]
                    else: indicators[key] = 0.0

            return indicators
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета индикаторов: {e}")
            return {}
            
    # =================================================================
    # 2. УЛУЧШЕНИЕ АНАЛИЗА MOMENTUM SCORE
    # =================================================================
    
    def _analyze_momentum_score(self, indicators: Dict) -> Dict:
        """Улучшенный анализ momentum с весовыми коэффициентами"""
        
        momentum_score = {
            'direction': 'NEUTRAL',
            'strength': 0.0,
            'components': [],
            'detailed_scores': {}
        }
        
        try:
            bullish_score = 0.0
            bearish_score = 0.0
            
            # === 1. PRICE MOMENTUM ANALYSIS (40% веса) ===
            price_5d = indicators['price_change_5d']
            if price_5d > self.PRICE_CHANGE_THRESHOLD_5D:
                bullish_score += 0.20
                momentum_score['components'].append(f'Цена +{price_5d:.1f}% за 5 период')
            elif price_5d < -self.PRICE_CHANGE_THRESHOLD_5D:
                bearish_score += 0.20
                momentum_score['components'].append(f'Цена {price_5d:.1f}% за 5 период')
                
            momentum_score['detailed_scores']['price_5d'] = price_5d
            
            price_10d = indicators['price_change_10d']
            if price_10d > self.PRICE_CHANGE_THRESHOLD_10D:
                bullish_score += 0.20
                momentum_score['components'].append(f'Цена +{price_10d:.1f}% за 10 периодов')
            elif price_10d < -self.PRICE_CHANGE_THRESHOLD_10D:
                bearish_score += 0.20
                momentum_score['components'].append(f'Цена {price_10d:.1f}% за 10 периодов')
                
            momentum_score['detailed_scores']['price_10d'] = price_10d
            
            # === 2. EMA CROSS ANALYSIS (20% веса) ===
            if indicators['ema_cross'] == 'bullish':
                bullish_score += 0.20
                momentum_score['components'].append('EMA пересечение вверх')
            elif indicators['ema_cross'] == 'bearish':
                bearish_score += 0.20
                momentum_score['components'].append('EMA пересечение вниз')
                
            # === 3. RSI MOMENTUM (15% веса) ===
            rsi = indicators['rsi']
            if rsi > 60:
                bullish_score += 0.15
                momentum_score['components'].append(f'RSI бычий: {rsi:.1f}')
            elif rsi < 40:
                bearish_score += 0.15
                momentum_score['components'].append(f'RSI медвежий: {rsi:.1f}')
                
            momentum_score['detailed_scores']['rsi'] = rsi
            
            # === 4. ROC MOMENTUM (15% веса) ===
            roc = indicators['roc']
            if roc > self.ROC_BULLISH_THRESHOLD:
                bullish_score += 0.15
                momentum_score['components'].append(f'ROC растет: {roc:.1f}%')
            elif roc < self.ROC_BEARISH_THRESHOLD:
                bearish_score += 0.15
                momentum_score['components'].append(f'ROC падает: {roc:.1f}%')
                
            momentum_score['detailed_scores']['roc'] = roc
            
            # === 5. VOLUME CONFIRMATION (10% веса) ===
            volume_ratio = indicators['volume_ratio']
            if volume_ratio > self.VOLUME_RATIO_THRESHOLD:
                if bullish_score > bearish_score:
                    bullish_score += 0.10
                    momentum_score['components'].append(f'Объем подтверждает: {volume_ratio:.1f}x')
                elif bearish_score > bullish_score:
                    bearish_score += 0.10
                    momentum_score['components'].append(f'Объем подтверждает: {volume_ratio:.1f}x')
                    
            momentum_score['detailed_scores']['volume_ratio'] = volume_ratio
            
            # === 6. ОПРЕДЕЛЕНИЕ ФИНАЛЬНОГО НАПРАВЛЕНИЯ ===
            momentum_score['detailed_scores']['bullish_score'] = bullish_score
            momentum_score['detailed_scores']['bearish_score'] = bearish_score
            
            if bullish_score > bearish_score and bullish_score > 0.4:
                momentum_score['direction'] = 'BULLISH'
                momentum_score['strength'] = bullish_score
            elif bearish_score > bullish_score and bearish_score > 0.4:
                momentum_score['direction'] = 'BEARISH'  
                momentum_score['strength'] = bearish_score
            else:
                momentum_score['direction'] = 'NEUTRAL'
                momentum_score['strength'] = max(bullish_score, bearish_score)
                
            if momentum_score['strength'] >= 0.8:
                momentum_score['strength_label'] = 'ОЧЕНЬ_СИЛЬНЫЙ'
            elif momentum_score['strength'] >= 0.6:
                momentum_score['strength_label'] = 'СИЛЬНЫЙ'
            elif momentum_score['strength'] >= 0.4:
                momentum_score['strength_label'] = 'УМЕРЕННЫЙ'
            else:
                momentum_score['strength_label'] = 'СЛАБЫЙ'
                
        except Exception as e:
            logger.error(f"❌ Ошибка анализа momentum: {e}")
            momentum_score['components'].append(f'Ошибка анализа: {str(e)}')
            
        return momentum_score
        
    def _calculate_with_talib(self, df: pd.DataFrame) -> Dict:
        """Расчет индикаторов с помощью TA-Lib"""
        indicators = {}
        
        try:
            rsi_indicator = RSIIndicator(df['close'], window=self.rsi_period)
            indicators['rsi'] = float(rsi_indicator.rsi().iloc[-1])
            
            ema_fast = EMAIndicator(df['close'], window=self.ema_fast)
            ema_slow = EMAIndicator(df['close'], window=self.ema_slow)
            indicators['ema_fast'] = float(ema_fast.ema_indicator().iloc[-1])
            indicators['ema_slow'] = float(ema_slow.ema_indicator().iloc[-1])
            
            roc_indicator = ROCIndicator(df['close'], window=self.roc_period)
            indicators['roc'] = float(roc_indicator.roc().iloc[-1])
            
            atr_indicator = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
            indicators['atr'] = float(atr_indicator.average_true_range().iloc[-1])
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка расчета с TA-Lib: {e}, переключаемся на ручной расчет")
            return self._calculate_manual(df)
            
        return indicators
    
    def _calculate_manual(self, df: pd.DataFrame) -> Dict:
        """Ручной расчет индикаторов"""
        indicators = {}
        
        try:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            indicators['rsi'] = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50.0
            
            ema_fast = df['close'].ewm(span=self.ema_fast).mean()
            ema_slow = df['close'].ewm(span=self.ema_slow).mean()
            indicators['ema_fast'] = float(ema_fast.iloc[-1])
            indicators['ema_slow'] = float(ema_slow.iloc[-1])
            
            roc = ((df['close'] - df['close'].shift(self.roc_period)) / df['close'].shift(self.roc_period)) * 100
            indicators['roc'] = float(roc.iloc[-1]) if pd.notna(roc.iloc[-1]) else 0.0
            
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(window=14).mean()
            indicators['atr'] = float(atr.iloc[-1]) if pd.notna(atr.iloc[-1]) else 1.0
            
        except Exception as e:
            logger.error(f"❌ Ошибка ручного расчета индикаторов: {e}")
            indicators = {
                'rsi': 50.0,
                'ema_fast': float(df['close'].iloc[-1]),
                'ema_slow': float(df['close'].iloc[-1]),
                'roc': 0.0,
                'atr': float(df['close'].iloc[-1]) * 0.02
            }
            
        return indicators
    
    def _analyze_momentum(self, indicators: Dict) -> Dict:
        """Анализ momentum на основе индикаторов"""
        momentum_score = {
            'direction': 'NEUTRAL',
            'strength': 0.0,
            'components': []
        }
        
        bullish_score = 0.0
        bearish_score = 0.0
        
        try:
            if indicators['ema_fast'] > indicators['ema_slow']:
                bullish_score += 0.3
                momentum_score['components'].append('EMA бычий')
            else:
                bearish_score += 0.3
                momentum_score['components'].append('EMA медвежий')
            
            rsi = indicators['rsi']
            if rsi > 60:
                bullish_score += 0.2
                momentum_score['components'].append('RSI сильный')
            elif rsi < 40:
                bearish_score += 0.2
                momentum_score['components'].append('RSI слабый')
            
            roc = indicators['roc']
            if roc > self.ROC_BULLISH_THRESHOLD:
                bullish_score += 0.25
                momentum_score['components'].append('ROC растет')
            elif roc < self.ROC_BEARISH_THRESHOLD:
                bearish_score += 0.25
                momentum_score['components'].append('ROC падает')
            
            if indicators.get('volume_ratio', 1.0) > self.VOLUME_RATIO_THRESHOLD:
                if bullish_score > bearish_score:
                    bullish_score += 0.15
                    momentum_score['components'].append('Объем подтверждает')
                else:
                    bearish_score += 0.15
                    momentum_score['components'].append('Объем подтверждает')
            
            if bullish_score > bearish_score and bullish_score > 0.5:
                momentum_score['direction'] = 'BULLISH'
                momentum_score['strength'] = bullish_score
            elif bearish_score > bullish_score and bearish_score > 0.5:
                momentum_score['direction'] = 'BEARISH'
                momentum_score['strength'] = bearish_score
            else:
                momentum_score['direction'] = 'NEUTRAL'
                momentum_score['strength'] = max(bullish_score, bearish_score)
                
        except Exception as e:
            logger.error(f"❌ Ошибка анализа momentum: {e}")
            
        return momentum_score
    
    def _make_decision(self, momentum_score: Dict, indicators: Dict, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """Улучшенное принятие решения с дополнительными фильтрами"""
        
        try:
            current_price = indicators.get('current_price', df['close'].iloc[-1])
        
            if momentum_score['strength'] < self.min_momentum_score:
                return TradingSignal(
                    symbol=symbol,
                    action='WAIT',
                    confidence=0,
                    price=current_price,
                    reason=f"Слабый momentum: {momentum_score['strength']:.2f} < {self.min_momentum_score}",
                    metadata={'momentum_score': momentum_score, 'indicators': indicators}
                )
            
            if momentum_score['direction'] == 'BULLISH':
                action = 'BUY'
            elif momentum_score['direction'] == 'BEARISH':
                action = 'SELL'
            else:
                return TradingSignal(
                    symbol=symbol,
                    action='WAIT',
                    confidence=0,
                    price=current_price,
                    reason="Нейтральный momentum",
                    metadata={'momentum_score': momentum_score}
                )
            
            atr = indicators.get('atr', current_price * 0.01)
            
            rsi = indicators['rsi']
            if action == 'BUY' and rsi > 80:
                return TradingSignal(
                    symbol=symbol, action='WAIT', confidence=0, price=current_price,
                    reason=f"RSI перекуплен: {rsi:.1f}", metadata={'rsi': rsi}
                )
            elif action == 'SELL' and rsi < 20:
                return TradingSignal(
                    symbol=symbol, action='WAIT', confidence=0, price=current_price,
                    reason=f"RSI перепродан: {rsi:.1f}", metadata={'rsi': rsi}
                )
            
            atr_multiplier = 2.5 if momentum_score['strength'] > 0.7 else 2.0
            stop_loss = self.calculate_stop_loss(current_price, action, atr, atr_multiplier)
            
            tp_multiplier = 4.0 if momentum_score['strength'] > 0.8 else 3.0  
            take_profit = self.calculate_take_profit(current_price, action, atr, tp_multiplier)
            
            risk_reward = self.calculate_risk_reward(current_price, stop_loss, take_profit)
            
            min_rr = 1.5 if momentum_score['strength'] > 0.7 else 2.0
            if risk_reward < min_rr:
                return TradingSignal(
                    symbol=symbol, action='WAIT', confidence=0, price=current_price,
                    reason=f"Плохой R/R: {risk_reward:.2f} < {min_rr}",
                    metadata={'risk_reward': risk_reward, 'required': min_rr}
                )
            
            base_confidence = momentum_score['strength']
            
            if indicators.get('volume_ratio', 1.0) > 1.5:
                base_confidence += 0.05
            
            if risk_reward > 3.0:
                base_confidence += 0.05
            
            if rsi > 75 or rsi < 25:
                base_confidence -= 0.1
            
            confidence = min(0.95, max(0.1, base_confidence))
            
            components_str = ', '.join(momentum_score.get('components', [])[:3])
            reason = (f"Momentum {momentum_score['direction']} ({momentum_score.get('strength_label', 'N/A')}): {components_str}")
            
            return TradingSignal(
                symbol=symbol,
                action=action,
                confidence=confidence,
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=reason,
                risk_reward_ratio=risk_reward,
                indicators=indicators,
                metadata={
                    'momentum_score': momentum_score,
                    'atr_multiplier': atr_multiplier,
                    'tp_multiplier': tp_multiplier,
                    'strength_label': momentum_score.get('strength_label', 'N/A'),
                    'detailed_scores': momentum_score.get('detailed_scores', {})
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка принятия решения: {e}")
            price_fallback = indicators.get('current_price', df['close'].iloc[-1] if not df.empty else 0)
            return TradingSignal(
                symbol=symbol,
                action='WAIT',
                confidence=0,
                price=price_fallback,
                reason=f'Ошибка решения: {e}',
                metadata={'error': str(e)}
            )

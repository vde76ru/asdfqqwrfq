"""
Базовый класс для торговых стратегий с ML поддержкой - РАСШИРЕННАЯ ВЕРСИЯ
Файл: src/strategies/base.py
"""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
import logging
import asyncio

logger = logging.getLogger(__name__)

from ..common.types import UnifiedTradingSignal as TradingSignal

class BaseStrategy(ABC):
    """
    Базовый класс для всех торговых стратегий с ML поддержкой
    ИСПРАВЛЕНО: Обработка параметров конфигурации + ML интеграция
    """
    
    def __init__(self, strategy_name: str = "base", config: Optional[Dict] = None):
        """
        Инициализация базовой стратегии с ML поддержкой
        
        Args:
            strategy_name: Название стратегии (строка)
            config: Конфигурация стратегии (словарь, опционально)
        """
        # ✅ ИСПРАВЛЕНИЕ: Правильная обработка параметров
        self.name = strategy_name
        
        # Если config не передан или это строка, создаем пустой словарь
        if config is None or isinstance(config, str):
            self.config = {}
        else:
            self.config = config
            
        # Базовые настройки стратегии (можно переопределить в конфигурации)
        self.timeframe = self.config.get('timeframe', '1h')
        self.risk_percent = self.config.get('risk_percent', 2.0)
        self.max_positions = self.config.get('max_positions', 1)
        
        # ATR множители для расчета стоп-лоссов и тейк-профитов
        self.atr_multiplier_stop = self.config.get('atr_multiplier_stop', 2.0)
        self.atr_multiplier_take = self.config.get('atr_multiplier_take', 3.0)
        
        # Минимальные требования к данным
        self.min_periods = self.config.get('min_periods', 50)
        
        # === НОВОЕ: ML интеграция ===
        self.use_ml = self.config.get('use_ml', True)
        self.ml_weight = self.config.get('ml_weight', 0.3)
        self.ml_min_confidence = self.config.get('ml_min_confidence', 0.6)
        self.ml_timeout_seconds = self.config.get('ml_timeout_seconds', 5)
        
        # ML тренер (ленивая инициализация)
        self.ml_trainer = None
        self._ml_initialized = False
        
        # Статистика ML
        self.ml_stats = {
            'predictions_made': 0,
            'successful_predictions': 0,
            'failed_predictions': 0,
            'combined_signals': 0,
            'ml_only_signals': 0
        }
        
        logger.debug(f"✅ Инициализирована стратегия {self.name} (ML: {'включен' if self.use_ml else 'отключен'})")
    
    async def _initialize_ml(self):
        """
        Ленивая инициализация ML тренера
        """
        if self._ml_initialized or not self.use_ml:
            return
        
        try:
            from ..ml.training.trainer import ml_trainer
            self.ml_trainer = ml_trainer
            
            # Проверяем, что тренер инициализирован
            if not hasattr(self.ml_trainer, 'models') or not self.ml_trainer.models:
                logger.info(f"Инициализируем ML тренер для стратегии {self.name}")
                await self.ml_trainer.initialize()
            
            self._ml_initialized = True
            logger.info(f"✅ ML поддержка активирована для стратегии {self.name}")
            
        except ImportError:
            logger.warning(f"⚠️ ML модули недоступны для стратегии {self.name}")
            self.use_ml = False
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации ML для {self.name}: {e}")
            self.use_ml = False
    
    @abstractmethod
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """
        Основной метод анализа рынка
        
        Args:
            df: DataFrame с рыночными данными
            symbol: Торговая пара
            
        Returns:
            TradingSignal: Торговый сигнал
        """
        pass
    
    async def calculate_market_strength(self, df: pd.DataFrame) -> float:
        """
        Расчет силы рынка для определения качества сигнала
        """
        try:
            # 1. Анализ объема
            volume_sma = df['volume'].rolling(20).mean()
            volume_ratio = df['volume'].iloc[-1] / volume_sma.iloc[-1] if volume_sma.iloc[-1] > 0 else 1
            volume_score = min(volume_ratio / 2, 1)  # Нормализуем до 1
            
            # 2. Анализ волатильности
            returns = df['close'].pct_change()
            volatility = returns.rolling(20).std().iloc[-1]
            volatility_score = 1 - min(volatility / 0.05, 1)  # Низкая волатильность = высокий скор
            
            # 3. Анализ тренда
            sma_20 = df['close'].rolling(20).mean()
            sma_50 = df['close'].rolling(50).mean()
            price = df['close'].iloc[-1]
            
            trend_score = 0
            if price > sma_20.iloc[-1] > sma_50.iloc[-1]:
                trend_score = 1
            elif price > sma_20.iloc[-1] or price > sma_50.iloc[-1]:
                trend_score = 0.5
            
            # 4. Анализ структуры рынка
            highs = df['high'].rolling(20).max()
            lows = df['low'].rolling(20).min()
            range_pct = (highs.iloc[-1] - lows.iloc[-1]) / lows.iloc[-1] if lows.iloc[-1] > 0 else 0
            structure_score = min(range_pct / 0.1, 1)  # Нормализуем до 1
            
            # Взвешенная оценка
            market_strength = (
                volume_score * 0.3 +
                volatility_score * 0.2 +
                trend_score * 0.3 +
                structure_score * 0.2
            )
            
            return market_strength
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета силы рынка: {e}")
            return 0.5

    async def find_support_resistance(self, df: pd.DataFrame) -> tuple:
        """
        Поиск уровней поддержки и сопротивления
        """
        try:
            # Метод 1: Локальные экстремумы
            window = 20
            highs = df['high'].rolling(window, center=True).max()
            lows = df['low'].rolling(window, center=True).min()
            
            # Находим точки разворота
            resistance_levels = df[df['high'] == highs]['high'].unique()
            support_levels = df[df['low'] == lows]['low'].unique()
            
            # Метод 2: Уровни объема
            volume_profile = df.groupby(pd.cut(df['close'], bins=50))['volume'].sum()
            high_volume_levels = volume_profile.nlargest(5).index
            
            # Метод 3: Психологические уровни
            current_price = df['close'].iloc[-1]
            round_levels = [round(current_price, -2), round(current_price, -3)]
            
            # Ближайшие уровни
            all_resistance = sorted([r for r in resistance_levels if r > current_price])
            all_support = sorted([s for s in support_levels if s < current_price], reverse=True)
            
            nearest_resistance = all_resistance[0] if all_resistance else current_price * 1.02
            nearest_support = all_support[0] if all_support else current_price * 0.98
            
            return nearest_support, nearest_resistance
            
        except Exception as e:
            self.logger.error(f"Ошибка поиска уровней: {e}")
            current_price = df['close'].iloc[-1]
            return current_price * 0.98, current_price * 1.02

    async def calculate_entry_score(self, df: pd.DataFrame, signal_type: str) -> float:
        """
        Расчет оценки качества точки входа
        """
        try:
            score = 0
            current_price = df['close'].iloc[-1]
            
            # 1. RSI условия
            rsi = getattr(self, 'indicators', {}).get('rsi', pd.Series([50]))
            if hasattr(rsi, 'iloc'):
                rsi_value = rsi.iloc[-1]
            else:
                rsi_value = 50
                
            if rsi_value < 30 and signal_type == 'long':
                score += 0.2
            elif rsi_value > 70 and signal_type == 'short':
                score += 0.2
            elif 40 < rsi_value < 60:
                score += 0.1
                
            # 2. MACD условия
            macd = getattr(self, 'indicators', {}).get('macd', pd.Series([0]))
            macd_signal = getattr(self, 'indicators', {}).get('macd_signal', pd.Series([0]))
            
            if hasattr(macd, 'iloc') and hasattr(macd_signal, 'iloc'):
                macd_val = macd.iloc[-1]
                signal_val = macd_signal.iloc[-1]
                
                if signal_type == 'long' and macd_val > signal_val:
                    score += 0.2
                elif signal_type == 'short' and macd_val < signal_val:
                    score += 0.2
                    
            # 3. Позиция относительно скользящих средних
            sma_20 = df['close'].rolling(20).mean().iloc[-1]
            sma_50 = df['close'].rolling(50).mean().iloc[-1]
            
            if signal_type == 'long':
                if current_price > sma_20 > sma_50:
                    score += 0.2
                elif current_price > sma_20:
                    score += 0.1
            else:
                if current_price < sma_20 < sma_50:
                    score += 0.2
                elif current_price < sma_20:
                    score += 0.1
                    
            # 4. Паттерны свечей
            last_candles = df.tail(3)
            
            # Бычий пин-бар
            if signal_type == 'long':
                last = last_candles.iloc[-1]
                body = abs(last['close'] - last['open'])
                lower_wick = last['open'] - last['low'] if last['close'] > last['open'] else last['close'] - last['low']
                
                if lower_wick > body * 2:
                    score += 0.15
                    
            # Медвежий пин-бар
            elif signal_type == 'short':
                last = last_candles.iloc[-1]
                body = abs(last['close'] - last['open'])
                upper_wick = last['high'] - last['close'] if last['close'] < last['open'] else last['high'] - last['open']
                
                if upper_wick > body * 2:
                    score += 0.15
                    
            # 5. Объемный анализ
            volume_increase = df['volume'].iloc[-1] / df['volume'].rolling(20).mean().iloc[-1]
            if volume_increase > 1.5:
                score += 0.15
                
            return min(score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета entry score: {e}")
            return 0.5

    async def generate_signal_with_filters(self, df: pd.DataFrame, min_confidence: float = 0.6):
        """
        Генерация сигнала с применением фильтров
        """
        try:
            from datetime import datetime
            
            # Базовый анализ индикаторов
            signals = await self.analyze_indicators(df)
            
            if not signals:
                return None
                
            # Выбираем сильнейший сигнал
            best_signal = max(signals, key=lambda x: x.get('strength', 0))
            
            # Проверяем минимальную силу
            if best_signal.get('strength', 0) < 0.5:
                return None
                
            # Расчет дополнительных метрик
            market_strength = await self.calculate_market_strength(df)
            entry_score = await self.calculate_entry_score(df, best_signal['type'])
            support, resistance = await self.find_support_resistance(df)
            
            # Расчет итоговой уверенности
            confidence = (
                best_signal['strength'] * 0.4 +
                market_strength * 0.3 +
                entry_score * 0.3
            )
            
            # Применяем минимальный порог
            if confidence < min_confidence:
                self.logger.debug(f"Сигнал отклонен: уверенность {confidence:.2%} < {min_confidence:.2%}")
                return None
                
            # Расчет уровней для позиции
            current_price = df['close'].iloc[-1]
            
            # Получаем параметры стоп-лосса и тейк-профита из конфигурации
            stop_loss_pct = getattr(self.config, 'STOP_LOSS_PERCENT', 2) / 100
            take_profit_pct = getattr(self.config, 'TAKE_PROFIT_PERCENT', 4) / 100
            
            if best_signal['type'] == 'long':
                entry_price = current_price
                stop_loss = max(support, current_price * (1 - stop_loss_pct))
                take_profit = min(resistance, current_price * (1 + take_profit_pct))
            else:
                entry_price = current_price
                stop_loss = min(resistance, current_price * (1 + stop_loss_pct))
                take_profit = max(support, current_price * (1 - take_profit_pct))
                
            # Проверка соотношения риск/прибыль
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            if risk_reward_ratio < 1.5:
                self.logger.debug(f"Сигнал отклонен: R/R ratio {risk_reward_ratio:.2f} < 1.5")
                return None
                
            # Формируем финальный сигнал
            signal = {
                'type': best_signal['type'],
                'symbol': getattr(self, 'symbol', 'UNKNOWN'),
                'strategy': getattr(self, 'name', 'BaseStrategy'),
                'confidence': confidence,
                'strength': best_signal['strength'],
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'risk_reward_ratio': risk_reward_ratio,
                'market_strength': market_strength,
                'entry_score': entry_score,
                'indicators': {
                    'rsi': getattr(self, 'indicators', {}).get('rsi', pd.Series([50])).iloc[-1],
                    'macd': getattr(self, 'indicators', {}).get('macd', pd.Series([0])).iloc[-1],
                    'volume_ratio': df['volume'].iloc[-1] / df['volume'].rolling(20).mean().iloc[-1]
                },
                'timestamp': datetime.now()
            }
            
            symbol = signal['symbol']
            strategy_name = signal['strategy']
            self.logger.info(
                f"📈 Сигнал: {signal['type'].upper()} {symbol} | "
                f"Уверенность: {confidence:.1%} | "
                f"R/R: {risk_reward_ratio:.2f} | "
                f"Стратегия: {strategy_name}"
            )
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации сигнала: {e}")
            return None

    async def analyze_indicators(self, df: pd.DataFrame) -> list:
        """
        Базовый анализ индикаторов (заглушка для совместимости)
        Должен быть переопределен в дочерних классах
        """
        try:
            signals = []
            
            # Простая логика на основе RSI и MACD
            current_price = df['close'].iloc[-1]
            
            # Рассчитываем простые индикаторы
            rsi = self.calculate_simple_rsi(df['close'])
            macd_line, signal_line = self.calculate_simple_macd(df['close'])
            
            # Условия для BUY
            if rsi < 40 and macd_line > signal_line:
                signals.append({
                    'type': 'long',
                    'strength': 0.7,
                    'price': current_price,
                    'reason': 'RSI oversold + MACD bullish'
                })
            
            # Условия для SELL
            elif rsi > 60 and macd_line < signal_line:
                signals.append({
                    'type': 'short',
                    'strength': 0.7,
                    'price': current_price,
                    'reason': 'RSI overbought + MACD bearish'
                })
            
            return signals
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа индикаторов: {e}")
            return []

    def calculate_simple_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Простой расчет RSI"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1] if not rsi.empty else 50
        except:
            return 50

    def calculate_simple_macd(self, prices: pd.Series) -> tuple:
        """Простой расчет MACD"""
        try:
            exp1 = prices.ewm(span=12).mean()
            exp2 = prices.ewm(span=26).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9).mean()
            return macd.iloc[-1] if not macd.empty else 0, signal.iloc[-1] if not signal.empty else 0
        except:
            return 0, 0

    async def calculate_enhanced_indicators(self, df: pd.DataFrame) -> dict:
        """
        Расчет расширенного набора индикаторов
        """
        indicators = {}
        
        try:
            # Базовые индикаторы
            indicators['sma_20'] = df['close'].rolling(20).mean()
            indicators['sma_50'] = df['close'].rolling(50).mean()
            indicators['sma_200'] = df['close'].rolling(200).mean()
            indicators['ema_12'] = df['close'].ewm(span=12).mean()
            indicators['ema_26'] = df['close'].ewm(span=26).mean()
            
            # RSI
            indicators['rsi'] = self.calculate_rsi_series(df['close'])
            indicators['rsi_sma'] = indicators['rsi'].rolling(14).mean()
            
            # MACD
            indicators['macd'] = indicators['ema_12'] - indicators['ema_26']
            indicators['macd_signal'] = indicators['macd'].ewm(span=9).mean()
            indicators['macd_hist'] = indicators['macd'] - indicators['macd_signal']
            
            # Bollinger Bands
            bb_sma = df['close'].rolling(20).mean()
            bb_std = df['close'].rolling(20).std()
            indicators['bb_upper'] = bb_sma + (bb_std * 2)
            indicators['bb_lower'] = bb_sma - (bb_std * 2)
            indicators['bb_width'] = indicators['bb_upper'] - indicators['bb_lower']
            
            # ATR (Average True Range)
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            indicators['atr'] = true_range.rolling(14).mean()
            
            # Stochastic
            low_14 = df['low'].rolling(14).min()
            high_14 = df['high'].rolling(14).max()
            indicators['stoch_k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
            indicators['stoch_d'] = indicators['stoch_k'].rolling(3).mean()
            
            # Volume indicators
            indicators['volume_sma'] = df['volume'].rolling(20).mean()
            indicators['volume_ratio'] = df['volume'] / indicators['volume_sma']
            
            # OBV (On Balance Volume)
            obv = (df['volume'] * (~df['close'].diff().le(0) * 2 - 1)).cumsum()
            indicators['obv'] = obv
            indicators['obv_sma'] = obv.rolling(20).mean()
            
            # Сохраняем индикаторы в экземпляре класса
            self.indicators = indicators
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета индикаторов: {e}")
            
        return indicators

    def calculate_rsi_series(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Расчет RSI как Series"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.fillna(50)
        except:
            return pd.Series([50] * len(prices), index=prices.index)
    
    async def get_ml_signal(self, symbol: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Получение ML сигнала с обработкой ошибок
        
        Args:
            symbol: Торговая пара
            df: DataFrame с рыночными данными
            
        Returns:
            Словарь с ML предсказанием или None
        """
        if not self.use_ml:
            return None
        
        # Инициализируем ML если нужно
        await self._initialize_ml()
        
        if not self.ml_trainer:
            return None
        
        try:
            # Таймаут для ML предсказания
            prediction = await asyncio.wait_for(
                self.ml_trainer.predict(symbol, df),
                timeout=self.ml_timeout_seconds
            )
            
            self.ml_stats['predictions_made'] += 1
            
            if prediction.get('success') and prediction.get('confidence', 0) >= self.ml_min_confidence:
                self.ml_stats['successful_predictions'] += 1
                
                # Преобразуем ML направления в торговые действия
                direction_map = {
                    'UP': 'BUY',
                    'BUY': 'BUY',
                    'DOWN': 'SELL', 
                    'SELL': 'SELL',
                    'SIDEWAYS': 'WAIT',
                    'HOLD': 'WAIT'
                }
                
                ml_direction = direction_map.get(prediction.get('direction', 'WAIT'), 'WAIT')
                
                return {
                    'direction': ml_direction,
                    'confidence': prediction.get('confidence', 0),
                    'ml_weight': self.ml_weight,
                    'probabilities': prediction.get('probabilities', {}),
                    'model_type': prediction.get('model_type', 'unknown'),
                    'prediction_raw': prediction
                }
            else:
                logger.debug(f"ML предсказание для {symbol} отклонено: низкая уверенность ({prediction.get('confidence', 0):.2f} < {self.ml_min_confidence})")
                return None
                
        except asyncio.TimeoutError:
            logger.warning(f"⏰ ML предсказание для {symbol} превысило таймаут ({self.ml_timeout_seconds}с)")
            self.ml_stats['failed_predictions'] += 1
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка ML предсказания для {symbol}: {e}")
            self.ml_stats['failed_predictions'] += 1
            return None
    
    def combine_signals(self, technical_signal: Dict[str, Any], 
                       ml_signal: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Умное комбинирование технического и ML сигналов
        
        Args:
            technical_signal: Технический сигнал
            ml_signal: ML сигнал (может быть None)
            
        Returns:
            Комбинированный сигнал
        """
        # Если нет ML сигнала, возвращаем технический
        if not ml_signal:
            return {
                **technical_signal,
                'source': 'technical_only',
                'ml_available': False
            }
        
        tech_direction = technical_signal.get('direction', 'WAIT')
        tech_confidence = technical_signal.get('confidence', 0)
        
        ml_direction = ml_signal.get('direction', 'WAIT')
        ml_confidence = ml_signal.get('confidence', 0)
        
        # Веса для комбинирования
        tech_weight = 1 - self.ml_weight
        ml_weight = self.ml_weight
        
        # Случай 1: Сигналы согласуются
        if tech_direction == ml_direction and tech_direction != 'WAIT':
            self.ml_stats['combined_signals'] += 1
            
            # Взвешенная уверенность с бонусом за согласованность
            combined_confidence = (
                tech_confidence * tech_weight + 
                ml_confidence * ml_weight
            ) * 1.15  # 15% бонус за согласованность
            
            # Ограничиваем максимальную уверенность
            combined_confidence = min(0.95, combined_confidence)
            
            return {
                **technical_signal,
                'direction': tech_direction,
                'confidence': combined_confidence,
                'source': 'combined_agreement',
                'ml_prediction': ml_signal,
                'agreement': True,
                'tech_confidence': tech_confidence,
                'ml_confidence': ml_confidence
            }
        
        # Случай 2: Противоречивые сигналы
        elif tech_direction != ml_direction:
            logger.debug(f"Противоречие сигналов: Техн={tech_direction}({tech_confidence:.2f}) vs ML={ml_direction}({ml_confidence:.2f})")
            
            # Высокая уверенность ML при низкой технической
            if ml_confidence > 0.8 and tech_confidence < 0.6:
                self.ml_stats['ml_only_signals'] += 1
                return {
                    **technical_signal,
                    'direction': ml_direction,
                    'confidence': ml_confidence * 0.9,  # Небольшое снижение за противоречие
                    'source': 'ml_override',
                    'ml_prediction': ml_signal,
                    'agreement': False,
                    'override_reason': 'high_ml_confidence'
                }
            
            # Высокая техническая уверенность
            elif tech_confidence > 0.7:
                return {
                    **technical_signal,
                    'confidence': tech_confidence * 0.9,  # Небольшое снижение за противоречие
                    'source': 'technical_override',
                    'ml_prediction': ml_signal,
                    'agreement': False,
                    'override_reason': 'high_tech_confidence'
                }
            
            # Средняя уверенность - взвешенное решение
            else:
                if ml_confidence > tech_confidence:
                    chosen_direction = ml_direction
                    chosen_confidence = ml_confidence * 0.8
                    source = 'ml_weighted'
                else:
                    chosen_direction = tech_direction
                    chosen_confidence = tech_confidence * 0.8
                    source = 'technical_weighted'
                
                return {
                    **technical_signal,
                    'direction': chosen_direction,
                    'confidence': chosen_confidence,
                    'source': source,
                    'ml_prediction': ml_signal,
                    'agreement': False,
                    'resolution': 'confidence_based'
                }
        
        # Случай 3: Один из сигналов WAIT
        else:
            # Если технический WAIT, но ML дает сигнал
            if tech_direction == 'WAIT' and ml_direction != 'WAIT' and ml_confidence > 0.7:
                return {
                    **technical_signal,
                    'direction': ml_direction,
                    'confidence': ml_confidence * 0.8,
                    'source': 'ml_when_tech_wait',
                    'ml_prediction': ml_signal
                }
            
            # В остальных случаях используем технический
            return {
                **technical_signal,
                'source': 'technical_default',
                'ml_prediction': ml_signal
            }
    
    async def analyze_with_ml(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """
        Анализ с ML поддержкой - шаблонный метод
        
        Args:
            df: DataFrame с рыночными данными
            symbol: Торговая пара
            
        Returns:
            TradingSignal с учетом ML
        """
        # Валидация данных
        if not self.validate_dataframe(df):
            return TradingSignal(action='WAIT', confidence=0.0, price=df['close'].iloc[-1], reason="Invalid data")
        
        # Получаем технический сигнал (основной метод стратегии)
        technical_signal_obj = await self.analyze(df, symbol)
        
        # Преобразуем в словарь для обработки
        technical_signal = {
            'direction': technical_signal_obj.action,
            'confidence': technical_signal_obj.confidence,
            'price': technical_signal_obj.price,
            'stop_loss': technical_signal_obj.stop_loss,
            'take_profit': technical_signal_obj.take_profit,
            'reason': technical_signal_obj.reason,
            'risk_reward_ratio': technical_signal_obj.risk_reward_ratio,
            'indicators': technical_signal_obj.indicators
        }
        
        # Получаем ML сигнал
        ml_signal = await self.get_ml_signal(symbol, df) if self.use_ml else None
        
        # Комбинируем сигналы
        combined_signal = self.combine_signals(technical_signal, ml_signal)
        
        # Возвращаем обновленный TradingSignal
        return TradingSignal(
            action=combined_signal.get('direction', 'WAIT'),
            confidence=combined_signal.get('confidence', 0.0),
            price=combined_signal.get('price', df['close'].iloc[-1]),
            stop_loss=combined_signal.get('stop_loss'),
            take_profit=combined_signal.get('take_profit'),
            reason=self._format_combined_reason(combined_signal),
            risk_reward_ratio=combined_signal.get('risk_reward_ratio'),
            indicators=combined_signal.get('indicators'),
            ml_prediction=combined_signal.get('ml_prediction'),
            source=combined_signal.get('source', 'technical')
        )
    
    def _format_combined_reason(self, combined_signal: Dict) -> str:
        """Форматирование причины комбинированного сигнала"""
        base_reason = combined_signal.get('reason', '')
        source = combined_signal.get('source', 'technical')
        
        if source == 'combined_agreement':
            return f"{base_reason} + ML согласуется (conf: {combined_signal.get('ml_confidence', 0):.2f})"
        elif source == 'ml_override':
            return f"ML override: {combined_signal.get('override_reason', '')} (ML conf: {combined_signal.get('ml_confidence', 0):.2f})"
        elif source == 'technical_override':
            return f"{base_reason} (техн. анализ приоритет)"
        elif source == 'ml_when_tech_wait':
            return f"ML сигнал при ожидании (ML conf: {combined_signal.get('ml_confidence', 0):.2f})"
        else:
            return base_reason
    
    def validate_dataframe(self, df: pd.DataFrame) -> bool:
        """Валидация DataFrame с проверкой на реальные данные"""
        if df.empty or len(df) < self.min_periods:
            return False
        
        # Проверка на моковые данные
        if self._is_mock_data(df):
            logger.warning("Обнаружены моковые данные, пропускаем анализ")
            return False
        
        return True
    
    def _is_mock_data(self, df: pd.DataFrame) -> bool:
        """Проверка на моковые данные"""
        if len(df) < 10:
            return True
        
        # Если стандартное отклонение очень маленькое - возможно моковые данные
        if df['close'].std() < 0.01:
            return True
        
        # Если все цены одинаковые
        if df['close'].nunique() == 1:
            return True
        
        return False
    
    def calculate_stop_loss(self, price: float, action: str, atr: float,
                          multiplier: Optional[float] = None) -> float:
        """
        Расчет уровня стоп-лосса на основе ATR
        
        Args:
            price: Цена входа
            action: Направление (BUY/SELL)
            atr: Average True Range
            multiplier: Множитель ATR
            
        Returns:
            Уровень стоп-лосса
        """
        if multiplier is None:
            multiplier = self.atr_multiplier_stop
            
        if action.upper() == 'BUY':
            return max(0, price - (atr * multiplier))
        else:  # SELL
            return price + (atr * multiplier)
    
    def calculate_take_profit(self, price: float, action: str, atr: float,
                            multiplier: Optional[float] = None) -> float:
        """
        Расчет уровня take-profit на основе ATR
        
        Args:
            price: Цена входа
            action: Направление (BUY/SELL)
            atr: Average True Range
            multiplier: Множитель ATR
            
        Returns:
            Уровень take-profit
        """
        if multiplier is None:
            multiplier = self.atr_multiplier_take
            
        if action.upper() == 'BUY':
            return price + (atr * multiplier)
        else:  # SELL
            return max(0, price - (atr * multiplier))
    
    def calculate_risk_reward(self, entry_price: float, stop_loss: float, 
                            take_profit: float) -> float:
        """
        Расчет соотношения риск/прибыль
        
        Args:
            entry_price: Цена входа
            stop_loss: Уровень стоп-лосса
            take_profit: Уровень тейк-профита
            
        Returns:
            Соотношение риск/прибыль
        """
        try:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            
            if risk == 0:
                return 0.0
                
            return reward / risk
            
        except (ZeroDivisionError, TypeError):
            return 0.0
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """
        Получение информации о стратегии включая ML статистику
        
        Returns:
            Словарь с информацией о стратегии
        """
        info = {
            'name': self.name,
            'class': self.__class__.__name__,
            'timeframe': self.timeframe,
            'risk_percent': self.risk_percent,
            'max_positions': self.max_positions,
            'min_periods': self.min_periods,
            'config': self.config,
            'ml_enabled': self.use_ml,
            'ml_initialized': self._ml_initialized,
            'ml_weight': self.ml_weight,
            'ml_min_confidence': self.ml_min_confidence,
            'ml_stats': self.ml_stats.copy()
        }
        
        # Добавляем ML эффективность
        total_predictions = self.ml_stats['predictions_made']
        if total_predictions > 0:
            info['ml_success_rate'] = self.ml_stats['successful_predictions'] / total_predictions
        else:
            info['ml_success_rate'] = 0.0
            
        return info
    
    def get_ml_stats(self) -> Dict[str, Any]:
        """Получение детальной статистики ML"""
        total = self.ml_stats['predictions_made']
        return {
            **self.ml_stats,
            'success_rate': self.ml_stats['successful_predictions'] / total if total > 0 else 0,
            'failure_rate': self.ml_stats['failed_predictions'] / total if total > 0 else 0,
            'ml_enabled': self.use_ml,
            'ml_weight': self.ml_weight
        }
    
    def reset_ml_stats(self):
        """Сброс статистики ML"""
        self.ml_stats = {
            'predictions_made': 0,
            'successful_predictions': 0,
            'failed_predictions': 0,
            'combined_signals': 0,
            'ml_only_signals': 0
        }
        logger.info(f"ML статистика сброшена для стратегии {self.name}")
    
    def update_config(self, new_config: Dict[str, Any]):
        """
        Обновление конфигурации стратегии включая ML параметры
        
        Args:
            new_config: Новая конфигурация
        """
        old_ml_config = {
            'use_ml': self.use_ml,
            'ml_weight': self.ml_weight,
            'ml_min_confidence': self.ml_min_confidence
        }
        
        self.config.update(new_config)
        
        # Обновляем основные параметры
        self.timeframe = self.config.get('timeframe', self.timeframe)
        self.risk_percent = self.config.get('risk_percent', self.risk_percent)
        self.max_positions = self.config.get('max_positions', self.max_positions)
        self.atr_multiplier_stop = self.config.get('atr_multiplier_stop', self.atr_multiplier_stop)
        self.atr_multiplier_take = self.config.get('atr_multiplier_take', self.atr_multiplier_take)
        self.min_periods = self.config.get('min_periods', self.min_periods)
        
        # Обновляем ML параметры
        self.use_ml = self.config.get('use_ml', self.use_ml)
        self.ml_weight = self.config.get('ml_weight', self.ml_weight)
        self.ml_min_confidence = self.config.get('ml_min_confidence', self.ml_min_confidence)
        self.ml_timeout_seconds = self.config.get('ml_timeout_seconds', self.ml_timeout_seconds)
        
        # Переинициализируем ML если настройки изменились
        new_ml_config = {
            'use_ml': self.use_ml,
            'ml_weight': self.ml_weight,
            'ml_min_confidence': self.ml_min_confidence
        }
        
        if old_ml_config != new_ml_config:
            self._ml_initialized = False
            logger.info(f"ML конфигурация изменена для стратегии {self.name}, требуется переинициализация")
        
        logger.info(f"✅ Конфигурация стратегии {self.name} обновлена")
    
    def __str__(self) -> str:
        """Строковое представление стратегии"""
        ml_status = "ML+" if self.use_ml else "ML-"
        return f"Strategy(name={self.name}, timeframe={self.timeframe}, {ml_status})"
    
    def __repr__(self) -> str:
        """Подробное строковое представление"""
        return f"<{self.__class__.__name__}(name='{self.name}', ml_enabled={self.use_ml}, config={self.config})>"
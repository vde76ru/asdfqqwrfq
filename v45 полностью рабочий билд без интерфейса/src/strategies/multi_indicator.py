"""
Мульти-индикаторная стратегия
Путь: /var/www/www-root/data/www/systemetech.ru/src/strategies/multi_indicator.py
"""
import pandas as pd
import numpy as np
from typing import Dict  # ✅ ИСПРАВЛЕНО: один импорт Dict
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator
import logging

from .base import BaseStrategy
from ..common.types import UnifiedTradingSignal as TradingSignal, SignalAction

logger = logging.getLogger(__name__)

class MultiIndicatorStrategy(BaseStrategy):
    """
    Продвинутая стратегия с множественными индикаторами
    Использует подтверждение от нескольких индикаторов
    """
    
    # ✅ УЛУЧШЕНИЕ: Константы для лучшей читаемости
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    STOCH_OVERSOLD = 20
    STOCH_OVERBOUGHT = 80
    ADX_TREND_THRESHOLD = 25
    VOLUME_RATIO_THRESHOLD = 1.5
    BB_LOWER_THRESHOLD = 0.2
    BB_UPPER_THRESHOLD = 0.8
    
    def __init__(self, strategy_name: str = "multi_indicator", config: Dict = None):
        """✅ ИСПРАВЛЕНО: Правильный конструктор для вашего BaseStrategy"""
        super().__init__(strategy_name, config)
        self.min_confidence = 0.65
        self.min_indicators_confirm = 3  # Минимум 3 индикатора должны подтвердить
        self.limited_mode = False  # ✅ ДОБАВЛЕНО: Инициализируем режим
    
    async def analyze(self, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """Комплексный анализ с множественными подтверждениями"""
        
        if not self.validate_dataframe(df):
            # ✅ ИСПРАВЛЕНО: Правильный формат для вашего TradingSignal
            return TradingSignal(
                symbol=symbol,
                action=SignalAction.WAIT,
                confidence=0.0,
                price=float(df['close'].iloc[-1]) if not df.empty else 0.0,
                reason='Недостаточно данных',
                strategy=self.name
            )
        
        try:
            # Рассчитываем все индикаторы
            indicators = self._calculate_indicators(df)
            
            # ✅ УЛУЧШЕНИЕ: Проверяем корректность индикаторов
            if not indicators:
                return TradingSignal(
                    symbol=symbol,
                    action=SignalAction.WAIT,
                    confidence=0.0,
                    price=float(df['close'].iloc[-1]),
                    reason='Ошибка расчета индикаторов',
                    strategy=self.name
                )
            
            # Анализируем сигналы от каждого индикатора
            signals = self._analyze_signals(indicators, df)
            
            # Принимаем решение на основе всех сигналов
            return self._make_decision(signals, indicators, df, symbol)
            
        except Exception as e:
            logger.error(f"Ошибка анализа {symbol}: {e}")
            return TradingSignal(
                symbol=symbol,
                action=SignalAction.WAIT,
                confidence=0.0,
                price=float(df['close'].iloc[-1]) if not df.empty else 0.0,
                reason=f'Ошибка анализа: {e}',
                strategy=self.name
            )
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """✅ ИСПРАВЛЕННЫЙ расчет индикаторов с учетом ограниченного режима"""
        indicators = {}
        data_length = len(df)
        
        try:
            # Базовые данные
            indicators['current_price'] = float(df['close'].iloc[-1])
            indicators['high'] = float(df['high'].iloc[-1]) 
            indicators['low'] = float(df['low'].iloc[-1])
            indicators['volume'] = float(df['volume'].iloc[-1])
            
            # RSI (требует минимум 14 периодов)
            if data_length >= 14:
                self._calculate_rsi_safely(df, indicators)
            else:
                indicators['rsi'] = 50.0  # Нейтральное значение
            
            # MACD (требует минимум 26 периодов)
            if data_length >= 26:
                self._calculate_macd_safely(df, indicators)
            else:
                indicators['macd'] = 0.0
                indicators['macd_signal'] = 0.0
                indicators['macd_diff'] = 0.0
            
            # Bollinger Bands (требует минимум 20 периодов)
            if data_length >= 20:
                self._calculate_bollinger_safely(df, indicators)
            else:
                price = indicators['current_price']
                indicators['bb_upper'] = price * 1.02
                indicators['bb_lower'] = price * 0.98
                indicators['bb_middle'] = price
                indicators['bb_percent'] = 0.5
            
            # ✅ ATR (ДОБАВЛЕНО)
            if data_length >= 14:
                self._calculate_atr_safely(df, indicators)
            else:
                indicators['atr'] = indicators['current_price'] * 0.02  # 2% от цены
            
            # EMA (адаптивные периоды)
            self._calculate_ema_adaptive(df, indicators, data_length)
            
            # ADX (требует минимум 14 периодов) 
            if data_length >= 14:
                self._calculate_adx_safely(df, indicators)
            else:
                indicators['adx'] = 25.0  # Нейтральное значение
                indicators['adx_pos'] = 25.0
                indicators['adx_neg'] = 25.0
            
            # Volume и Stochastic
            self._calculate_volume_safely(df, indicators)
            self._calculate_stochastic_safely(df, indicators)
            
            return indicators
            
        except Exception as e:
            logger.error(f"Критическая ошибка расчета индикаторов: {e}")
            return {}

    # ✅ ДОБАВЛЕННЫЕ НЕДОСТАЮЩИЕ МЕТОДЫ
    
    def _calculate_rsi_safely(self, df: pd.DataFrame, indicators: Dict):
        """✅ НОВЫЙ: Безопасный расчет RSI"""
        try:
            if len(df) >= 14:
                rsi_indicator = RSIIndicator(df['close'], window=14)
                rsi_values = rsi_indicator.rsi()
                indicators['rsi'] = rsi_values.iloc[-1] if not rsi_values.empty else 50.0
            else:
                indicators['rsi'] = 50.0
        except Exception as e:
            logger.error(f"Ошибка расчета RSI: {e}")
            indicators['rsi'] = 50.0

    def _calculate_macd_safely(self, df: pd.DataFrame, indicators: Dict):
        """✅ НОВЫЙ: Безопасный расчет MACD"""
        try:
            if len(df) >= 26:
                macd_indicator = MACD(df['close'])
                macd_line = macd_indicator.macd()
                macd_signal_line = macd_indicator.macd_signal()
                macd_diff = macd_indicator.macd_diff()
                
                indicators['macd'] = macd_line.iloc[-1] if not macd_line.empty else 0.0
                indicators['macd_signal'] = macd_signal_line.iloc[-1] if not macd_signal_line.empty else 0.0
                indicators['macd_diff'] = macd_diff.iloc[-1] if not macd_diff.empty else 0.0
            else:
                indicators['macd'] = 0.0
                indicators['macd_signal'] = 0.0
                indicators['macd_diff'] = 0.0
        except Exception as e:
            logger.error(f"Ошибка расчета MACD: {e}")
            indicators['macd'] = 0.0
            indicators['macd_signal'] = 0.0
            indicators['macd_diff'] = 0.0

    def _calculate_bollinger_safely(self, df: pd.DataFrame, indicators: Dict):
        """✅ НОВЫЙ: Безопасный расчет Bollinger Bands"""
        try:
            if len(df) >= 20:
                bb_indicator = BollingerBands(df['close'], window=20, window_dev=2)
                bb_upper = bb_indicator.bollinger_hband()
                bb_lower = bb_indicator.bollinger_lband()
                bb_middle = bb_indicator.bollinger_mavg()
                bb_percent = bb_indicator.bollinger_pband()
                
                indicators['bb_upper'] = bb_upper.iloc[-1] if not bb_upper.empty else indicators['current_price'] * 1.02
                indicators['bb_lower'] = bb_lower.iloc[-1] if not bb_lower.empty else indicators['current_price'] * 0.98
                indicators['bb_middle'] = bb_middle.iloc[-1] if not bb_middle.empty else indicators['current_price']
                indicators['bb_percent'] = bb_percent.iloc[-1] if not bb_percent.empty else 0.5
            else:
                price = indicators['current_price']
                indicators['bb_upper'] = price * 1.02
                indicators['bb_lower'] = price * 0.98
                indicators['bb_middle'] = price
                indicators['bb_percent'] = 0.5
        except Exception as e:
            logger.error(f"Ошибка расчета Bollinger Bands: {e}")
            price = indicators['current_price']
            indicators['bb_upper'] = price * 1.02
            indicators['bb_lower'] = price * 0.98
            indicators['bb_middle'] = price
            indicators['bb_percent'] = 0.5

    def _calculate_atr_safely(self, df: pd.DataFrame, indicators: Dict):
        """✅ НОВЫЙ: Безопасный расчет ATR"""
        try:
            if len(df) >= 14:
                atr_indicator = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
                atr_values = atr_indicator.average_true_range()
                indicators['atr'] = atr_values.iloc[-1] if not atr_values.empty else indicators['current_price'] * 0.02
            else:
                indicators['atr'] = indicators['current_price'] * 0.02  # 2% от цены
        except Exception as e:
            logger.error(f"Ошибка расчета ATR: {e}")
            indicators['atr'] = indicators['current_price'] * 0.02

    def calculate_stop_loss(self, price: float, action: SignalAction, atr: float) -> float:
        """✅ НОВЫЙ: Расчет уровня стоп-лосса"""
        try:
            # Используем ATR для динамического стоп-лосса
            atr_multiplier = 2.0  # 2 ATR для стоп-лосса
            
            if action == SignalAction.BUY:
                return price - (atr * atr_multiplier)
            else:  # SELL
                return price + (atr * atr_multiplier)
        except Exception as e:
            logger.error(f"Ошибка расчета stop_loss: {e}")
            # Fallback: 2% от цены
            if action == SignalAction.BUY:
                return price * 0.98
            else:
                return price * 1.02

    def calculate_take_profit(self, price: float, action: SignalAction, atr: float) -> float:
        """✅ НОВЫЙ: Расчет уровня тейк-профита"""
        try:
            # Используем ATR для динамического тейк-профита
            atr_multiplier = 3.0  # 3 ATR для тейк-профита (R:R = 1.5:1)
            
            if action == SignalAction.BUY:
                return price + (atr * atr_multiplier)
            else:  # SELL
                return price - (atr * atr_multiplier)
        except Exception as e:
            logger.error(f"Ошибка расчета take_profit: {e}")
            # Fallback: 4% от цены
            if action == SignalAction.BUY:
                return price * 1.04
            else:
                return price * 0.96
            
    def _calculate_ema_adaptive(self, df: pd.DataFrame, indicators: Dict, data_length: int):
        """✅ НОВЫЙ: Адаптивный расчет EMA в зависимости от количества данных"""
        try:
            # Выбираем периоды в зависимости от доступных данных
            if data_length >= 200:
                # Полный набор
                periods = [9, 21, 50, 200]
            elif data_length >= 50:
                # Сокращенный набор
                periods = [9, 21, 50]
            else:
                # Минимальный набор
                periods = [9, min(21, data_length - 1)]
            
            for period in periods:
                if data_length > period:
                    ema = EMAIndicator(df['close'], window=period)
                    indicators[f'ema_{period}'] = float(ema.ema_indicator().iloc[-1])
                else:
                    # Если недостаточно данных, используем простое среднее
                    indicators[f'ema_{period}'] = float(df['close'].tail(min(period, data_length)).mean())
                    
        except Exception as e:
            logger.error(f"Ошибка расчета EMA: {e}")
            # Устанавливаем безопасные значения
            price = indicators.get('current_price', df['close'].iloc[-1])
            for period in [9, 21, 50, 200]:
                indicators[f'ema_{period}'] = price
    
    def _calculate_adx_safely(self, df: pd.DataFrame, indicators: Dict):
        """✅ ИСПРАВЛЕННЫЙ: Безопасный расчет ADX с правильной проверкой данных"""
        try:
            data_length = len(df)
            
            # ADX требует минимум 14 периодов для расчета + еще данные для сглаживания
            # Увеличиваем минимальное требование до 30 периодов для надежности
            if data_length >= 30:
                adx_indicator = ADXIndicator(df['high'], df['low'], df['close'], window=14)
                
                # Получаем значения индикаторов
                adx_values = adx_indicator.adx()
                adx_pos_values = adx_indicator.adx_pos()
                adx_neg_values = adx_indicator.adx_neg()
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем что результаты не пустые и имеют достаточно данных
                if (not adx_values.empty and len(adx_values) > 0 and 
                    not adx_pos_values.empty and len(adx_pos_values) > 0 and 
                    not adx_neg_values.empty and len(adx_neg_values) > 0):
                    
                    # Берем последнее валидное значение, проверяя на NaN
                    last_adx = adx_values.iloc[-1]
                    last_adx_pos = adx_pos_values.iloc[-1]
                    last_adx_neg = adx_neg_values.iloc[-1]
                    
                    # Проверяем что значения не NaN
                    indicators['adx'] = float(last_adx) if not pd.isna(last_adx) else 25.0
                    indicators['adx_pos'] = float(last_adx_pos) if not pd.isna(last_adx_pos) else 25.0
                    indicators['adx_neg'] = float(last_adx_neg) if not pd.isna(last_adx_neg) else 25.0
                    
                    logger.debug(f"ADX рассчитан: ADX={indicators['adx']:.2f}, +DI={indicators['adx_pos']:.2f}, -DI={indicators['adx_neg']:.2f}")
                else:
                    # Если результаты пустые
                    logger.warning(f"ADX вернул пустые результаты для {data_length} свечей")
                    indicators['adx'] = 25.0
                    indicators['adx_pos'] = 25.0
                    indicators['adx_neg'] = 25.0
            else:
                # Недостаточно данных для расчета ADX
                logger.debug(f"Недостаточно данных для ADX: {data_length} < 30")
                indicators['adx'] = 25.0  # Нейтральное значение
                indicators['adx_pos'] = 25.0
                indicators['adx_neg'] = 25.0
                
        except Exception as e:
            logger.error(f"Ошибка расчета ADX: {e}")
            # Устанавливаем безопасные значения по умолчанию
            indicators['adx'] = 25.0
            indicators['adx_pos'] = 25.0
            indicators['adx_neg'] = 25.0
    
    def _calculate_volume_safely(self, df: pd.DataFrame, indicators: Dict):
        """✅ НОВОЕ: Безопасный расчет объемных индикаторов"""
        try:
            if len(df) >= 20:
                volume_sma = df['volume'].rolling(window=20).mean()
                indicators['volume_sma'] = volume_sma.iloc[-1] if not volume_sma.empty else df['volume'].iloc[-1]
                
                if indicators['volume_sma'] > 0:
                    indicators['volume_ratio'] = df['volume'].iloc[-1] / indicators['volume_sma']
                else:
                    indicators['volume_ratio'] = 1.0
            else:
                indicators['volume_sma'] = df['volume'].mean()
                indicators['volume_ratio'] = 1.0
        except Exception as e:
            logger.error(f"Ошибка расчета объемных индикаторов: {e}")
            indicators['volume_sma'] = df['volume'].iloc[-1] if len(df) > 0 else 1.0
            indicators['volume_ratio'] = 1.0
    
    def _calculate_stochastic_safely(self, df: pd.DataFrame, indicators: Dict):
        """✅ НОВОЕ: Безопасный расчет Stochastic"""
        try:
            if len(df) >= 14:  # Stochastic требует минимум 14 периодов
                stoch = StochasticOscillator(df['high'], df['low'], df['close'])
                stoch_k_values = stoch.stoch()
                stoch_d_values = stoch.stoch_signal()
                
                indicators['stoch_k'] = stoch_k_values.iloc[-1] if not stoch_k_values.empty else 50.0
                indicators['stoch_d'] = stoch_d_values.iloc[-1] if not stoch_d_values.empty else 50.0
            else:
                indicators['stoch_k'] = 50.0
                indicators['stoch_d'] = 50.0
        except Exception as e:
            logger.error(f"Ошибка расчета Stochastic: {e}")
            indicators['stoch_k'] = 50.0
            indicators['stoch_d'] = 50.0
    
    def _analyze_signals(self, indicators: Dict, df: pd.DataFrame) -> Dict:
        """Анализ сигналов от каждого индикатора"""
        signals = {
            'buy_signals': [],
            'sell_signals': [],
            'neutral_signals': []
        }
        
        try:
            # RSI сигналы
            if indicators['rsi'] < self.RSI_OVERSOLD:
                signals['buy_signals'].append(('RSI', 'Перепроданность', 0.8))
            elif indicators['rsi'] > self.RSI_OVERBOUGHT:
                signals['sell_signals'].append(('RSI', 'Перекупленность', 0.8))
                
            # MACD сигналы
            if indicators['macd'] > indicators['macd_signal'] and indicators['macd_diff'] > 0:
                signals['buy_signals'].append(('MACD', 'Бычий пересечение + растущий гистограмма', 0.7))
            elif indicators['macd'] < indicators['macd_signal'] and indicators['macd_diff'] < 0:
                signals['sell_signals'].append(('MACD', 'Медвежий пересечение + падающий гистограмма', 0.7))
                
            # Bollinger Bands сигналы
            if indicators['bb_percent'] < self.BB_LOWER_THRESHOLD:  # Касание нижней полосы
                signals['buy_signals'].append(('BB', 'Касание нижней полосы', 0.6))
            elif indicators['bb_percent'] > self.BB_UPPER_THRESHOLD:  # Касание верхней полосы  
                signals['sell_signals'].append(('BB', 'Касание верхней полосы', 0.6))
                
            # EMA тренд
            if (indicators.get('ema_9', 0) > indicators.get('ema_21', 0) > indicators.get('ema_50', 0) and 
                indicators['current_price'] > indicators.get('ema_9', 0)):
                signals['buy_signals'].append(('EMA', 'Восходящий тренд', 0.7))
            elif (indicators.get('ema_9', 0) < indicators.get('ema_21', 0) < indicators.get('ema_50', 0) and 
                  indicators['current_price'] < indicators.get('ema_9', 0)):
                signals['sell_signals'].append(('EMA', 'Нисходящий тренд', 0.7))
                
            # ADX сила тренда
            if indicators['adx'] > self.ADX_TREND_THRESHOLD:
                if indicators['adx_pos'] > indicators['adx_neg']:
                    signals['buy_signals'].append(('ADX', 'Сильный восходящий тренд', 0.6))
                else:
                    signals['sell_signals'].append(('ADX', 'Сильный нисходящий тренд', 0.6))
                    
            # Volume подтверждение
            if indicators['volume_ratio'] > self.VOLUME_RATIO_THRESHOLD:
                signals['neutral_signals'].append(('Volume', 'Высокий объем', 0.5))
                
            # Stochastic сигналы
            if indicators['stoch_k'] < self.STOCH_OVERSOLD and indicators['stoch_k'] > indicators['stoch_d']:
                signals['buy_signals'].append(('Stochastic', 'Перепроданность + пересечение', 0.6))
            elif indicators['stoch_k'] > self.STOCH_OVERBOUGHT and indicators['stoch_k'] < indicators['stoch_d']:
                signals['sell_signals'].append(('Stochastic', 'Перекупленность + пересечение', 0.6))
                
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка анализа сигналов: {e}")
            return signals
    
    def _make_decision(self, signals: Dict, indicators: Dict, df: pd.DataFrame, symbol: str) -> TradingSignal:
        """✅ ИСПРАВЛЕНО: Принятие решения для вашего формата TradingSignal"""
        try:
            buy_score = sum(signal[2] for signal in signals['buy_signals'])
            sell_score = sum(signal[2] for signal in signals['sell_signals'])
            
            buy_count = len(signals['buy_signals'])
            sell_count = len(signals['sell_signals'])
            
            current_price = indicators['current_price']
            atr = indicators['atr']
            
            # Проверяем минимальное количество подтверждений
            if buy_count >= self.min_indicators_confirm and buy_score > sell_score:
                # Расчет уровней
                stop_loss = self.calculate_stop_loss(current_price, SignalAction.BUY, atr)
                take_profit = self.calculate_take_profit(current_price, SignalAction.BUY, atr)
                
                confidence = min(buy_score / 5.0, 1.0)  # Нормализуем уверенность
                
                # Проверяем минимальную уверенность
                if confidence >= self.min_confidence:
                    reasons = [f"{signal[0]}: {signal[1]}" for signal in signals['buy_signals']]
                    reason = "BUY: " + "; ".join(reasons)
                    
                    return TradingSignal(
                        symbol=symbol,
                        action=SignalAction.BUY,
                        confidence=confidence,
                        price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=reason,
                        risk_reward_ratio=(take_profit - current_price) / (current_price - stop_loss),
                        indicators=indicators,
                        strategy=self.name
                    )
                    
            elif sell_count >= self.min_indicators_confirm and sell_score > buy_score:
                # Расчет уровней для SELL
                stop_loss = self.calculate_stop_loss(current_price, SignalAction.SELL, atr)
                take_profit = self.calculate_take_profit(current_price, SignalAction.SELL, atr)
                
                confidence = min(sell_score / 5.0, 1.0)
                
                if confidence >= self.min_confidence:
                    reasons = [f"{signal[0]}: {signal[1]}" for signal in signals['sell_signals']]
                    reason = "SELL: " + "; ".join(reasons)
                    
                    return TradingSignal(
                        symbol=symbol,
                        action=SignalAction.SELL,
                        confidence=confidence,
                        price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=reason,
                        risk_reward_ratio=(current_price - take_profit) / (stop_loss - current_price),
                        indicators=indicators,
                        strategy=self.name
                    )
            
            # Если нет четкого сигнала
            reason = f"WAIT: buy_signals={buy_count}, sell_signals={sell_count}, confidence={max(buy_score, sell_score):.2f}"
            return TradingSignal(
                symbol=symbol,
                action=SignalAction.WAIT,
                confidence=0.0,
                price=current_price,
                reason=reason,
                indicators=indicators,
                strategy=self.name
            )
            
        except Exception as e:
            logger.error(f"Ошибка принятия решения: {e}")
            return TradingSignal(
                symbol=symbol,
                action=SignalAction.WAIT,
                confidence=0.0,
                price=current_price if 'current_price' in indicators else 0.0,
                reason=f"Ошибка анализа: {e}",
                strategy=self.name
            )
            
    def validate_dataframe(self, df: pd.DataFrame) -> bool:
        """
        ✅ ИСПРАВЛЕННАЯ валидация данных с адаптивным подходом
        
        Проверяет корректность DataFrame и устанавливает режим работы:
        - < 20 свечей: критически мало данных, возвращает False
        - 20-49 свечей: ограниченный режим (только базовые индикаторы)
        - >= 50 свечей: полный режим (все индикаторы)
        """
        # 1. Проверка на None и пустоту
        if df is None or df.empty:
            logger.warning("DataFrame пустой или None")
            return False
        
        # 2. Проверка обязательных колонок
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.warning(f"Отсутствуют обязательные колонки: {missing_columns}")
            return False
        
        # 3. Проверка на NaN и некорректные значения
        if df[required_columns].isnull().any().any():
            logger.warning("Обнаружены пустые значения (NaN) в данных")
            # Пробуем очистить данные
            df_clean = df.dropna(subset=required_columns)
            if len(df_clean) < 10:
                logger.error("Слишком много NaN значений, недостаточно чистых данных")
                return False
            logger.info(f"Очищены данные: {len(df)} -> {len(df_clean)} строк")
        
        # 4. Проверка что цены положительные
        price_columns = ['open', 'high', 'low', 'close']
        if (df[price_columns] <= 0).any().any():
            logger.error("Обнаружены отрицательные или нулевые цены")
            return False
        
        # 5. Проверка логики OHLC (high >= low, etc.)
        try:
            invalid_ohlc = ~(
                (df['high'] >= df['low']) & 
                (df['high'] >= df['open']) & 
                (df['high'] >= df['close']) &
                (df['low'] <= df['open']) & 
                (df['low'] <= df['close'])
            )
            if invalid_ohlc.any():
                logger.warning(f"Обнаружены некорректные OHLC данные в {invalid_ohlc.sum()} строках")
        except Exception as e:
            logger.debug(f"Не удалось проверить логику OHLC: {e}")
        
        # 6. ✅ АДАПТИВНАЯ ПРОВЕРКА КОЛИЧЕСТВА ДАННЫХ
        data_length = len(df)
        
        # Пороговые значения
        CRITICAL_MIN = 20    # Абсолютный минимум
        FULL_MODE_MIN = 50   # Минимум для полного режима
        
        if data_length < CRITICAL_MIN:
            logger.warning(f"❌ Критически мало данных: {data_length} < {CRITICAL_MIN}")
            return False
            
        elif data_length < FULL_MODE_MIN:
            logger.info(f"⚠️ Ограниченный режим: {data_length} свечей (используем базовые индикаторы)")
            self.limited_mode = True
            
        else:
            logger.debug(f"✅ Полный режим: {data_length} свечей (все индикаторы доступны)")
            self.limited_mode = False
        
        # 7. Дополнительные проверки качества данных
        try:
            # Проверяем волатильность
            price_std = df['close'].std()
            price_mean = df['close'].mean()
            if price_mean > 0 and (price_std / price_mean) < 0.001:
                logger.warning(f"Очень низкая волатильность данных: {(price_std/price_mean)*100:.4f}%")
        except Exception as e:
            logger.debug(f"Дополнительные проверки качества не выполнены: {e}")
        
        # 8. Финальное подтверждение
        logger.debug(f"✅ Валидация пройдена: {data_length} свечей, режим: {'ограниченный' if getattr(self, 'limited_mode', False) else 'полный'}")
        return True
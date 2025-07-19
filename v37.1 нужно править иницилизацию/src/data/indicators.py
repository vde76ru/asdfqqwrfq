#!/usr/bin/env python3
"""
Унифицированный модуль технических индикаторов
Файл: src/data/indicators.py

Обеспечивает совместимость между различными библиотеками индикаторов
"""

import logging
import numpy as np
import pandas as pd
from typing import Union, Optional, Tuple, List

logger = logging.getLogger(__name__)

# Попытка импорта TA-Lib
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logger.warning("TA-Lib не установлен, используем альтернативные расчеты")

# Попытка импорта библиотеки ta
try:
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.trend import EMAIndicator, MACD, ADXIndicator, SMAIndicator
    from ta.volatility import BollingerBands, AverageTrueRange
    from ta.volume import OnBalanceVolumeIndicator
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logger.warning("Библиотека ta не установлена")


class UnifiedIndicators:
    """
    Унифицированный класс для расчета технических индикаторов
    Автоматически выбирает между TA-Lib и альтернативными реализациями
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UnifiedIndicators, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        logger.info(f"UnifiedIndicators инициализирован (TA-Lib: {TALIB_AVAILABLE}, ta: {TA_AVAILABLE})")
    
    # ===== MOMENTUM INDICATORS =====
    
    def RSI(self, close: Union[pd.Series, np.ndarray], timeperiod: int = 14) -> np.ndarray:
        """Relative Strength Index"""
        if TALIB_AVAILABLE and hasattr(talib, 'RSI'):
            return talib.RSI(close, timeperiod=timeperiod)
        elif TA_AVAILABLE:
            rsi = RSIIndicator(pd.Series(close), window=timeperiod)
            return rsi.rsi().fillna(50).values
        else:
            return self._calculate_rsi_manual(close, timeperiod)
    
    def STOCH(self, high: Union[pd.Series, np.ndarray], 
              low: Union[pd.Series, np.ndarray], 
              close: Union[pd.Series, np.ndarray],
              fastk_period: int = 5, slowk_period: int = 3, 
              slowd_period: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """Stochastic Oscillator"""
        if TALIB_AVAILABLE and hasattr(talib, 'STOCH'):
            return talib.STOCH(high, low, close, fastk_period, slowk_period, 
                             0, slowd_period, 0)
        elif TA_AVAILABLE:
            stoch = StochasticOscillator(pd.Series(high), pd.Series(low), 
                                       pd.Series(close), window=fastk_period,
                                       smooth_window=slowk_period)
            k = stoch.stoch().fillna(50).values
            d = stoch.stoch_signal().fillna(50).values
            return k, d
        else:
            return self._calculate_stoch_manual(high, low, close, fastk_period, 
                                              slowk_period, slowd_period)
    
    # ===== TREND INDICATORS =====
    
    def EMA(self, close: Union[pd.Series, np.ndarray], timeperiod: int = 30) -> np.ndarray:
        """Exponential Moving Average"""
        if TALIB_AVAILABLE and hasattr(talib, 'EMA'):
            return talib.EMA(close, timeperiod=timeperiod)
        elif TA_AVAILABLE:
            ema = EMAIndicator(pd.Series(close), window=timeperiod)
            return ema.ema_indicator().fillna(method='bfill').values
        else:
            return self._calculate_ema_manual(close, timeperiod)
    
    def SMA(self, close: Union[pd.Series, np.ndarray], timeperiod: int = 30) -> np.ndarray:
        """Simple Moving Average"""
        if TALIB_AVAILABLE and hasattr(talib, 'SMA'):
            return talib.SMA(close, timeperiod=timeperiod)
        elif TA_AVAILABLE:
            sma = SMAIndicator(pd.Series(close), window=timeperiod)
            return sma.sma_indicator().fillna(method='bfill').values
        else:
            return pd.Series(close).rolling(window=timeperiod).mean().fillna(method='bfill').values
    
    def MACD(self, close: Union[pd.Series, np.ndarray], 
             fastperiod: int = 12, slowperiod: int = 26, 
             signalperiod: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """MACD - Moving Average Convergence Divergence"""
        if TALIB_AVAILABLE and hasattr(talib, 'MACD'):
            return talib.MACD(close, fastperiod, slowperiod, signalperiod)
        elif TA_AVAILABLE:
            macd = MACD(pd.Series(close), window_slow=slowperiod, 
                       window_fast=fastperiod, window_sign=signalperiod)
            macd_line = macd.macd().fillna(0).values
            signal_line = macd.macd_signal().fillna(0).values
            histogram = macd.macd_diff().fillna(0).values
            return macd_line, signal_line, histogram
        else:
            return self._calculate_macd_manual(close, fastperiod, slowperiod, signalperiod)
    
    def ADX(self, high: Union[pd.Series, np.ndarray], 
            low: Union[pd.Series, np.ndarray], 
            close: Union[pd.Series, np.ndarray], 
            timeperiod: int = 14) -> np.ndarray:
        """Average Directional Movement Index"""
        if TALIB_AVAILABLE and hasattr(talib, 'ADX'):
            return talib.ADX(high, low, close, timeperiod=timeperiod)
        elif TA_AVAILABLE:
            adx = ADXIndicator(pd.Series(high), pd.Series(low), 
                             pd.Series(close), window=timeperiod)
            return adx.adx().fillna(25).values
        else:
            return np.full(len(close), 25.0)  # Default neutral value
    
    # ===== VOLATILITY INDICATORS =====
    
    def BBANDS(self, close: Union[pd.Series, np.ndarray], 
               timeperiod: int = 20, nbdevup: float = 2, 
               nbdevdn: float = 2) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Bollinger Bands"""
        if TALIB_AVAILABLE and hasattr(talib, 'BBANDS'):
            return talib.BBANDS(close, timeperiod, nbdevup, nbdevdn, 0)
        elif TA_AVAILABLE:
            bb = BollingerBands(pd.Series(close), window=timeperiod, 
                               window_dev=nbdevup)
            upper = bb.bollinger_hband().fillna(method='bfill').values
            middle = bb.bollinger_mavg().fillna(method='bfill').values
            lower = bb.bollinger_lband().fillna(method='bfill').values
            return upper, middle, lower
        else:
            return self._calculate_bbands_manual(close, timeperiod, nbdevup, nbdevdn)
    
    def ATR(self, high: Union[pd.Series, np.ndarray], 
            low: Union[pd.Series, np.ndarray], 
            close: Union[pd.Series, np.ndarray], 
            timeperiod: int = 14) -> np.ndarray:
        """Average True Range"""
        if TALIB_AVAILABLE and hasattr(talib, 'ATR'):
            return talib.ATR(high, low, close, timeperiod=timeperiod)
        elif TA_AVAILABLE:
            atr = AverageTrueRange(pd.Series(high), pd.Series(low), 
                                 pd.Series(close), window=timeperiod)
            return atr.average_true_range().fillna(0).values
        else:
            return self._calculate_atr_manual(high, low, close, timeperiod)
    
    # ===== VOLUME INDICATORS =====
    
    def OBV(self, close: Union[pd.Series, np.ndarray], 
            volume: Union[pd.Series, np.ndarray]) -> np.ndarray:
        """On Balance Volume"""
        if TALIB_AVAILABLE and hasattr(talib, 'OBV'):
            return talib.OBV(close, volume)
        elif TA_AVAILABLE:
            obv = OnBalanceVolumeIndicator(pd.Series(close), pd.Series(volume))
            return obv.on_balance_volume().fillna(0).values
        else:
            return self._calculate_obv_manual(close, volume)
    
    # ===== MANUAL CALCULATIONS =====
    
    def _calculate_rsi_manual(self, close: Union[pd.Series, np.ndarray], 
                            period: int = 14) -> np.ndarray:
        """Ручной расчет RSI"""
        closes = pd.Series(close)
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50).values
    
    def _calculate_ema_manual(self, data: Union[pd.Series, np.ndarray], 
                            period: int) -> np.ndarray:
        """Ручной расчет EMA"""
        return pd.Series(data).ewm(span=period, adjust=False).mean().values
    
    def _calculate_macd_manual(self, close: Union[pd.Series, np.ndarray],
                             fast: int = 12, slow: int = 26, 
                             signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Ручной расчет MACD"""
        closes = pd.Series(close)
        ema_fast = closes.ewm(span=fast, adjust=False).mean()
        ema_slow = closes.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line.values, signal_line.values, histogram.values
    
    def _calculate_bbands_manual(self, close: Union[pd.Series, np.ndarray],
                               period: int = 20, std_dev: float = 2,
                               std_dev_dn: float = 2) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Ручной расчет Bollinger Bands"""
        closes = pd.Series(close)
        middle = closes.rolling(window=period).mean()
        std = closes.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev_dn)
        return upper.values, middle.values, lower.values
    
    def _calculate_atr_manual(self, high: Union[pd.Series, np.ndarray],
                            low: Union[pd.Series, np.ndarray],
                            close: Union[pd.Series, np.ndarray],
                            period: int = 14) -> np.ndarray:
        """Ручной расчет ATR"""
        high_s = pd.Series(high)
        low_s = pd.Series(low)
        close_s = pd.Series(close)
        
        high_low = high_s - low_s
        high_close = np.abs(high_s - close_s.shift())
        low_close = np.abs(low_s - close_s.shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr.fillna(0).values
    
    def _calculate_stoch_manual(self, high: Union[pd.Series, np.ndarray],
                              low: Union[pd.Series, np.ndarray],
                              close: Union[pd.Series, np.ndarray],
                              fastk_period: int = 5, slowk_period: int = 3,
                              slowd_period: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """Ручной расчет Stochastic"""
        high_s = pd.Series(high)
        low_s = pd.Series(low)
        close_s = pd.Series(close)
        
        low_min = low_s.rolling(window=fastk_period).min()
        high_max = high_s.rolling(window=fastk_period).max()
        
        k_percent = 100 * ((close_s - low_min) / (high_max - low_min))
        k = k_percent.rolling(window=slowk_period).mean()
        d = k.rolling(window=slowd_period).mean()
        
        return k.fillna(50).values, d.fillna(50).values
    
    def _calculate_obv_manual(self, close: Union[pd.Series, np.ndarray],
                            volume: Union[pd.Series, np.ndarray]) -> np.ndarray:
        """Ручной расчет OBV"""
        closes = pd.Series(close)
        volumes = pd.Series(volume)
        
        obv = [0]
        for i in range(1, len(closes)):
            if closes.iloc[i] > closes.iloc[i-1]:
                obv.append(obv[-1] + volumes.iloc[i])
            elif closes.iloc[i] < closes.iloc[i-1]:
                obv.append(obv[-1] - volumes.iloc[i])
            else:
                obv.append(obv[-1])
        
        return np.array(obv)


# Создаем глобальный экземпляр
indicators = UnifiedIndicators()

# Экспорт для обратной совместимости
__all__ = ['UnifiedIndicators', 'indicators', 'TALIB_AVAILABLE', 'TA_AVAILABLE']
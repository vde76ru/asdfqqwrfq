"""
Анализ рынка и поиск торговых возможностей
Файл: src/bot/internal/market_analysis.py
"""

import asyncio
import logging
import numpy as np
import pandas as pd
import traceback
import time
import random
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

def get_market_analysis(bot_instance):
    """Возвращает объект с методами анализа рынка"""
    
    class MarketAnalysis:
        def __init__(self, bot):
            self.bot = bot
            
        async def analyze_market_conditions(self):
            """Анализ рыночных условий"""
            return await analyze_market_conditions(self.bot)
            
        async def determine_market_phase(self):
            """Определение рыночной фазы"""
            return await determine_market_phase(self.bot)
    
    return MarketAnalysis(bot_instance)

async def _update_market_data(bot_instance):
    """Обновление рыночных данных для всех торговых пар"""
    try:
        logger.debug("📊 Обновление рыночных данных...")
        
        updated_pairs = 0
        for symbol in bot_instance.active_pairs:
            try:
                # ✅ ИСПРАВЛЕНО: используем data_collector если он доступен
                if hasattr(bot_instance, 'data_collector') and bot_instance.data_collector:
                    # Собираем данные через data_collector
                    market_data = await bot_instance.data_collector.collect_market_data(symbol)
                    
                    # ✅ ИСПРАВЛЕНО: правильная проверка словаря
                    if market_data and isinstance(market_data, dict):
                        # Сохраняем candles в кэш если они есть
                        if 'candles' in market_data and market_data['candles']:
                            if symbol not in bot_instance.candle_cache:
                                bot_instance.candle_cache[symbol] = deque(maxlen=100)
                            
                            # Добавляем свечи в кэш
                            for candle in market_data['candles']:
                                bot_instance.candle_cache[symbol].append(candle)
                        
                        # Обновляем последнюю цену
                        if 'ticker' in market_data and market_data['ticker']:
                            last_price = float(market_data['ticker'].get('last', 0))
                            
                            if symbol not in bot_instance.price_history:
                                bot_instance.price_history[symbol] = deque(maxlen=100)
                            
                            bot_instance.price_history[symbol].append({
                                'price': last_price,
                                'volume': float(market_data['ticker'].get('volume', 0)),
                                'timestamp': datetime.utcnow()
                            })
                            
                            updated_pairs += 1
                            logger.debug(f"📈 {symbol}: ${last_price:.4f}")
                else:
                    # Fallback: получаем данные напрямую через exchange
                    if hasattr(bot_instance.exchange_client, 'get_klines'):
                        candles = await bot_instance.exchange_client.get_klines(
                            symbol=symbol,
                            interval='5m',
                            limit=50
                        )
                    elif hasattr(bot_instance.exchange_client, 'fetch_ohlcv'):
                        candles = await bot_instance.exchange_client.fetch_ohlcv(
                            symbol, '5m', limit=50
                        )
                    else:
                        logger.warning(f"⚠️ Метод получения свечей недоступен для {symbol}")
                        continue
                    
                    if candles and len(candles) > 0:
                        # Сохраняем данные в кэш
                        if symbol not in bot_instance.candle_cache:
                            bot_instance.candle_cache[symbol] = deque(maxlen=100)
                        
                        # Добавляем новые свечи
                        for candle in candles[-10:]:  # Последние 10 свечей
                            candle_data = {
                                'timestamp': candle[0] if isinstance(candle, list) else candle.get('timestamp'),
                                'open': float(candle[1] if isinstance(candle, list) else candle.get('open', 0)),
                                'high': float(candle[2] if isinstance(candle, list) else candle.get('high', 0)),
                                'low': float(candle[3] if isinstance(candle, list) else candle.get('low', 0)),
                                'close': float(candle[4] if isinstance(candle, list) else candle.get('close', 0)),
                                'volume': float(candle[5] if isinstance(candle, list) else candle.get('volume', 0))
                            }
                            bot_instance.candle_cache[symbol].append(candle_data)
                        
                        # Обновляем последнюю цену
                        last_candle = candles[-1]
                        last_price = float(last_candle[4] if isinstance(last_candle, list) else last_candle.get('close', 0))
                        
                        if symbol not in bot_instance.price_history:
                            bot_instance.price_history[symbol] = deque(maxlen=100)
                        
                        bot_instance.price_history[symbol].append({
                            'price': last_price,
                            'volume': float(last_candle[5] if isinstance(last_candle, list) else last_candle.get('volume', 0)),
                            'timestamp': datetime.utcnow()
                        })
                        
                        updated_pairs += 1
                        logger.debug(f"📈 {symbol}: ${last_price:.4f}")
                        
            except Exception as e:
                logger.error(f"❌ Ошибка обновления данных {symbol}: {e}")
        
        if updated_pairs > 0:
            logger.debug(f"✅ Обновлены данные для {updated_pairs}/{len(bot_instance.active_pairs)} пар")
        else:
            logger.warning("⚠️ Не удалось обновить данные ни для одной пары")
            
    except Exception as e:
        logger.error(f"❌ Ошибка обновления рыночных данных: {e}")
        logger.error(traceback.format_exc())

async def _update_market_data_for_symbol(bot_instance, symbol: str):
    """Обновление данных для одного символа"""
    try:
        if bot_instance.data_collector:
            # Используем data_collector
            market_data = await bot_instance.data_collector.collect_market_data(symbol)
            if market_data:
                # Сохраняем в кэш
                bot_instance.market_data_cache[symbol] = market_data
                return True
        else:
            # Прямое получение данных
            if hasattr(bot_instance.exchange_client, 'fetch_ticker'):
                ticker = await bot_instance.exchange_client.fetch_ticker(symbol)
                if ticker:
                    bot_instance.market_data_cache[symbol] = {
                        'price': ticker.get('last', 0),
                        'volume': ticker.get('volume', 0),
                        'timestamp': datetime.utcnow()
                    }
                    return True
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления данных для {symbol}: {e}")
        return False

async def _find_all_trading_opportunities(bot_instance):
    """Поиск торговых возможностей по всем парам и стратегиям"""
    opportunities = []
    
    try:
        logger.debug("🔍 Поиск торговых возможностей...")
        
        # Получаем фабрику стратегий
        strategy_factory = None
        if hasattr(bot_instance, 'strategy_factory'):
            strategy_factory = bot_instance.strategy_factory
        else:
            # Импортируем фабрику если не инициализирована
            try:
                from ...strategies import strategy_factory as sf
                strategy_factory = sf
            except ImportError:
                logger.error("❌ Не удалось импортировать фабрику стратегий")
                return opportunities
        
        for symbol in bot_instance.active_pairs:
            try:
                # Подготавливаем данные для анализа
                market_data = await _prepare_market_data(bot_instance, symbol)
                
                if not market_data or len(market_data.get('close', [])) < 20:
                    logger.debug(f"⚠️ Недостаточно данных для анализа {symbol}")
                    continue
                
                # Преобразуем в DataFrame
                df = _market_data_to_dataframe(bot_instance, market_data)
                
                # Анализируем всеми активными стратегиями
                active_strategies = getattr(bot_instance.config, 'ACTIVE_STRATEGIES', None)

                # Если нет ACTIVE_STRATEGIES, используем веса стратегий
                if active_strategies is None:
                    active_strategies = {}
                    
                    # Проверяем наличие весов в конфигурации
                    if hasattr(bot_instance.config, 'STRATEGY_WEIGHTS'):
                        strategy_weights_raw = bot_instance.config.STRATEGY_WEIGHTS
                        
                        # Если это строка, парсим её
                        if isinstance(strategy_weights_raw, str):
                            for pair in strategy_weights_raw.split(','):
                                if ':' in pair:
                                    name, weight = pair.strip().split(':')
                                    active_strategies[name.strip()] = float(weight)
                        elif isinstance(strategy_weights_raw, dict):
                            active_strategies = strategy_weights_raw
                    
                    # Если всё ещё пусто, используем значения по умолчанию
                    if not active_strategies:
                        active_strategies = {
                            'multi_indicator': 25.0,
                            'momentum': 20.0,
                            'mean_reversion': 15.0,
                            'breakout': 15.0,
                            'scalping': 10.0,
                            'swing': 10.0,
                            'whale_hunting': 15.0,
                            'sleeping_giants': 12.0,
                            'order_book_analysis': 10.0
                        }
                
                # Убеждаемся что это словарь
                if isinstance(active_strategies, str):
                    logger.warning(f"⚠️ ACTIVE_STRATEGIES является строкой: {active_strategies}")
                    # Пытаемся распарсить
                    parsed_strategies = {}
                    try:
                        import json
                        parsed_strategies = json.loads(active_strategies)
                    except:
                        # Если не JSON, пробуем как список
                        for strategy in active_strategies.split(','):
                            strategy = strategy.strip()
                            if strategy:
                                parsed_strategies[strategy] = 1.0
                    active_strategies = parsed_strategies
                
                logger.debug(f"📊 Активные стратегии: {list(active_strategies.keys())}")
                
                for strategy_name, weight in active_strategies.items():
                    if weight <= 0:
                        continue
                        
                    try:
                        # Создаем экземпляр стратегии
                        strategy = strategy_factory.create(strategy_name)
                        
                        # Анализируем
                        signal = await strategy.analyze(df, symbol)
                        
                        # Преобразуем TradingSignal в словарь
                        if signal and signal.action != 'WAIT' and signal.action != 'HOLD':
                            opportunity = {
                                'symbol': symbol,
                                'strategy': strategy_name,
                                'signal': signal.action,
                                'confidence': signal.confidence * (weight / 100.0),  # Учитываем вес стратегии
                                'price': signal.price if signal.price > 0 else float(market_data['close'][-1]),
                                'stop_loss': signal.stop_loss,
                                'take_profit': signal.take_profit,
                                'timestamp': datetime.utcnow(),
                                'reasons': [signal.reason] if signal.reason else [f'{strategy_name}_signal'],
                                'raw_confidence': signal.confidence,
                                'strategy_weight': weight
                            }
                            
                            # Проверяем минимальную уверенность
                            min_confidence = getattr(bot_instance.config, 'MIN_STRATEGY_CONFIDENCE', 0.65)
                            if signal.confidence >= min_confidence:
                                opportunities.append(opportunity)
                                logger.info(f"🎯 Найдена возможность: {symbol} {signal.action} от {strategy_name} (уверенность: {signal.confidence:.2f})")
                            
                    except Exception as e:
                        logger.debug(f"Ошибка анализа {symbol} стратегией {strategy_name}: {e}")
                        continue
                
                # ML анализ (если включен)
                if getattr(bot_instance.config, 'ENABLE_MACHINE_LEARNING', False) and hasattr(bot_instance, 'ml_system') and bot_instance.ml_system:
                    ml_signal = await _analyze_with_ml(bot_instance, symbol, df)
                    if ml_signal and ml_signal['confidence'] >= getattr(bot_instance.config, 'ML_PREDICTION_THRESHOLD', 0.7):
                        opportunities.append(ml_signal)
                        logger.info(f"🤖 ML сигнал: {symbol} {ml_signal['signal']} (уверенность: {ml_signal['confidence']:.2f})")
                        
            except Exception as e:
                logger.error(f"❌ Ошибка анализа {symbol}: {e}")
                continue
                
        logger.info(f"📊 Всего найдено {len(opportunities)} торговых возможностей")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка поиска возможностей: {e}")
        import traceback
        traceback.print_exc()
        
    return opportunities
    
def _market_data_to_dataframe(bot_instance, market_data):
    """Преобразование market_data в DataFrame для стратегий"""
    try:
        import pandas as pd
        
        # Если уже DataFrame - возвращаем как есть
        if isinstance(market_data, pd.DataFrame):
            return market_data
            
        # Преобразуем словарь в DataFrame
        df_data = {
            'open': market_data.get('open', []),
            'high': market_data.get('high', []),
            'low': market_data.get('low', []),
            'close': market_data.get('close', []),
            'volume': market_data.get('volume', [])
        }
        
        # Проверяем, что все массивы одинаковой длины
        lengths = [len(v) for v in df_data.values() if isinstance(v, list)]
        if lengths and all(l == lengths[0] for l in lengths):
            df = pd.DataFrame(df_data)
            
            # Добавляем временные метки если есть
            if 'timestamp' in market_data:
                df['timestamp'] = pd.to_datetime(market_data['timestamp'])
                df.set_index('timestamp', inplace=True)
                
            return df
        else:
            logger.error("Неодинаковая длина массивов данных")
            return None
            
    except Exception as e:
        logger.error(f"Ошибка преобразования данных в DataFrame: {e}")
        return None

async def _analyze_with_ml(bot_instance, symbol: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """✅ ИСПРАВЛЕНО: Анализ с использованием ML моделей"""
    try:
        if not hasattr(bot_instance, 'ml_system') or not bot_instance.ml_system:
            return None
        
        # Проверяем что ML включен в конфигурации
        if not getattr(bot_instance.config, 'ENABLE_MACHINE_LEARNING', False):
            return None
        
        # ✅ ИСПРАВЛЕНО: Правильное обращение к ML компонентам
        direction_prediction = None
        
        # Пробуем разные способы получения предсказания
        try:
            # Способ 1: Через trainer (если есть)
            if hasattr(bot_instance.ml_system, 'trainer') and bot_instance.ml_system.trainer:
                if hasattr(bot_instance.ml_system.trainer, 'predict_direction'):
                    direction_prediction = await bot_instance.ml_system.trainer.predict_direction(symbol, df)
                elif hasattr(bot_instance.ml_system.trainer, 'predict'):
                    direction_prediction = await bot_instance.ml_system.trainer.predict(symbol, df)
            
            # Способ 2: Через direction_classifier (если trainer не сработал)
            if not direction_prediction and hasattr(bot_instance.ml_system, 'direction_classifier'):
                if hasattr(bot_instance.ml_system.direction_classifier, 'predict'):
                    # Подготавливаем признаки
                    features = bot_instance.ml_system.feature_engineer.create_features(df, symbol) if hasattr(bot_instance.ml_system, 'feature_engineer') else df
                    
                    # Получаем предсказание
                    prediction_result = bot_instance.ml_system.direction_classifier.predict(features)
                    
                    if 'error' not in prediction_result:
                        # Преобразуем в нужный формат
                        direction_prediction = {
                            'direction': prediction_result.get('direction_labels', ['HOLD'])[-1] if prediction_result.get('direction_labels') else 'HOLD',
                            'confidence': prediction_result.get('confidence', [0.5])[-1] if prediction_result.get('confidence') else 0.5,
                            'features': {},
                            'model_type': 'direction_classifier'
                        }
            
            # Способ 3: Создаем заглушку, если ничего не получилось
            if not direction_prediction:
                logger.warning("⚠️ ML модели недоступны, используем заглушку")
                direction_prediction = {
                    'direction': 'HOLD',
                    'confidence': 0.3,  # Низкая уверенность для заглушки
                    'features': {},
                    'model_type': 'fallback'
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения ML предсказания: {e}")
            return None
        
        # Проверяем минимальную уверенность
        min_confidence = getattr(bot_instance.config, 'ML_PREDICTION_THRESHOLD', 0.7)
        if direction_prediction.get('confidence', 0) < min_confidence:
            logger.debug(f"🤖 ML предсказание отклонено: уверенность {direction_prediction.get('confidence', 0):.2f} < {min_confidence}")
            return None
            
        # ✅ ИСПРАВЛЕНО: Получение price_prediction
        price_prediction = {
            'support': df['close'].iloc[-1] * 0.98, 
            'resistance': df['close'].iloc[-1] * 1.02,
            'confidence': 0.5
        }
        
        try:
            if hasattr(bot_instance.ml_system, 'price_regressor'):
                # Здесь можно добавить реальное предсказание цены
                pass
        except Exception as e:
            logger.warning(f"⚠️ Ошибка price_prediction: {e}")
        
        # ✅ ИСПРАВЛЕНО: Получение RL recommendation  
        rl_recommendation = None
        try:
            if hasattr(bot_instance.ml_system, 'rl_agent') and bot_instance.ml_system.rl_agent:
                # Здесь можно добавить RL предсказание
                pass
        except Exception as e:
            logger.warning(f"⚠️ Ошибка RL recommendation: {e}")
        
        # Формируем торговый сигнал
        ml_signal = {
            'symbol': symbol,
            'signal': direction_prediction.get('direction', 'HOLD'),
            'price': df['close'].iloc[-1],
            'confidence': direction_prediction['confidence'],
            'stop_loss': price_prediction.get('support', df['close'].iloc[-1] * 0.98),
            'take_profit': price_prediction.get('resistance', df['close'].iloc[-1] * 1.02),
            'strategy': 'ml_prediction',
            'ml_features': direction_prediction.get('features', {}),
            'price_targets': price_prediction.get('targets', {}),
            'rl_action': rl_recommendation.get('action') if rl_recommendation else None,
            'indicators': {
                'ml_direction_confidence': direction_prediction['confidence'],
                'ml_price_confidence': price_prediction.get('confidence', 0),
                'feature_importance': direction_prediction.get('feature_importance', {}),
                'model_type': direction_prediction.get('model_type', 'ensemble')
            }
        }
        
        logger.debug(f"🤖 ML сигнал для {symbol}: {ml_signal['signal']} (уверенность: {ml_signal['confidence']:.2f})")
        return ml_signal
        
    except Exception as e:
        logger.error(f"❌ Ошибка ML анализа для {symbol}: {e}")
        return None

def _calculate_rsi(bot_instance, prices: pd.Series, period: int = 14) -> pd.Series:
    """Расчет RSI"""
    try:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)
    except:
        return pd.Series([50] * len(prices))

def _calculate_macd(bot_instance, prices: pd.Series) -> pd.Series:
    """Расчет MACD"""
    try:
        exp1 = prices.ewm(span=12).mean()
        exp2 = prices.ewm(span=26).mean()
        macd = exp1 - exp2
        return macd.fillna(0)
    except:
        return pd.Series([0] * len(prices))

def _calculate_bb_position(bot_instance, prices: pd.Series, period: int = 20) -> pd.Series:
    """Расчет позиции относительно полос Боллинджера"""
    try:
        rolling_mean = prices.rolling(window=period).mean()
        rolling_std = prices.rolling(window=period).std()
        upper_band = rolling_mean + (rolling_std * 2)
        lower_band = rolling_mean - (rolling_std * 2)
        bb_position = (prices - lower_band) / (upper_band - lower_band)
        return bb_position.fillna(0.5)
    except:
        return pd.Series([0.5] * len(prices))

async def _analyze_with_basic_strategy(bot_instance, symbol: str, market_data: dict):
    """Базовый анализ для поиска сигналов - УЛУЧШЕННАЯ ВЕРСИЯ"""
    try:
        closes = market_data.get('close', [])
        volumes = market_data.get('volume', [])
        
        if len(closes) < 20:
            return None
        
        # Преобразуем в numpy arrays для быстрых вычислений
        import numpy as np
        closes = np.array(closes[-50:])  # Последние 50 свечей
        volumes = np.array(volumes[-50:])
        
        # Рассчитываем индикаторы
        sma_20 = np.mean(closes[-20:])
        sma_10 = np.mean(closes[-10:])
        sma_5 = np.mean(closes[-5:])
        current_price = closes[-1]
        
        # RSI
        rsi = _calculate_rsi_value(bot_instance, closes, 14)
        
        # Объем
        volume_avg = np.mean(volumes[-20:])
        current_volume = volumes[-1]
        volume_ratio = current_volume / volume_avg if volume_avg > 0 else 1
        
        # MACD
        exp1 = pd.Series(closes).ewm(span=12).mean()
        exp2 = pd.Series(closes).ewm(span=26).mean()
        macd = exp1.iloc[-1] - exp2.iloc[-1]
        signal_line = (exp1 - exp2).ewm(span=9).mean().iloc[-1]
        macd_histogram = macd - signal_line
        
        # Изменение цены
        price_change_5 = (current_price - closes[-5]) / closes[-5] * 100
        price_change_10 = (current_price - closes[-10]) / closes[-10] * 100
        
        # === УЛУЧШЕННЫЕ УСЛОВИЯ ДЛЯ СИГНАЛОВ ===
        
        # BUY сигналы (менее строгие условия)
        buy_signals = 0
        
        # 1. Пересечение MA снизу вверх
        if sma_5 > sma_10 and closes[-2] < np.mean(closes[-11:-1]):
            buy_signals += 1
            
        # 2. RSI выходит из перепроданности
        if 25 < rsi < 45:  # Расширенный диапазон
            buy_signals += 1
            
        # 3. MACD пересекает сигнальную линию снизу вверх
        if macd_histogram > 0 and macd > signal_line * 0.95:  # Менее строгое условие
            buy_signals += 1
            
        # 4. Увеличение объема
        if volume_ratio > 1.2:  # Снизили порог
            buy_signals += 1
            
        # 5. Цена растет
        if price_change_5 > 0.5:  # Снизили порог
            buy_signals += 1
        
        # SELL сигналы
        sell_signals = 0
        
        # 1. Пересечение MA сверху вниз
        if sma_5 < sma_10 and closes[-2] > np.mean(closes[-11:-1]):
            sell_signals += 1
            
        # 2. RSI в перекупленности
        if rsi > 65:  # Снизили порог
            sell_signals += 1
            
        # 3. MACD пересекает сигнальную линию сверху вниз
        if macd_histogram < 0 and macd < signal_line * 1.05:
            sell_signals += 1
            
        # 4. Цена падает
        if price_change_5 < -0.5:  # Снизили порог
            sell_signals += 1
        
        # Определяем сигнал (нужно минимум 2 подтверждения вместо 3)
        signal_type = 'HOLD'
        confidence = 0.0
        
        # Логируем количество сигналов для отладки
        logger.debug(f"{symbol}: BUY signals={buy_signals}, SELL signals={sell_signals}")
        
        if buy_signals >= 2:
            signal_type = 'BUY'
            confidence = min(0.8, buy_signals / 5.0)  # Минимум 0.8 для уверенности
        elif sell_signals >= 2:
            signal_type = 'SELL'
            confidence = min(0.8, sell_signals / 4.0)
        
        if signal_type != 'HOLD':
            return {
                'symbol': symbol,
                'signal': signal_type,
                'price': current_price,
                'confidence': confidence,
                'stop_loss': current_price * (0.97 if signal_type == 'BUY' else 1.03),
                'take_profit': current_price * (1.06 if signal_type == 'BUY' else 0.94),
                'indicators': {
                    'rsi': rsi,
                    'macd': macd,
                    'volume_ratio': volume_ratio,
                    'sma_trend': 'up' if sma_5 > sma_20 else 'down',
                    'price_change_5': price_change_5
                }
            }
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка базового анализа {symbol}: {e}")
        return None

def _calculate_rsi_value(bot_instance, prices: np.ndarray, period: int = 14) -> float:
    """Расчет RSI из numpy array"""
    try:
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    except:
        return 50

async def get_latest_candles(bot_instance, symbol: str, timeframe: str = '1h', limit: int = 100):
    """
    Получение последних свечей для символа
    
    Args:
        bot_instance: Экземпляр бота
        symbol: Торговая пара (например, 'BTCUSDT')
        timeframe: Временной интервал ('1m', '5m', '15m', '1h', '4h', '1d')
        limit: Количество свечей
        
    Returns:
        List[List]: Список свечей в формате [timestamp, open, high, low, close, volume]
    """
    try:
        logger.debug(f"📊 Диагностика для {symbol}:")
        logger.debug(f"   Exchange type: {type(bot_instance.exchange).__name__}")
        logger.debug(f"   Has get_klines: {hasattr(bot_instance.exchange, 'get_klines')}")
        logger.debug(f"   Has ccxt_exchange: {hasattr(bot_instance.exchange, 'ccxt_exchange')}")
        
        # Пытаемся получить данные через exchange
        if hasattr(bot_instance.exchange, 'get_klines'):
            # Используем собственный метод exchange
            logger.debug(f"📊 Запрос исторических данных для {symbol} ({timeframe}, limit={limit})")
            candles = await bot_instance.exchange.get_klines(symbol, timeframe, limit)
            
            if candles and len(candles) > 0:
                logger.debug(f"✅ Получено {len(candles)} свечей для {symbol}")
                
                # Сохраняем в БД если доступно
                if hasattr(bot_instance, 'db') and bot_instance.db:
                    await _save_candles_to_db(bot_instance, symbol, timeframe, candles)
                
                # Возвращаем в нужном формате
                return _format_candles(candles)
            else:
                logger.warning(f"⚠️ {symbol} {timeframe}: Нет данных")
                
        elif hasattr(bot_instance.exchange, 'ccxt_exchange') and bot_instance.exchange.ccxt_exchange:
            # Используем CCXT
            logger.debug(f"📊 Запрос через CCXT для {symbol} ({timeframe}, limit={limit})")
            
            # Преобразуем таймфрейм для CCXT
            ccxt_timeframe = _convert_timeframe_to_ccxt(timeframe)
            
            ohlcv = await bot_instance.exchange.ccxt_exchange.fetch_ohlcv(
                symbol, ccxt_timeframe, limit=limit
            )
            
            if ohlcv and len(ohlcv) > 0:
                logger.debug(f"✅ Получено {len(ohlcv)} свечей для {symbol} через CCXT")
                
                # Сохраняем в БД если доступно
                if hasattr(bot_instance, 'db') and bot_instance.db:
                    await _save_ohlcv_to_db(bot_instance, symbol, timeframe, ohlcv)
                
                return ohlcv
            else:
                logger.warning(f"⚠️ {symbol} {timeframe}: Нет данных через CCXT")
        
        # Если прямые методы не сработали, пытаемся получить из БД
        if hasattr(bot_instance, 'db') and bot_instance.db:
            logger.debug(f"📊 Попытка получить данные из БД для {symbol}")
            return await _get_candles_from_db(bot_instance, symbol, timeframe, limit)
        
        logger.warning(f"⚠️ Не удалось получить данные для {symbol} ({timeframe})")
        return []
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения свечей для {symbol}: {e}")
        return []

def _convert_timeframe_to_ccxt(timeframe: str) -> str:
    """Преобразование таймфрейма в формат CCXT"""
    mapping = {
        '1m': '1m',
        '5m': '5m', 
        '15m': '15m',
        '30m': '30m',
        '1h': '1h',
        '4h': '4h',
        '1d': '1d'
    }
    return mapping.get(timeframe, '1h')

def _format_candles(candles):
    """Форматирование свечей в стандартный формат"""
    if not candles:
        return []
    
    formatted = []
    for candle in candles:
        if isinstance(candle, dict):
            # Если свеча в формате словаря
            formatted.append([
                candle.get('timestamp', 0),
                float(candle.get('open', 0)),
                float(candle.get('high', 0)),
                float(candle.get('low', 0)),
                float(candle.get('close', 0)),
                float(candle.get('volume', 0))
            ])
        elif isinstance(candle, (list, tuple)) and len(candle) >= 6:
            # Если свеча уже в формате списка
            formatted.append([
                candle[0],  # timestamp
                float(candle[1]),  # open
                float(candle[2]),  # high
                float(candle[3]),  # low
                float(candle[4]),  # close
                float(candle[5])   # volume
            ])
    
    return formatted

async def _get_candles_from_db(bot_instance, symbol: str, timeframe: str, limit: int):
    """Получение свечей из базы данных"""
    try:
        if not hasattr(bot_instance, 'db') or not bot_instance.db:
            return []
        
        from ..core.models import Candle
        
        # Создаем сессию БД
        session = bot_instance.db() if callable(bot_instance.db) else bot_instance.db
        
        # Получаем свечи из БД
        candles = session.query(Candle).filter(
            Candle.symbol == symbol,
            Candle.interval == timeframe
        ).order_by(Candle.open_time.desc()).limit(limit).all()
        
        if candles:
            # Конвертируем в нужный формат и сортируем по возрастанию
            result = []
            for candle in reversed(candles):  # Реверсируем для правильного порядка
                result.append([
                    int(candle.open_time.timestamp() * 1000),  # timestamp в мс
                    float(candle.open),
                    float(candle.high),
                    float(candle.low),
                    float(candle.close),
                    float(candle.volume)
                ])
            
            logger.debug(f"📊 Получено {len(result)} свечей для {symbol} из БД")
            return result
        
        return []
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения свечей из БД для {symbol}: {e}")
        return []

async def _save_candles_to_db(bot_instance, symbol: str, timeframe: str, candles):
    """Сохранение свечей в базу данных"""
    try:
        if not hasattr(bot_instance, 'db') or not bot_instance.db or not candles:
            return
        
        from ..core.models import Candle
        from datetime import datetime
        
        session = bot_instance.db() if callable(bot_instance.db) else bot_instance.db
        
        for candle_data in candles[-30:]:  # Сохраняем только последние 30 свечей
            try:
                # Определяем формат данных
                if isinstance(candle_data, dict):
                    timestamp = candle_data.get('timestamp', 0)
                    open_price = candle_data.get('open', 0)
                    high_price = candle_data.get('high', 0)
                    low_price = candle_data.get('low', 0)
                    close_price = candle_data.get('close', 0)
                    volume = candle_data.get('volume', 0)
                elif isinstance(candle_data, (list, tuple)) and len(candle_data) >= 6:
                    timestamp = candle_data[0]
                    open_price = candle_data[1]
                    high_price = candle_data[2]
                    low_price = candle_data[3]
                    close_price = candle_data[4]
                    volume = candle_data[5]
                else:
                    continue
                
                # Преобразуем timestamp
                if isinstance(timestamp, (int, float)):
                    if timestamp > 1e12:  # timestamp в миллисекундах
                        open_time = datetime.fromtimestamp(timestamp / 1000)
                    else:  # timestamp в секундах
                        open_time = datetime.fromtimestamp(timestamp)
                else:
                    continue
                
                # Проверяем, есть ли уже такая свеча
                existing = session.query(Candle).filter(
                    Candle.symbol == symbol,
                    Candle.interval == timeframe,
                    Candle.open_time == open_time
                ).first()
                
                if not existing:
                    # Создаем новую свечу
                    candle = Candle(
                        symbol=symbol,
                        interval=timeframe,
                        open_time=open_time,
                        open=float(open_price),
                        high=float(high_price),
                        low=float(low_price),
                        close=float(close_price),
                        volume=float(volume)
                    )
                    session.add(candle)
            
            except Exception as e:
                logger.debug(f"Ошибка сохранения свечи: {e}")
                continue
        
        session.commit()
        logger.debug(f"💾 Данные для {symbol} ({timeframe}) обработаны и сохранены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения свечей в БД: {e}")

async def _save_ohlcv_to_db(bot_instance, symbol: str, timeframe: str, ohlcv):
    """Сохранение OHLCV данных в базу данных"""
    try:
        if not hasattr(bot_instance, 'db') or not bot_instance.db or not ohlcv:
            return
        
        # Преобразуем OHLCV в формат свечей
        candles = []
        for item in ohlcv:
            if len(item) >= 6:
                candles.append({
                    'timestamp': item[0],
                    'open': item[1],
                    'high': item[2],
                    'low': item[3],
                    'close': item[4],
                    'volume': item[5]
                })
        
        await _save_candles_to_db(bot_instance, symbol, timeframe, candles)
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения OHLCV в БД: {e}")

async def _prepare_market_data(bot_instance, symbol: str):
    """✅ ИСПРАВЛЕНО: Асинхронная подготовка рыночных данных для анализа"""
    try:
        import pandas as pd
        
        logger.debug(f"📊 Подготовка данных для {symbol}")
        
        # Проверяем кэш свечей
        if hasattr(bot_instance, 'candle_cache') and symbol in bot_instance.candle_cache:
            candles = list(bot_instance.candle_cache[symbol])
            
            if candles and len(candles) > 0:
                # Подготавливаем массивы OHLCV
                timestamps, opens, highs, lows, closes, volumes = [], [], [], [], [], []
                
                for candle in candles:
                    try:
                        if isinstance(candle, dict):
                            timestamps.append(candle.get('timestamp', candle.get('open_time', 0)))
                            opens.append(float(candle.get('open', 0)))
                            highs.append(float(candle.get('high', 0)))
                            lows.append(float(candle.get('low', 0)))
                            closes.append(float(candle.get('close', 0)))
                            volumes.append(float(candle.get('volume', 0)))
                        elif isinstance(candle, (list, tuple)) and len(candle) >= 6:
                            timestamps.append(candle[0])
                            opens.append(float(candle[1]))
                            highs.append(float(candle[2]))
                            lows.append(float(candle[3]))
                            closes.append(float(candle[4]))
                            volumes.append(float(candle[5]))
                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"⚠️ Ошибка обработки свечи для {symbol}: {e}")
                        continue
                
                if len(closes) > 0:
                    return {
                        'timestamp': timestamps,
                        'open': opens,
                        'high': highs,
                        'low': lows,
                        'close': closes,
                        'volume': volumes,
                        'symbol': symbol
                    }
        
        # Если кэш пуст, получаем через data_collector
        if hasattr(bot_instance, 'data_collector') and bot_instance.data_collector:
            logger.debug(f"📈 Получение данных через data_collector для {symbol}")
            
            market_data = await bot_instance.data_collector.collect_market_data(symbol)
            
            if market_data and isinstance(market_data, dict) and 'candles' in market_data:
                candles = market_data['candles']
                if candles:
                    return {
                        'timestamp': [c.get('timestamp', c.get('open_time', 0)) for c in candles],
                        'open': [float(c.get('open', 0)) for c in candles],
                        'high': [float(c.get('high', 0)) for c in candles],
                        'low': [float(c.get('low', 0)) for c in candles],
                        'close': [float(c.get('close', 0)) for c in candles],
                        'volume': [float(c.get('volume', 0)) for c in candles],
                        'symbol': symbol
                    }
        
        logger.warning(f"⚠️ Нет данных для {symbol}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка подготовки данных для {symbol}: {e}")
        return None

async def validate_market_data(bot_instance, symbol: str, df: pd.DataFrame) -> bool:
    """
    Валидация полученных рыночных данных
    """
    try:
        if df is None or df.empty:
            logger.warning(f"⚠️ {symbol}: Пустой DataFrame")
            return False
            
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.warning(f"⚠️ {symbol}: Отсутствуют колонки: {missing_columns}")
            return False
            
        # Проверка на достаточное количество данных
        min_candles = 200
        if len(df) < min_candles:
            logger.warning(f"⚠️ {symbol}: Недостаточно данных ({len(df)} < {min_candles})")
            return False
            
        # Проверка на актуальность данных
        latest_time = pd.to_datetime(df.index[-1])
        time_diff = (datetime.now() - latest_time).total_seconds()
        
        if time_diff > 300:  # Данные старше 5 минут
            logger.warning(f"⚠️ {symbol}: Устаревшие данные (последняя свеча {time_diff/60:.1f} минут назад)")
            return False
            
        # Проверка на нулевые значения
        if df[required_columns].isnull().any().any():
            logger.warning(f"⚠️ {symbol}: Обнаружены null значения")
            return False
            
        # Проверка объема торгов
        recent_volume = df['volume'].tail(10).mean()
        if recent_volume < 100:  # Минимальный объем
            logger.info(f"ℹ️ {symbol}: Низкий объем торгов ({recent_volume:.2f})")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ {symbol}: Ошибка валидации данных: {e}")
        return False

async def get_market_conditions(bot_instance, symbol: str, df: pd.DataFrame) -> dict:
    """
    Анализ текущих рыночных условий для более точного входа
    """
    try:
        # Расчет волатильности
        returns = df['close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(24 * 365)  # Годовая волатильность
        
        # Определение тренда
        sma_20 = df['close'].rolling(20).mean().iloc[-1]
        sma_50 = df['close'].rolling(50).mean().iloc[-1]
        sma_200 = df['close'].rolling(200).mean().iloc[-1]
        current_price = df['close'].iloc[-1]
        
        trend = 'neutral'
        if current_price > sma_20 > sma_50 > sma_200:
            trend = 'strong_uptrend'
        elif current_price > sma_20 and current_price > sma_50:
            trend = 'uptrend'
        elif current_price < sma_20 < sma_50 < sma_200:
            trend = 'strong_downtrend'
        elif current_price < sma_20 and current_price < sma_50:
            trend = 'downtrend'
            
        # Расчет объемного профиля
        volume_avg = df['volume'].rolling(20).mean().iloc[-1]
        volume_current = df['volume'].iloc[-1]
        volume_ratio = volume_current / volume_avg if volume_avg > 0 else 0
        
        # RSI для определения перекупленности/перепроданности
        rsi = calculate_rsi(bot_instance, df['close'], 14).iloc[-1]
        
        # Поддержка и сопротивление
        recent_high = df['high'].tail(20).max()
        recent_low = df['low'].tail(20).min()
        price_position = (current_price - recent_low) / (recent_high - recent_low) if recent_high != recent_low else 0.5
        
        conditions = {
            'symbol': symbol,
            'price': current_price,
            'volatility': volatility,
            'trend': trend,
            'volume_ratio': volume_ratio,
            'rsi': rsi,
            'price_position': price_position,
            'support': recent_low,
            'resistance': recent_high,
            'timestamp': datetime.now()
        }
        
        logger.info(f"📊 {symbol}: Тренд={trend}, RSI={rsi:.1f}, Объем={volume_ratio:.2f}x, Позиция={price_position:.2%}")
        
        return conditions
        
    except Exception as e:
        logger.error(f"❌ {symbol}: Ошибка анализа условий: {e}")
        return {}

def calculate_rsi(bot_instance, prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Расчет RSI
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

async def apply_entry_filters(bot_instance, opportunities: List[Dict]) -> List[Dict]:
    """
    Применение дополнительных фильтров для отсеивания слабых сигналов
    """
    filtered = []
    
    for opp in opportunities:
        symbol = opp['symbol']
        confidence = opp.get('confidence', 0)
        
        # Получаем рыночные условия
        df = await bot_instance.exchange.get_historical_data(symbol, '5m', limit=200)
        if not await validate_market_data(bot_instance, symbol, df):
            continue
            
        conditions = await get_market_conditions(bot_instance, symbol, df)
        
        # Фильтры входа
        filters_passed = []
        
        # 1. Фильтр по объему
        if conditions.get('volume_ratio', 0) > 1.2:
            filters_passed.append('volume')
            
        # 2. Фильтр по тренду
        if opp['direction'] == 'long' and conditions.get('trend') in ['uptrend', 'strong_uptrend']:
            filters_passed.append('trend')
        elif opp['direction'] == 'short' and conditions.get('trend') in ['downtrend', 'strong_downtrend']:
            filters_passed.append('trend')
            
        # 3. Фильтр по RSI
        rsi = conditions.get('rsi', 50)
        if opp['direction'] == 'long' and 30 < rsi < 70:
            filters_passed.append('rsi')
        elif opp['direction'] == 'short' and 30 < rsi < 70:
            filters_passed.append('rsi')
            
        # 4. Фильтр по позиции цены
        price_pos = conditions.get('price_position', 0.5)
        if opp['direction'] == 'long' and price_pos < 0.7:
            filters_passed.append('price_position')
        elif opp['direction'] == 'short' and price_pos > 0.3:
            filters_passed.append('price_position')
            
        # Минимум 2 фильтра должны пройти
        if len(filters_passed) >= 2:
            opp['filters_passed'] = filters_passed
            opp['market_conditions'] = conditions
            opp['final_confidence'] = confidence * (len(filters_passed) / 4)
            filtered.append(opp)
            logger.info(f"✅ {symbol}: Прошел фильтры: {filters_passed}, итоговая уверенность: {opp['final_confidence']:.2%}")
        else:
            logger.debug(f"❌ {symbol}: Не прошел фильтры (прошло {len(filters_passed)}/4)")
            
    return filtered

async def log_analysis_summary(bot_instance, opportunities: List[Dict], filtered_opportunities: List[Dict]):
    """
    Детальное логирование результатов анализа
    """
    logger.info("📈 ИТОГИ АНАЛИЗА РЫНКА:")
    logger.info(f"├─ Проанализировано пар: {len(bot_instance.trading_pairs)}")
    logger.info(f"├─ Найдено сигналов: {len(opportunities)}")
    logger.info(f"├─ После фильтрации: {len(filtered_opportunities)}")
    
    if opportunities and not filtered_opportunities:
        logger.info("└─ ⚠️ Все сигналы отфильтрованы. Возможные причины:")
        logger.info("   ├─ Слабые рыночные условия")
        logger.info("   ├─ Низкий объем торгов")
        logger.info("   └─ Несоответствие тренду")
        
    # Статистика по стратегиям
    strategy_stats = {}
    for opp in opportunities:
        strategy = opp.get('strategy', 'unknown')
        strategy_stats[strategy] = strategy_stats.get(strategy, 0) + 1
        
    if strategy_stats:
        logger.info("📊 Сигналы по стратегиям:")
        for strategy, count in strategy_stats.items():
            logger.info(f"   ├─ {strategy}: {count}")

async def analyze_market(bot_instance) -> List[Dict]:
    """Анализ рынка и поиск торговых возможностей"""
    all_opportunities = []
    
    # Проверяем режим тестирования
    if bot_instance.config.get('TESTNET'):
        logger.info("🧪 Работаем в TESTNET режиме")
    else:
        logger.info("💰 Работаем с MAINNET данными (Paper Trading)")
    
    tasks = []
    for symbol in bot_instance.trading_pairs:
        if bot_instance.can_open_position(symbol):
            task = asyncio.create_task(bot_instance.analyze_trading_pair(symbol))
            tasks.append(task)
        else:
            logger.debug(f"⏭️ {symbol}: Пропускаем (уже есть позиция или лимит)")
            
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"❌ Ошибка анализа: {result}")
        elif result:
            all_opportunities.extend(result)
    
    # Применяем дополнительные фильтры
    filtered_opportunities = await apply_entry_filters(bot_instance, all_opportunities)
    
    # Логируем итоги анализа
    await log_analysis_summary(bot_instance, all_opportunities, filtered_opportunities)
    
    # Сортируем по итоговой уверенности
    filtered_opportunities.sort(key=lambda x: x.get('final_confidence', 0), reverse=True)
    
    # Ограничиваем количество одновременных сделок
    max_new_positions = min(
        bot_instance.max_positions - len(bot_instance.active_positions),
        bot_instance.config.get('MAX_CONCURRENT_TRADES', 3)
    )
    
    return filtered_opportunities[:max_new_positions]

async def check_api_limits(bot_instance):
    """
    Проверка и соблюдение лимитов API Bybit
    """
    current_time = time.time()
    
    # Очистка старых записей
    bot_instance.api_calls = [call_time for call_time in bot_instance.api_calls if current_time - call_time < 60]
    
    # Проверка лимитов
    calls_per_minute = len(bot_instance.api_calls)
    max_calls = int(bot_instance.config.get('MAX_API_CALLS_PER_SECOND', 10) * 60 * 0.8)  # 80% от лимита
    
    if calls_per_minute >= max_calls:
        wait_time = 60 - (current_time - bot_instance.api_calls[0])
        logger.warning(f"⚠️ Приближаемся к лимиту API ({calls_per_minute}/{max_calls}). Ждем {wait_time:.1f}с")
        await asyncio.sleep(wait_time)
        
    # Добавляем задержку для человекоподобности
    if bot_instance.config.get('RANDOM_DELAY_MIN') and bot_instance.config.get('RANDOM_DELAY_MAX'):
        delay = random.uniform(
            float(bot_instance.config.get('RANDOM_DELAY_MIN', 2)),
            float(bot_instance.config.get('RANDOM_DELAY_MAX', 10))
        )
        await asyncio.sleep(delay)
        
    bot_instance.api_calls.append(current_time)

async def analyze_market_conditions(bot_instance):
    """Анализ рыночных условий"""
    try:
        logger.debug("📊 Анализ рыночных условий...")
        
        # Обновляем рыночные данные
        await _update_market_data(bot_instance)
        
        # Ищем торговые возможности
        opportunities = await _find_all_trading_opportunities(bot_instance)
        
        return {
            'opportunities': opportunities,
            'market_phase': 'neutral',  # Можно добавить более сложную логику
            'volatility': 'medium',
            'timestamp': datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка анализа рыночных условий: {e}")
        return {
            'opportunities': [],
            'market_phase': 'unknown',
            'volatility': 'unknown',
            'timestamp': datetime.utcnow()
        }

async def determine_market_phase(bot_instance):
    """Определение рыночной фазы"""
    try:
        # Простое определение фазы рынка
        # Можно усложнить логику в зависимости от требований
        return 'neutral'
        
    except Exception as e:
        logger.error(f"❌ Ошибка определения рыночной фазы: {e}")
        return 'unknown'
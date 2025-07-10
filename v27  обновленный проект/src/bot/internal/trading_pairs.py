"""
Модуль работы с торговыми парами BotManager
Файл: src/bot/internal/trading_pairs.py

Все методы для работы с торговыми парами
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from ...core.unified_config import unified_config as config

logger = logging.getLogger(__name__)


async def discover_all_trading_pairs(bot_manager) -> bool:
    """Автоматическое обнаружение всех торговых пар"""
    try:
        logger.info("🔍 Автоматическое обнаружение торговых пар...")
        
        if config.ENABLE_AUTO_PAIR_DISCOVERY and bot_manager.exchange:
            # Получаем все рынки с биржи
            markets = await fetch_all_markets_from_exchange(bot_manager)
            
            if not markets:
                logger.warning("⚠️ Не удалось получить рынки с биржи")
                return False
            
            # Фильтруем по критериям
            filtered_pairs = await filter_and_rank_pairs(bot_manager, markets)
            
            # Ограничиваем количество
            max_pairs = config.MAX_TRADING_PAIRS
            bot_manager.all_trading_pairs = filtered_pairs[:max_pairs]
            
            # Разделяем на категории
            await categorize_trading_pairs(bot_manager)
            
            logger.info(f"✅ Обнаружено {len(bot_manager.all_trading_pairs)} торговых пар")
            logger.info(f"📈 Активных: {len(bot_manager.active_pairs)}")
            logger.info(f"👀 В списке наблюдения: {len(bot_manager.watchlist_pairs)}")
            
            return True
        else:
            # Используем конфигурационный список
            load_pairs_from_config(bot_manager)
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка обнаружения торговых пар: {e}")
        return False


async def fetch_all_markets_from_exchange(bot_manager) -> List[Dict]:
    """Получение РЕАЛЬНЫХ рынков с биржи"""
    try:
        # Используем ваш существующий real_client.py
        if not hasattr(bot_manager, 'real_exchange') or not bot_manager.real_exchange:
            from ...exchange.real_client import RealExchangeClient
            bot_manager.real_exchange = RealExchangeClient()
            await bot_manager.real_exchange.connect()
        
        # Получаем реальные рынки
        markets = await bot_manager.real_exchange.get_all_markets()
        
        if not markets:
            logger.warning("⚠️ Не удалось получить рынки, используем конфиг")
            load_pairs_from_config(bot_manager)
            return []
        
        logger.info(f"✅ Загружено {len(markets)} РЕАЛЬНЫХ рынков с Bybit")
        return markets
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения реальных рынков: {e}")
        return []


async def filter_and_rank_pairs(bot_manager, markets: List[Dict]) -> List[Dict]:
    """Фильтрация и ранжирование торговых пар"""
    try:
        filtered_pairs = []
        
        for market in markets:
            # Применяем фильтры
            if await passes_pair_filters(bot_manager, market):
                # Рассчитываем скор для ранжирования
                score = await calculate_pair_score(bot_manager, market)
                market['trading_score'] = score
                filtered_pairs.append(market)
        
        # Сортируем по скору (лучшие сначала)
        filtered_pairs.sort(key=lambda x: x['trading_score'], reverse=True)
        
        logger.info(f"🎯 Отфильтровано {len(filtered_pairs)} пар из {len(markets)}")
        return filtered_pairs
        
    except Exception as e:
        logger.error(f"❌ Ошибка фильтрации пар: {e}")
        return []


async def passes_pair_filters(bot_manager, market: Dict) -> bool:
    """Проверка пары на соответствие фильтрам"""
    try:
        symbol = market.get('symbol', '')
        base = market.get('base', '')
        quote = market.get('quote', '')
        volume_24h = market.get('volume_24h', 0)
        price = market.get('price', 0)
        
        # Базовые фильтры
        if not market.get('active', False):
            return False
        
        # Фильтр по котируемой валюте
        if quote not in config.ALLOWED_QUOTE_ASSETS:
            return False
        
        # Фильтр по исключенным базовым активам
        if base in config.EXCLUDED_BASE_ASSETS:
            return False
        
        # Фильтр по объему
        if volume_24h < config.MIN_VOLUME_24H_USD:
            return False
        
        # Фильтр по цене
        if price < config.MIN_PRICE_USD or price > config.MAX_PRICE_USD:
            return False
        
        # Фильтр по черному списку
        if symbol in bot_manager.blacklisted_pairs:
            return False
        
        # Дополнительные фильтры
        change_24h = abs(market.get('change_24h', 0))
        if change_24h > 50:  # Исключаем слишком волатильные
            return False
        
        trades_count = market.get('trades_count', 0)
        if trades_count < 100:  # Минимальная активность
            return False
        
        spread_percent = (market.get('ask', 0) - market.get('bid', 0)) / price * 100
        if spread_percent > 1:  # Максимальный спред 1%
            return False
        
        return True
        
    except Exception as e:
        logger.debug(f"Ошибка проверки фильтров для {market.get('symbol', 'unknown')}: {e}")
        return False


async def calculate_pair_score(bot_manager, market: Dict) -> float:
    """Расчет скора торговой пары для ранжирования"""
    try:
        score = 0.0
        
        # Скор по объему (30%)
        volume_24h = market.get('volume_24h', 0)
        volume_score = min(1.0, volume_24h / 50000000)  # Нормализуем к $50M
        score += volume_score * 0.3
        
        # Скор по активности торгов (20%)
        trades_count = market.get('trades_count', 0)
        activity_score = min(1.0, trades_count / 10000)  # Нормализуем к 10k сделок
        score += activity_score * 0.2
        
        # Скор по ликвидности (спреду) (20%)
        price = market.get('price', 1)
        spread = (market.get('ask', price) - market.get('bid', price)) / price
        liquidity_score = max(0, 1 - spread * 100)  # Чем меньше спред, тем лучше
        score += liquidity_score * 0.2
        
        # Скор по волатильности (15%)
        change_24h = abs(market.get('change_24h', 0))
        volatility_score = min(1.0, change_24h / 10)  # Нормализуем к 10%
        score += volatility_score * 0.15
        
        # Скор по популярности базового актива (15%)
        base = market.get('base', '')
        popularity_score = get_asset_popularity_score(bot_manager, base)
        score += popularity_score * 0.15
        
        return min(1.0, score)
        
    except Exception as e:
        logger.debug(f"Ошибка расчета скора для {market.get('symbol', 'unknown')}: {e}")
        return 0.0


def get_asset_popularity_score(bot_manager, base_asset: str) -> float:
    """Получение скора популярности актива"""
    # Популярные активы получают больший скор
    popularity_map = {
        'BTC': 1.0, 'ETH': 0.95, 'BNB': 0.9, 'SOL': 0.85, 'ADA': 0.8,
        'XRP': 0.75, 'DOT': 0.7, 'AVAX': 0.65, 'MATIC': 0.6, 'LINK': 0.55,
        'UNI': 0.5, 'LTC': 0.45, 'BCH': 0.4, 'ATOM': 0.35, 'FIL': 0.3
    }
    return popularity_map.get(base_asset, 0.1)  # Базовый скор для неизвестных


async def categorize_trading_pairs(bot_manager):
    """Категоризация торговых пар"""
    try:
        # Очищаем старые категории
        bot_manager.active_pairs.clear()
        bot_manager.watchlist_pairs.clear()
        bot_manager.trending_pairs.clear()
        bot_manager.high_volume_pairs.clear()
        
        if not bot_manager.all_trading_pairs:
            return
        
        # Сортируем по скору
        sorted_pairs = sorted(bot_manager.all_trading_pairs, 
                            key=lambda x: x.get('trading_score', 0), 
                            reverse=True)
        
        # Активные пары (топ 30% или максимум из конфига)
        max_active = min(config.MAX_POSITIONS, len(sorted_pairs) // 3)
        bot_manager.active_pairs = [pair['symbol'] for pair in sorted_pairs[:max_active]]
        
        # Список наблюдения (следующие 20%)
        watchlist_count = min(50, len(sorted_pairs) // 5)
        start_idx = len(bot_manager.active_pairs)
        bot_manager.watchlist_pairs = [pair['symbol'] for pair in sorted_pairs[start_idx:start_idx + watchlist_count]]
        
        # Трендовые пары (с высоким изменением за 24ч)
        trending_pairs = [pair for pair in sorted_pairs if abs(pair.get('change_24h', 0)) > 5]
        bot_manager.trending_pairs = [pair['symbol'] for pair in trending_pairs[:20]]
        
        # Высокообъемные пары (топ по объему)
        volume_sorted = sorted(sorted_pairs, key=lambda x: x.get('volume_24h', 0), reverse=True)
        bot_manager.high_volume_pairs = [pair['symbol'] for pair in volume_sorted[:20]]
        
        logger.info(f"📊 Категоризация завершена:")
        logger.info(f"  🎯 Активные: {len(bot_manager.active_pairs)}")
        logger.info(f"  👀 Наблюдение: {len(bot_manager.watchlist_pairs)}")
        logger.info(f"  📈 Трендовые: {len(bot_manager.trending_pairs)}")
        logger.info(f"  💰 Высокообъемные: {len(bot_manager.high_volume_pairs)}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка категоризации пар: {e}")


def load_pairs_from_config(bot_manager):
    """Загрузка торговых пар из конфигурации"""
    try:
        configured_pairs = config.get_active_trading_pairs()
        
        # Преобразуем в формат all_trading_pairs
        bot_manager.all_trading_pairs = [
            {
                'symbol': symbol,
                'base': symbol.replace('USDT', '').replace('BUSD', '').replace('USDC', ''),
                'quote': 'USDT',
                'trading_score': 0.5  # Средний скор
            }
            for symbol in configured_pairs
        ]
        
        # Ограничиваем количество
        max_pairs = config.MAX_TRADING_PAIRS
        bot_manager.all_trading_pairs = bot_manager.all_trading_pairs[:max_pairs]
        bot_manager.active_pairs = [pair['symbol'] for pair in bot_manager.all_trading_pairs[:config.MAX_POSITIONS]]
        
        logger.info(f"📊 Загружено {len(bot_manager.all_trading_pairs)} пар из конфигурации")
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки пар из конфигурации: {e}")
        # Fallback к минимальному набору


async def load_historical_data_for_pairs(bot_manager):
    """Загрузка исторических данных для активных торговых пар"""
    try:
        if not bot_manager.active_pairs:
            logger.warning("⚠️ Нет активных пар для загрузки данных")
            return
            
        logger.info(f"📊 Загрузка данных для {len(bot_manager.active_pairs)} пар...")
        
        for symbol in bot_manager.active_pairs[:5]:  # Загружаем для первых 5 пар
            try:
                if bot_manager.data_collector:
                    await bot_manager.data_collector.collect_historical_data(symbol, '1h', 100)
                await asyncio.sleep(0.5)  # Небольшая задержка между запросами
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки данных для {symbol}: {e}")
                
        logger.info("✅ Исторические данные загружены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки исторических данных: {e}")


async def update_pairs(bot_manager, pairs: List[str]) -> None:
    """Обновление торговых пар (для совместимости)"""
    bot_manager.trading_pairs = pairs
    # Обновляем также активные пары
    bot_manager.active_pairs = pairs[:config.MAX_TRADING_PAIRS]
    logger.info(f"📊 Обновлены торговые пары: {len(pairs)}")
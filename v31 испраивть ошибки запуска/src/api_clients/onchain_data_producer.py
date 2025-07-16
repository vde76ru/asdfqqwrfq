#!/usr/bin/env python3
"""
Продюсер для сбора ончейн-данных с Etherscan и аналогов
Файл: src/api_clients/onchain_data_producer.py

✅ ИСПРАВЛЕНИЯ API ЛИМИТОВ:
- Добавлены паузы для соблюдения лимитов Etherscan/BscScan/PolygonScan (5 req/sec)
- Улучшено кэширование цен токенов для CoinGecko API
- Добавлена обработка rate limiting
"""
import asyncio
import aiohttp
import logging
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from decimal import Decimal
import json
import os
from dataclasses import dataclass
from enum import Enum

from ..core.database import SessionLocal
from ..core.models import WhaleTransaction, TransactionTypeEnum
from ..core.unified_config import unified_config as config

logger = logging.getLogger(__name__)


class BlockchainNetwork(Enum):
    """Поддерживаемые блокчейн сети"""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"


@dataclass
class NetworkConfig:
    """Конфигурация для каждой сети"""
    name: str
    api_base_url: str
    api_key: str
    native_token: str
    decimals: int = 18
    block_time: int = 12  # секунд


class OnchainDataProducer:
    """
    Продюсер для сбора ончейн-данных о транзакциях китов
    Поддерживает Etherscan, BscScan, PolygonScan (унифицированный API)
    
    ✅ СОБЛЮДЕНИЕ API ЛИМИТОВ:
    - Etherscan, BscScan, PolygonScan: 5 запросов/секунду
    - CoinGecko: 30 запросов/минуту (кэширование на 5 минут)
    """
    
    # Пороги для определения китов (в USD)
    WHALE_THRESHOLDS = {
        'ethereum': 1_000_000,    # $1M для Ethereum
        'bsc': 500_000,          # $500K для BSC
        'polygon': 250_000       # $250K для Polygon
    }
    
    # Известные адреса бирж
    EXCHANGE_ADDRESSES = {
        'binance': {
            'ethereum': ['0x28c6c06298d514db089934071355e5743bf21d60', 
                        '0xdfd5293d8e347dfe59e90efd55b2956a1343963d'],
            'bsc': ['0x8894e0a0c962cb723c1976a4421c95949be2d4e3']
        },
        'bybit': {
            'ethereum': ['0xf89d7b9c864f589bbf53a82105107622b35eaa40']
        },
        'okx': {
            'ethereum': ['0x06959153b974d0d5fdfd87d561db6d8d4fa0bb0b']
        },
        'kucoin': {
            'ethereum': ['0xb8e6d31e7b212b2b7250ee9c26c56cebbfbe6b23']
        }
    }
    
    def __init__(self):
        """Инициализация продюсера"""
        self.networks = self._init_networks()
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_running = False
        self.last_blocks = {}  # Последний обработанный блок для каждой сети
        
        # ✅ УЛУЧШЕННОЕ КЭШИРОВАНИЕ ЦЕН
        self.token_prices = {}  # Кэш цен токенов: {symbol: (price, timestamp)}
        self.price_cache_ttl = 300  # 5 минут кэширования
        
    def _init_networks(self) -> Dict[str, NetworkConfig]:
        """Инициализация конфигураций сетей"""
        return {
            BlockchainNetwork.ETHEREUM.value: NetworkConfig(
                name="Ethereum",
                api_base_url="https://api.etherscan.io/api",
                api_key=getattr(config, 'ETHERSCAN_API_KEY', ''),
                native_token="ETH",
                decimals=18,
                block_time=12
            ),
            BlockchainNetwork.BSC.value: NetworkConfig(
                name="BSC",
                api_base_url="https://api.bscscan.com/api",
                api_key=getattr(config, 'BSCSCAN_API_KEY', ''),
                native_token="BNB",
                decimals=18,
                block_time=3
            ),
            BlockchainNetwork.POLYGON.value: NetworkConfig(
                name="Polygon",
                api_base_url="https://api.polygonscan.com/api",
                api_key=getattr(config, 'POLYGONSCAN_API_KEY', ''),
                native_token="MATIC",
                decimals=18,
                block_time=2
            )
        }
        
    async def start(self):
        """Запуск продюсера"""
        logger.info("🚀 Запуск OnchainDataProducer...")
        
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        self.is_running = True
        
        # Запускаем мониторинг для каждой сети
        tasks = []
        for network_name, network_config in self.networks.items():
            if network_config.api_key:
                tasks.append(asyncio.create_task(self._monitor_network(network_name)))
            else:
                logger.warning(f"⚠️ API ключ для {network_name} не настроен")
                
        await asyncio.gather(*tasks)
        
    async def stop(self):
        """Остановка продюсера"""
        logger.info("🛑 Остановка OnchainDataProducer...")
        self.is_running = False
        
        if self.session:
            await self.session.close()
            
    async def _monitor_network(self, network: str):
        """Мониторинг транзакций в конкретной сети"""
        logger.info(f"👁️ Начат мониторинг сети {network}")
        
        network_config = self.networks[network]
        retry_count = 0
        max_retries = 3
        
        while self.is_running:
            try:
                # Получаем последний блок
                current_block = await self._get_latest_block(network)
                
                if not current_block:
                    await asyncio.sleep(10)
                    continue
                    
                # Если это первый запуск, начинаем с текущего блока
                if network not in self.last_blocks:
                    self.last_blocks[network] = current_block - 1
                    
                # Обрабатываем новые блоки
                if current_block > self.last_blocks[network]:
                    await self._process_blocks(
                        network, 
                        self.last_blocks[network] + 1, 
                        current_block
                    )
                    self.last_blocks[network] = current_block
                    
                # Ждем время блока
                await asyncio.sleep(network_config.block_time)
                retry_count = 0
                
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга {network}: {e}")
                retry_count += 1
                
                if retry_count >= max_retries:
                    logger.error(f"❌ Превышено количество попыток для {network}")
                    await asyncio.sleep(60)  # Долгая пауза перед повторной попыткой
                    retry_count = 0
                else:
                    await asyncio.sleep(10 * retry_count)
                    
    async def _get_latest_block(self, network: str) -> Optional[int]:
        """Получение номера последнего блока"""
        network_config = self.networks[network]
        
        params = {
            'module': 'proxy',
            'action': 'eth_blockNumber',
            'apikey': network_config.api_key
        }
        
        try:
            async with self.session.get(
                network_config.api_base_url, 
                params=params
            ) as response:
                data = await response.json()
                
                if data.get('status') == '1' and data.get('result'):
                    return int(data['result'], 16)
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения блока {network}: {e}")
            
        return None
        
    async def _process_blocks(self, network: str, start_block: int, end_block: int):
        """Обработка диапазона блоков"""
        logger.debug(f"📦 Обработка блоков {start_block}-{end_block} в {network}")
        
        # Получаем транзакции из блоков
        transactions = await self._get_transactions(network, start_block, end_block)
        
        # Фильтруем транзакции китов
        whale_txs = await self._filter_whale_transactions(network, transactions)
        
        # Сохраняем в БД
        if whale_txs:
            await self._save_transactions(whale_txs)
            logger.info(f"🐋 Найдено {len(whale_txs)} транзакций китов в {network}")
            
    async def _get_transactions(self, network: str, start_block: int, end_block: int) -> List[Dict]:
        """
        Получение транзакций из диапазона блоков
        ✅ СОБЛЮДЕНИЕ API ЛИМИТОВ: 5 запросов/секунду
        """
        network_config = self.networks[network]
        all_transactions = []
        
        # Ограничиваем количество блоков за раз
        blocks_per_request = 10
        
        for block_start in range(start_block, end_block + 1, blocks_per_request):
            block_end = min(block_start + blocks_per_request - 1, end_block)
            
            # Получаем ERC20 токен трансферы
            params = {
                'module': 'account',
                'action': 'tokentx',
                'startblock': block_start,
                'endblock': block_end,
                'sort': 'desc',
                'apikey': network_config.api_key
            }
            
            try:
                async with self.session.get(
                    network_config.api_base_url, 
                    params=params
                ) as response:
                    data = await response.json()
                    
                    if data.get('status') == '1' and data.get('result'):
                        all_transactions.extend(data['result'])
                        
            except Exception as e:
                logger.error(f"❌ Ошибка получения транзакций {network}: {e}")
            
            # ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Пауза для соблюдения лимита API
            # Лимит: 5 запросов/секунду = 210мс между запросами
            await asyncio.sleep(0.21)  # 210 мс для соблюдения лимита 5 req/sec
                
        return all_transactions
        
    async def _filter_whale_transactions(self, network: str, transactions: List[Dict]) -> List[Dict]:
        """Фильтрация транзакций китов"""
        whale_txs = []
        threshold = self.WHALE_THRESHOLDS.get(network, 1_000_000)
        
        for tx in transactions:
            try:
                # Получаем символ токена
                symbol = tx.get('tokenSymbol', '').upper()
                
                # Проверяем, что это интересующий нас токен
                tracked_symbols = getattr(config, 'TRACKED_SYMBOLS', ['BTC', 'ETH', 'USDT', 'USDC'])
                if symbol not in tracked_symbols:
                    continue
                    
                # Получаем количество токенов
                decimals = int(tx.get('tokenDecimal', 18))
                value = Decimal(tx.get('value', 0)) / Decimal(10 ** decimals)
                
                # Получаем цену токена
                token_price = await self._get_token_price(symbol)
                if not token_price:
                    continue
                    
                # Вычисляем USD стоимость
                usd_value = float(value) * token_price
                
                # Проверяем порог
                if usd_value >= threshold:
                    # Определяем тип транзакции
                    tx_type = self._determine_transaction_type(
                        tx.get('from', '').lower(),
                        tx.get('to', '').lower()
                    )
                    
                    whale_txs.append({
                        'network': network,
                        'hash': tx.get('hash'),
                        'from': tx.get('from'),
                        'to': tx.get('to'),
                        'symbol': symbol,
                        'amount': float(value),
                        'usd_value': usd_value,
                        'tx_type': tx_type,
                        'timestamp': datetime.fromtimestamp(int(tx.get('timeStamp', 0))),
                        'block_number': int(tx.get('blockNumber', 0))
                    })
                    
            except Exception as e:
                logger.error(f"❌ Ошибка обработки транзакции: {e}")
                continue
                
        return whale_txs
        
    async def _get_token_price(self, symbol: str) -> Optional[float]:
        """
        Получение цены токена с кэшированием на 5 минут
        ✅ СОБЛЮДЕНИЕ ЛИМИТОВ: CoinGecko API ~30 запросов/минуту
        """
        cache_key = symbol.upper()
        current_time = time.time()

        # Проверяем кэш
        if cache_key in self.token_prices:
            price, last_update = self.token_prices[cache_key]
            if current_time - last_update < self.price_cache_ttl:  # 300 секунд = 5 минут
                logger.debug(f"💰 Цена для {symbol} взята из кэша: ${price}")
                return price

        # Если в кэше нет или он устарел, делаем запрос
        logger.debug(f"🔄 Запрос новой цены для {symbol}...")
        
        # TODO: Здесь должна быть ваша реальная интеграция с CoinGecko API
        # Пример реального запроса:
        # try:
        #     url = f"https://api.coingecko.com/api/v3/simple/price"
        #     params = {'ids': symbol.lower(), 'vs_currencies': 'usd'}
        #     async with self.session.get(url, params=params) as response:
        #         data = await response.json()
        #         price = data.get(symbol.lower(), {}).get('usd')
        #         if price:
        #             self.token_prices[cache_key] = (price, current_time)
        #             return price
        # except Exception as e:
        #     logger.error(f"❌ Ошибка получения цены {symbol}: {e}")
        
        # Временные статичные цены для тестирования
        static_prices = {
            'BTC': 43000, 'ETH': 2300, 'BNB': 310,
            'USDT': 1, 'USDC': 1, 'SOL': 95, 'XRP': 0.6,
            'ADA': 0.48, 'AVAX': 35, 'DOT': 6.5, 'MATIC': 0.85, 
            'LINK': 14, 'UNI': 7.2, 'LTC': 73, 'ATOM': 10,
            'NEAR': 3.5, 'ALGO': 0.15, 'FTM': 0.5, 'SAND': 0.35
        }
        
        price = static_prices.get(symbol.upper())

        if price:
            # Сохраняем в кэш
            self.token_prices[cache_key] = (price, current_time)
            logger.info(f"✅ Новая цена для {symbol} получена и закэширована: ${price}")
            return price
        else:
            logger.warning(f"⚠️ Не удалось получить цену для {symbol}")
            return None
        
    def _determine_transaction_type(self, from_address: str, to_address: str) -> TransactionTypeEnum:
        """Определение типа транзакции"""
        from_exchange = self._is_exchange_address(from_address)
        to_exchange = self._is_exchange_address(to_address)
        
        if from_exchange and not to_exchange:
            return TransactionTypeEnum.EXCHANGE_WITHDRAWAL
        elif to_exchange and not from_exchange:
            return TransactionTypeEnum.EXCHANGE_DEPOSIT
        elif self._is_dex_address(from_address) or self._is_dex_address(to_address):
            return TransactionTypeEnum.DEX_SWAP
        else:
            return TransactionTypeEnum.TRANSFER
            
    def _is_exchange_address(self, address: str) -> bool:
        """Проверка, является ли адрес биржевым"""
        address_lower = address.lower()
        
        for exchange, networks in self.EXCHANGE_ADDRESSES.items():
            for network_addresses in networks.values():
                if address_lower in [addr.lower() for addr in network_addresses]:
                    return True
                    
        return False
        
    def _is_dex_address(self, address: str) -> bool:
        """Проверка, является ли адрес DEX"""
        dex_addresses = [
            '0x7a250d5630b4cf539739df2c5dacb4c659f2488d',  # Uniswap V2 Router
            '0xe592427a0aece92de3edee1f18e0157c05861564',  # Uniswap V3 Router
            '0x10ed43c718714eb63d5aa57b78b54704e256024e',  # PancakeSwap Router
            '0x1b02da8cb0d097eb8d57a175b88c7d8b47997506',  # SushiSwap Router
            '0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45',  # Uniswap V3 Router 2
        ]
        
        return address.lower() in [addr.lower() for addr in dex_addresses]
        
    async def _save_transactions(self, transactions: List[Dict]):
        """Сохранение транзакций в БД"""
        db = SessionLocal()
        
        try:
            saved_count = 0
            for tx_data in transactions:
                # Проверяем, нет ли уже такой транзакции
                existing = db.query(WhaleTransaction).filter_by(
                    blockchain=tx_data['network'],
                    transaction_hash=tx_data['hash']
                ).first()
                
                if not existing:
                    whale_tx = WhaleTransaction(
                        blockchain=tx_data['network'],
                        transaction_hash=tx_data['hash'],
                        from_address=tx_data['from'],
                        to_address=tx_data['to'],
                        symbol=tx_data['symbol'],
                        amount=Decimal(str(tx_data['amount'])),
                        usd_value=Decimal(str(tx_data['usd_value'])),
                        transaction_type=tx_data['tx_type'],
                        timestamp=tx_data['timestamp'],
                        block_number=tx_data['block_number'],
                        is_processed=False  # Новые транзакции не обработаны
                    )
                    
                    db.add(whale_tx)
                    saved_count += 1
                    
            db.commit()
            if saved_count > 0:
                logger.info(f"✅ Сохранено {saved_count} новых транзакций китов")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения транзакций: {e}")
            db.rollback()
        finally:
            db.close()

    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики работы продюсера"""
        return {
            'networks_monitored': len([n for n in self.networks.values() if n.api_key]),
            'cache_size': len(self.token_prices),
            'last_blocks': self.last_blocks.copy(),
            'is_running': self.is_running
        }


# Функция для запуска продюсера
async def main():
    """Пример запуска продюсера"""
    producer = OnchainDataProducer()
    
    try:
        await producer.start()
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
    finally:
        await producer.stop()


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())
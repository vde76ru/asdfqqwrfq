#!/usr/bin/env python3
"""
Продюсер для сбора ончейн-данных с Etherscan и аналогов
Файл: src/api_clients/onchain_data_producer.py

Собирает данные о транзакциях китов с блокчейнов Ethereum, BSC, Polygon
"""
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from decimal import Decimal
import json
import os
from dataclasses import dataclass
from enum import Enum

from ..core.database import SessionLocal
from ..core.signal_models import WhaleTransaction, TransactionType
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
        self.token_prices = {}  # Кэш цен токенов
        self.price_cache_ttl = 300  # 5 минут
        self.last_price_update = {}
        
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
        """Получение транзакций из диапазона блоков"""
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
                if symbol not in getattr(config, 'TRACKED_SYMBOLS', []):
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
        """Получение цены токена (заглушка - нужно интегрировать с CoinGecko)"""
        # Простой кэш цен
        if symbol in self.token_prices:
            last_update = self.last_price_update.get(symbol, 0)
            if datetime.now().timestamp() - last_update < self.price_cache_ttl:
                return self.token_prices[symbol]
                
        # TODO: Интеграция с CoinGecko API
        # Временные статичные цены для тестирования
        static_prices = {
            'BTC': 30000,
            'ETH': 2000,
            'BNB': 300,
            'USDT': 1,
            'USDC': 1,
            'SOL': 25,
            'XRP': 0.5,
            'ADA': 0.3,
            'AVAX': 15,
            'DOT': 5,
            'MATIC': 0.7,
            'LINK': 7
        }
        
        price = static_prices.get(symbol.upper(), 0)
        
        # Кэшируем цену
        if price > 0:
            self.token_prices[symbol] = price
            self.last_price_update[symbol] = datetime.now().timestamp()
            
        return price if price > 0 else None
        
    def _determine_transaction_type(self, from_address: str, to_address: str) -> TransactionType:
        """Определение типа транзакции"""
        from_exchange = self._is_exchange_address(from_address)
        to_exchange = self._is_exchange_address(to_address)
        
        if from_exchange and not to_exchange:
            return TransactionType.EXCHANGE_WITHDRAWAL
        elif to_exchange and not from_exchange:
            return TransactionType.EXCHANGE_DEPOSIT
        elif self._is_dex_address(from_address) or self._is_dex_address(to_address):
            return TransactionType.DEX_SWAP
        else:
            return TransactionType.TRANSFER
            
    def _is_exchange_address(self, address: str) -> bool:
        """Проверка, является ли адрес биржевым"""
        address_lower = address.lower()
        
        for exchange, networks in self.EXCHANGE_ADDRESSES.items():
            for network_addresses in networks.values():
                if address_lower in [addr.lower() for addr in network_addresses]:
                    return True
                    
        return False
        
    def _is_dex_address(self, address: str) -> bool:
        """Проверка, является ли адрес DEX (заглушка)"""
        # TODO: Добавить известные адреса DEX
        dex_addresses = [
            '0x7a250d5630b4cf539739df2c5dacb4c659f2488d',  # Uniswap V2 Router
            '0xe592427a0aece92de3edee1f18e0157c05861564',  # Uniswap V3 Router
            '0x10ed43c718714eb63d5aa57b78b54704e256024e',  # PancakeSwap Router
        ]
        
        return address.lower() in [addr.lower() for addr in dex_addresses]
        
    async def _save_transactions(self, transactions: List[Dict]):
        """Сохранение транзакций в БД"""
        db = SessionLocal()
        
        try:
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
                    
            db.commit()
            logger.info(f"✅ Сохранено {len(transactions)} транзакций китов")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения транзакций: {e}")
            db.rollback()
        finally:
            db.close()


# Функция для запуска продюсера
async def main():
    """Пример запуска продюсера"""
    producer = OnchainDataProducer()
    
    try:
        await producer.start()
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    finally:
        await producer.stop()


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())

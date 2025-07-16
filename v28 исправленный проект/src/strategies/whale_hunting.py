#!/usr/bin/env python3
"""
Стратегия "Охота на китов" (Whale Hunting)
Файл: src/strategies/whale_hunting.py

Логика:
- Мониторинг транзакций китов из таблицы whale_transactions
- Генерация сигналов на основе типа транзакции
- Учет репутации адресов и исторической эффективности
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from decimal import Decimal
import json
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import desc, and_, func
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..core.unified_config import unified_config as config
from ..core.signal_models import (
    WhaleTransaction, TransactionType, Signal as SignalExtended,
    WhaleAddress, SignalType
)
from ..strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class WhaleReputationType(Enum):
    """Типы репутации китов"""
    SMART_MONEY = "smart_money"      # Умные деньги с высоким win rate
    INSTITUTION = "institution"       # Институциональные инвесторы
    EXCHANGE = "exchange"            # Биржевые кошельки
    DEX = "dex"                      # DEX протоколы
    UNKNOWN = "unknown"              # Неизвестные адреса


@dataclass
class WhaleReputation:
    """Репутация кита"""
    address: str
    reputation_type: WhaleReputationType
    win_rate: float
    total_transactions: int
    total_volume_usd: Decimal
    confidence_modifier: float  # Модификатор уверенности на основе истории


class WhaleHuntingStrategy(BaseStrategy):
    """
    Стратегия отслеживания и копирования действий китов
    
    Генерирует торговые сигналы на основе анализа крупных транзакций:
    - Депозиты на биржи = сигнал к продаже
    - Выводы с бирж = сигнал к покупке
    - Накопление умными деньгами = сигнал к покупке
    """
    
    def __init__(self, 
                 name: str = "whale_hunting",
                 min_usd_value: float = 100_000,
                 exchange_flow_threshold: float = 500_000):
        """
        Инициализация стратегии
        
        Args:
            name: Название стратегии
            min_usd_value: Минимальная сумма транзакции для анализа (USD)
            exchange_flow_threshold: Порог для биржевых потоков (USD)
        """
        super().__init__(name)
        
        # Параметры стратегии
        self.min_usd_value = getattr(config, 'WHALE_MIN_USD_VALUE', min_usd_value)
        self.exchange_flow_threshold = exchange_flow_threshold
        self.lookback_hours = getattr(config, 'WHALE_LOOKBACK_HOURS', 24)
        self.confidence_base = getattr(config, 'WHALE_SIGNAL_CONFIDENCE', 0.7)
        
        # Кэш репутаций
        self.known_whales: Dict[str, WhaleReputation] = {}
        self.last_reputation_update = datetime.utcnow()
        self.reputation_update_interval = timedelta(hours=6)
        
        logger.info(f"✅ {self.name} инициализирована (min_value=${self.min_usd_value:,.0f})")
        
    async def analyze(self) -> List[Dict[str, Any]]:
        """
        Анализ транзакций китов и генерация сигналов
        
        Returns:
            Список сгенерированных сигналов
        """
        logger.debug(f"🔍 {self.name}: начинаем анализ транзакций...")
        
        db = SessionLocal()
        signals = []
        
        try:
            # Обновляем репутации если необходимо
            if datetime.utcnow() - self.last_reputation_update > self.reputation_update_interval:
                await self._update_whale_reputations(db)
                
            # Получаем необработанные транзакции
            recent_time = datetime.utcnow() - timedelta(hours=self.lookback_hours)
            
            whale_txs = db.query(WhaleTransaction).filter(
                and_(
                    WhaleTransaction.is_processed == False,
                    WhaleTransaction.usd_value >= self.min_usd_value,
                    WhaleTransaction.timestamp >= recent_time
                )
            ).order_by(desc(WhaleTransaction.usd_value)).limit(100).all()
            
            logger.info(f"📊 Найдено {len(whale_txs)} необработанных транзакций китов")
            
            # Анализируем каждую транзакцию
            for tx in whale_txs:
                signal = await self._analyze_transaction(tx, db)
                
                if signal:
                    signals.append(signal)
                    
                # Помечаем как обработанную
                tx.is_processed = True
                
            # Анализируем паттерны накопления
            accumulation_signals = await self._analyze_accumulation_patterns(db)
            signals.extend(accumulation_signals)
            
            # Сохраняем изменения
            db.commit()
            
            logger.info(f"✅ {self.name}: сгенерировано {len(signals)} сигналов")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в {self.name}: {e}")
            db.rollback()
        finally:
            db.close()
            
        return signals
        
    async def _analyze_transaction(self, tx: WhaleTransaction, db: Session) -> Optional[Dict[str, Any]]:
        """Анализ отдельной транзакции"""
        signal = None
        
        # Получаем репутацию адресов
        from_reputation = self._get_whale_reputation(tx.from_address)
        to_reputation = self._get_whale_reputation(tx.to_address)
        
        # Базовая уверенность
        confidence = self.confidence_base
        
        # Анализируем тип транзакции
        if tx.transaction_type == TransactionType.EXCHANGE_DEPOSIT:
            # Депозит на биржу - потенциальная продажа
            if tx.usd_value >= self.exchange_flow_threshold:
                signal = self._create_signal(
                    symbol=tx.symbol,
                    signal_type='sell',
                    confidence=confidence * 0.8,
                    reason=f"🐋 Крупный депозит ${tx.usd_value:,.0f} на биржу",
                    transaction=tx
                )
                
        elif tx.transaction_type == TransactionType.EXCHANGE_WITHDRAWAL:
            # Вывод с биржи - потенциальное накопление
            if tx.usd_value >= self.exchange_flow_threshold:
                # Проверяем репутацию получателя
                if to_reputation.reputation_type == WhaleReputationType.SMART_MONEY:
                    confidence *= to_reputation.confidence_modifier
                    
                signal = self._create_signal(
                    symbol=tx.symbol,
                    signal_type='buy',
                    confidence=confidence,
                    reason=f"🐋 Крупный вывод ${tx.usd_value:,.0f} с биржи",
                    transaction=tx
                )
                
        elif tx.transaction_type == TransactionType.TRANSFER:
            # Перевод между кошельками
            if from_reputation.reputation_type == WhaleReputationType.SMART_MONEY:
                # Smart money продает
                if to_reputation.reputation_type == WhaleReputationType.EXCHANGE:
                    signal = self._create_signal(
                        symbol=tx.symbol,
                        signal_type='sell',
                        confidence=confidence * from_reputation.confidence_modifier,
                        reason=f"💡 Smart money переводит ${tx.usd_value:,.0f} на биржу",
                        transaction=tx
                    )
            elif to_reputation.reputation_type == WhaleReputationType.SMART_MONEY:
                # Smart money покупает
                signal = self._create_signal(
                    symbol=tx.symbol,
                    signal_type='buy',
                    confidence=confidence * to_reputation.confidence_modifier,
                    reason=f"💡 Smart money накапливает ${tx.usd_value:,.0f}",
                    transaction=tx
                )
                
        # Сохраняем сигнал в БД если он был создан
        if signal:
            self._save_signal(signal, tx)
            
        return signal
        
    async def _analyze_accumulation_patterns(self, db: Session) -> List[Dict[str, Any]]:
        """Анализ паттернов накопления"""
        signals = []
        
        # Анализируем накопление за последние 7 дней
        lookback_days = 7
        start_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Группируем транзакции по символам и адресам
        accumulation_query = db.query(
            WhaleTransaction.symbol,
            WhaleTransaction.to_address,
            func.sum(WhaleTransaction.usd_value).label('total_accumulated'),
            func.count(WhaleTransaction.id).label('tx_count')
        ).filter(
            and_(
                WhaleTransaction.timestamp >= start_date,
                WhaleTransaction.transaction_type.in_([
                    TransactionType.EXCHANGE_WITHDRAWAL,
                    TransactionType.TRANSFER
                ]),
                WhaleTransaction.usd_value >= self.min_usd_value
            )
        ).group_by(
            WhaleTransaction.symbol,
            WhaleTransaction.to_address
        ).having(
            func.sum(WhaleTransaction.usd_value) >= self.exchange_flow_threshold * 2
        ).all()
        
        for row in accumulation_query:
            symbol, address, total_accumulated, tx_count = row
            
            # Проверяем репутацию
            reputation = self._get_whale_reputation(address)
            
            if reputation.reputation_type in [WhaleReputationType.SMART_MONEY, 
                                             WhaleReputationType.INSTITUTION]:
                # Генерируем сигнал накопления
                confidence = self.confidence_base * reputation.confidence_modifier
                
                # Увеличиваем уверенность при множественных транзакциях
                if tx_count > 3:
                    confidence *= 1.1
                    
                signal = {
                    'symbol': symbol,
                    'signal_type': 'buy',
                    'confidence': min(confidence, 0.95),
                    'action': 'BUY',
                    'reason': f"📈 Паттерн накопления: ${total_accumulated:,.0f} за {tx_count} транзакций",
                    'details': {
                        'pattern': 'accumulation',
                        'whale_address': address,
                        'whale_type': reputation.reputation_type.value,
                        'total_accumulated': float(total_accumulated),
                        'transaction_count': tx_count,
                        'period_days': lookback_days
                    }
                }
                
                signals.append(signal)
                
        return signals
        
    async def _update_whale_reputations(self, db: Session):
        """Обновление репутаций китов"""
        logger.info("🔄 Обновление репутаций китов...")
        
        # Получаем или создаем записи для известных адресов
        known_addresses = []
        
        # Добавляем адреса из конфига
        from ..api_clients.onchain_data_producer import OnchainDataProducer
        for exchange, networks in OnchainDataProducer.EXCHANGE_ADDRESSES.items():
            for network_addresses in networks.values():
                known_addresses.extend(network_addresses)
                
        # Обновляем репутации в БД
        for address in known_addresses:
            whale_addr = db.query(WhaleAddress).filter_by(
                address=address.lower()
            ).first()
            
            if not whale_addr:
                whale_addr = WhaleAddress(
                    address=address.lower(),
                    blockchain='ethereum',  # TODO: определять сеть
                    reputation_type='exchange',
                    label=exchange if 'exchange' in locals() else None
                )
                db.add(whale_addr)
                
        # Анализируем эффективность неизвестных адресов
        # (Здесь должна быть логика анализа win rate)
        
        db.commit()
        self.last_reputation_update = datetime.utcnow()
        
    def _get_whale_reputation(self, address: str) -> WhaleReputation:
        """Получение репутации кита"""
        address_lower = address.lower()
        
        # Проверяем кэш
        if address_lower in self.known_whales:
            return self.known_whales[address_lower]
            
        # Создаем дефолтную репутацию
        reputation = WhaleReputation(
            address=address_lower,
            reputation_type=self._determine_reputation_type(address),
            win_rate=0.5,
            total_transactions=0,
            total_volume_usd=Decimal(0),
            confidence_modifier=1.0
        )
        
        # Кэшируем
        self.known_whales[address_lower] = reputation
        
        return reputation
        
    def _determine_reputation_type(self, address: str) -> WhaleReputationType:
        """Определение типа репутации по адресу"""
        address_lower = address.lower()
        
        # Проверяем в БД
        db = SessionLocal()
        try:
            whale_addr = db.query(WhaleAddress).filter_by(
                address=address_lower
            ).first()
            
            if whale_addr:
                return WhaleReputationType(whale_addr.reputation_type)
        finally:
            db.close()
            
        # Проверяем известные биржевые адреса
        from ..api_clients.onchain_data_producer import OnchainDataProducer
        for exchange, networks in OnchainDataProducer.EXCHANGE_ADDRESSES.items():
            for network_addresses in networks.values():
                if address_lower in [addr.lower() for addr in network_addresses]:
                    return WhaleReputationType.EXCHANGE
                    
        return WhaleReputationType.UNKNOWN
        
    def _create_signal(self, symbol: str, signal_type: str, confidence: float, 
                      reason: str, transaction: WhaleTransaction) -> Dict[str, Any]:
        """Создание сигнала"""
        return {
            'symbol': symbol,
            'signal_type': signal_type,
            'confidence': confidence,
            'action': signal_type.upper(),
            'reason': reason,
            'transaction_hash': transaction.transaction_hash,
            'amount_usd': float(transaction.usd_value),
            'whale_from': transaction.from_address,
            'whale_to': transaction.to_address,
            'blockchain': transaction.blockchain,
            'details': {
                'transaction_type': transaction.transaction_type.value,
                'timestamp': transaction.timestamp.isoformat(),
                'block_number': transaction.block_number
            }
        }
        
    def _save_signal(self, signal_data: Dict[str, Any], tx: WhaleTransaction):
        """Сохранение сигнала в БД с получением актуальной цены."""
        db = SessionLocal()
        try:
            current_price = 0.0
            try:
                # Bybit использует символы без "/"
                symbol_for_ticker = signal_data['symbol'].replace('/', '')
                if not symbol_for_ticker.endswith('USDT'):
                    symbol_for_ticker += 'USDT'
                
                # Запускаем асинхронную функцию в синхронном контексте
                ticker = asyncio.run(self.exchange_client.get_ticker(symbol_for_ticker))
                if ticker and 'last' in ticker and ticker['last'] is not None:
                    current_price = float(ticker['last'])
                else:
                    logger.warning(f"Не удалось получить цену для {signal_data['symbol']} из тикера: {ticker}")
            except Exception as e:
                logger.warning(f"Не удалось получить цену для {signal_data['symbol']}: {e}")

            signal = SignalExtended(
                symbol=signal_data['symbol'],
                strategy=self.name,
                action=signal_data['action'],
                signal_type=signal_data['signal_type'],
                confidence=signal_data['confidence'],
                price=current_price, # <-- ИСПРАВЛЕНО
                reason=signal_data['reason'],
                details=signal_data.get('details', {}),
                indicators={
                    'transaction_hash': signal_data['transaction_hash'],
                    'amount_usd': signal_data['amount_usd'],
                    'whale_transaction_id': tx.id
                },
                created_at=datetime.utcnow()
            )
            db.add(signal)
            db.commit()
            logger.info(f"Сигнал сохранен: {signal_data['symbol']} {signal_data['signal_type']} @ ${current_price}")
        except Exception as e:
            logger.error(f"Ошибка сохранения сигнала: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()


# Пример использования
async def main():
    """Тестовый запуск стратегии"""
    strategy = WhaleHuntingStrategy()
    
    while True:
        try:
            signals = await strategy.analyze()
            
            if signals:
                logger.info(f"🎯 Получено {len(signals)} сигналов:")
                for signal in signals:
                    logger.info(f"  - {signal['symbol']}: {signal['signal_type']} "
                              f"(confidence: {signal['confidence']:.2%})")
                              
            await asyncio.sleep(60)  # Анализ каждую минуту
            
        except KeyboardInterrupt:
            logger.info("Остановка стратегии...")
            break
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await asyncio.sleep(10)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())

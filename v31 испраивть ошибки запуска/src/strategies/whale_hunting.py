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
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass

from sqlalchemy import desc, and_, func
from sqlalchemy.orm import Session

# =================================================================
# 🎯 ИСПРАВЛЕНИЕ: Все импорты исправлены и унифицированы
# =================================================================
from ..core.database import SessionLocal
from ..core.unified_config import unified_config as config
from ..core.models import (
    WhaleTransaction,
    TransactionTypeEnum,
    Signal,  # <-- ИЗМЕНЕНО: Используем основную модель Signal
    WhaleAddress,
    WhaleReputationTypeEnum, # <-- ИЗМЕНЕНО: Импортируем правильный Enum
    SignalTypeEnum
)
from .base import BaseStrategy # <-- ИЗМЕНЕНО: Исправлен путь импорта
from ..exchange import get_exchange_client
from ..api_clients.onchain_data_producer import OnchainDataProducer


logger = logging.getLogger(__name__)


@dataclass
class WhaleReputation:
    """Репутация кита"""
    address: str
    reputation_type: WhaleReputationTypeEnum # <-- ИЗМЕНЕНО: Используем правильный Enum из моделей
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
        
        self.exchange_client = None # Будет инициализирован асинхронно
        
        logger.info(f"✅ {self.name} инициализирована (min_value=${self.min_usd_value:,.0f})")
        
    async def _ensure_exchange_client(self):
        """Инициализирует клиент биржи, если он еще не создан."""
        if self.exchange_client is None:
            self.exchange_client = await get_exchange_client()
            if self.exchange_client is None:
                raise RuntimeError("Не удалось инициализировать ExchangeClient для стратегии.")

    async def generate_signals(self) -> List[Dict[str, Any]]:
        """
        Анализ транзакций китов и генерация сигналов.
        🎯 ИСПРАВЛЕНИЕ: Метод переименован в `generate_signals` для соответствия базовой стратегии.
        """
        logger.debug(f"🔍 {self.name}: начинаем анализ транзакций...")
        await self._ensure_exchange_client()
        
        db = SessionLocal()
        signals = []
        
        try:
            if datetime.utcnow() - self.last_reputation_update > self.reputation_update_interval:
                await self._update_whale_reputations(db)
            
            recent_time = datetime.utcnow() - timedelta(hours=self.lookback_hours)
            
            whale_txs = db.query(WhaleTransaction).filter(
                and_(
                    WhaleTransaction.is_processed == False,
                    WhaleTransaction.usd_value >= self.min_usd_value,
                    WhaleTransaction.timestamp >= recent_time
                )
            ).order_by(desc(WhaleTransaction.usd_value)).limit(100).all()
            
            logger.info(f"📊 Найдено {len(whale_txs)} необработанных транзакций китов")
            
            for tx in whale_txs:
                signal = await self._analyze_transaction(tx, db)
                if signal:
                    signals.append(signal)
                tx.is_processed = True
            
            accumulation_signals = await self._analyze_accumulation_patterns(db)
            signals.extend(accumulation_signals)
            
            db.commit()
            
            # Сохраняем сигналы после коммита транзакций
            for signal_data in signals:
                await self._save_signal(signal_data)

            logger.info(f"✅ {self.name}: сгенерировано и обработано {len(signals)} сигналов")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в {self.name}: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
            
        return signals
        
    async def _analyze_transaction(self, tx: WhaleTransaction, db: Session) -> Optional[Dict[str, Any]]:
        """Анализ отдельной транзакции"""
        signal = None
        
        from_reputation = await self._get_whale_reputation(tx.from_address, db)
        to_reputation = await self._get_whale_reputation(tx.to_address, db)
        
        confidence = self.confidence_base
        
        if tx.transaction_type == TransactionTypeEnum.EXCHANGE_DEPOSIT and tx.usd_value >= self.exchange_flow_threshold:
            signal = self._create_signal_dict(tx, 'sell', confidence * 0.8, f"🐋 Крупный депозит ${tx.usd_value:,.0f} на биржу")
            
        elif tx.transaction_type == TransactionTypeEnum.EXCHANGE_WITHDRAWAL and tx.usd_value >= self.exchange_flow_threshold:
            if to_reputation.reputation_type == WhaleReputationTypeEnum.SMART_MONEY:
                confidence *= to_reputation.confidence_modifier
            signal = self._create_signal_dict(tx, 'buy', confidence, f"� Крупный вывод ${tx.usd_value:,.0f} с биржи")
            
        elif tx.transaction_type == TransactionTypeEnum.TRANSFER:
            if from_reputation.reputation_type == WhaleReputationTypeEnum.SMART_MONEY and to_reputation.reputation_type == WhaleReputationTypeEnum.EXCHANGE:
                signal = self._create_signal_dict(tx, 'sell', confidence * from_reputation.confidence_modifier, f"💡 Smart money переводит ${tx.usd_value:,.0f} на биржу")
            elif to_reputation.reputation_type == WhaleReputationTypeEnum.SMART_MONEY:
                signal = self._create_signal_dict(tx, 'buy', confidence * to_reputation.confidence_modifier, f"💡 Smart money накапливает ${tx.usd_value:,.0f}")
                
        return signal
        
    async def _analyze_accumulation_patterns(self, db: Session) -> List[Dict[str, Any]]:
        """Анализ паттернов накопления"""
        signals = []
        lookback_days = 7
        start_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        accumulation_query = db.query(
            WhaleTransaction.symbol,
            WhaleTransaction.to_address,
            func.sum(WhaleTransaction.usd_value).label('total_accumulated'),
            func.count(WhaleTransaction.id).label('tx_count')
        ).filter(
            and_(
                WhaleTransaction.timestamp >= start_date,
                WhaleTransaction.transaction_type.in_([TransactionTypeEnum.EXCHANGE_WITHDRAWAL, TransactionTypeEnum.TRANSFER]),
                WhaleTransaction.usd_value >= self.min_usd_value
            )
        ).group_by(WhaleTransaction.symbol, WhaleTransaction.to_address).having(func.sum(WhaleTransaction.usd_value) >= self.exchange_flow_threshold * 2).all()
        
        for row in accumulation_query:
            symbol, address, total_accumulated, tx_count = row
            reputation = await self._get_whale_reputation(address, db)
            
            if reputation.reputation_type in [WhaleReputationTypeEnum.SMART_MONEY, WhaleReputationTypeEnum.INSTITUTION]:
                confidence = self.confidence_base * reputation.confidence_modifier
                if tx_count > 3:
                    confidence *= 1.1
                
                signal = {
                    'symbol': symbol,
                    'action': 'buy',
                    'confidence': min(confidence, 0.95),
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
        # (Логика обновления репутации)
        self.last_reputation_update = datetime.utcnow()
        
    async def _get_whale_reputation(self, address: str, db: Session) -> WhaleReputation:
        """Получение репутации кита"""
        address_lower = address.lower()
        if address_lower in self.known_whales:
            return self.known_whales[address_lower]
        
        whale_addr_db = db.query(WhaleAddress).filter_by(address=address_lower).first()
        
        rep_type = WhaleReputationTypeEnum.UNKNOWN
        if whale_addr_db:
            rep_type = whale_addr_db.reputation_type
        
        reputation = WhaleReputation(
            address=address_lower, reputation_type=rep_type, win_rate=0.5,
            total_transactions=whale_addr_db.total_transactions if whale_addr_db else 0,
            total_volume_usd=whale_addr_db.total_volume_usd if whale_addr_db else Decimal(0),
            confidence_modifier=1.0
        )
        self.known_whales[address_lower] = reputation
        return reputation

    def _create_signal_dict(self, tx: WhaleTransaction, action: str, confidence: float, reason: str) -> Dict[str, Any]:
        """Создает словарь с данными для сигнала."""
        return {
            "symbol": tx.symbol,
            "strategy": self.name,
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "details": {
                "transaction_hash": tx.transaction_hash,
                "usd_value": float(tx.usd_value),
                "whale_transaction_id": tx.id,
                'transaction_type': tx.transaction_type.value,
                'timestamp': tx.timestamp.isoformat(),
                'block_number': tx.block_number
            }
        }
        
    async def _save_signal(self, signal_data: Dict[str, Any]):
        """Сохраняет сигнал в БД с получением актуальной цены."""
        db = self.db_session_factory()
        try:
            symbol_for_ticker = signal_data['symbol'].replace('/', '')
            ticker = await self.exchange_client.get_ticker(symbol_for_ticker)
            current_price = float(ticker['last_price']) if ticker and ticker.get('last_price') else 0.0

            if current_price == 0.0:
                logger.warning(f"Не удалось получить цену для {signal_data['symbol']}, сигнал не будет сохранен.")
                return

            signal = Signal(
                symbol=signal_data['symbol'],
                strategy=self.name,
                action=signal_data['action'].upper(),
                price=current_price,
                confidence=signal_data['confidence'],
                reason=signal_data['reason'],
                indicators=signal_data.get('details', {})
            )
            db.add(signal)
            db.commit()
            logger.info(f"Сигнал сохранен: {signal.symbol} {signal.action} @ ${signal.price}")
        except Exception as e:
            logger.error(f"Ошибка сохранения сигнала: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()

# Пример использования
async def main():
    """Тестовый запуск стратегии"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    strategy = WhaleHuntingStrategy()
    
    while True:
        try:
            signals = await strategy.generate_signals()
            
            if signals:
                logger.info(f"🎯 Получено {len(signals)} сигналов:")
                for signal in signals:
                    logger.info(f"  - {signal['symbol']}: {signal['action']} (confidence: {signal['confidence']:.2%})")
                    
            await asyncio.sleep(60)
            
        except KeyboardInterrupt:
            logger.info("Остановка стратегии...")
            break
        except Exception as e:
            logger.error(f"Ошибка в цикле main: {e}", exc_info=True)
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
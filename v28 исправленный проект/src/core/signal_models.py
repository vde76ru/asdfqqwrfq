# Файл: src/core/signal_models.py
# Этот файл содержит все НОВЫЕ модели SQLAlchemy для системы генерации сигналов.

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    JSON, Text, Enum, ForeignKey, DECIMAL, Index, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

# Попытка импортировать базовый класс из основного файла моделей.
# Это стандартная практика, чтобы все модели использовали один Base.
try:
    from .models import Base
except ImportError:
    # Если импорт не удался (например, при отдельном запуске), создаем свой Base.
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

# --- Перечисления (Enums) для новых моделей ---

class SignalTypeEnum(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    NEUTRAL = "neutral"

class FinalSignalTypeEnum(str, enum.Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"

class TransactionTypeEnum(str, enum.Enum):
    TRANSFER = "transfer"
    EXCHANGE_DEPOSIT = "exchange_deposit"
    EXCHANGE_WITHDRAWAL = "exchange_withdrawal"
    DEX_SWAP = "dex_swap"

class AnomalyTypeEnum(str, enum.Enum):
    SPIKE = "spike"
    UNUSUAL_BUY = "unusual_buy"
    UNUSUAL_SELL = "unusual_sell"
    DIVERGENCE = "divergence"

class WhaleReputationTypeEnum(str, enum.Enum):
    SMART_MONEY = "smart_money"
    INSTITUTION = "institution"
    EXCHANGE = "exchange"
    DEX = "dex"
    UNKNOWN = "unknown"

# --- Новые модели ---

class AggregatedSignal(Base):
    """Модель для агрегированных (итоговых) сигналов по валютам."""
    __tablename__ = 'aggregated_signals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    final_signal = Column(Enum(FinalSignalTypeEnum), nullable=False, default=FinalSignalTypeEnum.NEUTRAL)
    confidence_score = Column(Float, nullable=False)
    contributing_signals = Column(JSON, nullable=False)
    buy_signals_count = Column(Integer, default=0)
    sell_signals_count = Column(Integer, default=0)
    neutral_signals_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    metadata = Column(JSON)

class WhaleTransaction(Base):
    """Модель для хранения данных о транзакциях китов."""
    __tablename__ = 'whale_transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    blockchain = Column(String(20), nullable=False)
    transaction_hash = Column(String(100), nullable=False)
    from_address = Column(String(100), nullable=False, index=True)
    to_address = Column(String(100), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    amount = Column(DECIMAL(30, 10), nullable=False)
    usd_value = Column(DECIMAL(20, 2), nullable=False, index=True)
    transaction_type = Column(Enum(TransactionTypeEnum), default=TransactionTypeEnum.TRANSFER)
    timestamp = Column(DateTime, nullable=False, index=True)
    block_number = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=func.now())
    is_processed = Column(Boolean, default=False, nullable=False, index=True, comment="Флаг обработки транзакции стратегиями")

    __table_args__ = (
        Index('idx_unique_tx', 'blockchain', 'transaction_hash', unique=True),
        Index('idx_symbol_processed_timestamp', 'symbol', 'is_processed', 'timestamp'),
    )

class OrderBookSnapshot(Base):
    """Модель для хранения снимков стакана ордеров."""
    __tablename__ = 'order_book_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    exchange = Column(String(20), nullable=False, default='bybit')
    timestamp = Column(DateTime, nullable=False)
    bids = Column(JSON, nullable=False)
    asks = Column(JSON, nullable=False)
    bid_volume = Column(DECIMAL(20, 8))
    ask_volume = Column(DECIMAL(20, 8))
    spread = Column(DECIMAL(10, 8))
    mid_price = Column(DECIMAL(20, 8))
    imbalance = Column(DECIMAL(10, 4))
    ofi = Column(DECIMAL(20, 8), comment='Order Flow Imbalance')
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_ob_symbol_timestamp', 'symbol', 'timestamp'),
    )

class VolumeAnomaly(Base):
    """Модель для хранения данных об аномальных объемах."""
    __tablename__ = 'volume_anomalies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    exchange = Column(String(20), nullable=False, default='bybit')
    anomaly_type = Column(Enum(AnomalyTypeEnum), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    volume = Column(DECIMAL(20, 8), nullable=False)
    avg_volume = Column(DECIMAL(20, 8), nullable=False)
    volume_ratio = Column(DECIMAL(10, 4), nullable=False)
    price = Column(DECIMAL(20, 8), nullable=False)
    price_change = Column(DECIMAL(10, 4))
    details = Column(JSON)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_va_symbol_timestamp', 'symbol', 'timestamp'),
    )

class WhaleAddress(Base):
    """Модель для хранения адресов китов и их репутации."""
    __tablename__ = 'whale_addresses'

    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String(100), nullable=False)
    blockchain = Column(String(20), nullable=False)
    label = Column(String(100))
    reputation_type = Column(Enum(WhaleReputationTypeEnum), default=WhaleReputationTypeEnum.UNKNOWN)
    first_seen = Column(DateTime, default=func.now())
    last_activity = Column(DateTime, default=func.now(), onupdate=func.now())
    total_transactions = Column(Integer, default=0)
    total_volume_usd = Column(DECIMAL(20, 2), default=0)
    win_rate = Column(DECIMAL(5, 2))
    metadata = Column(JSON)

    __table_args__ = (
        Index('idx_unique_whale_address', 'address', 'blockchain', unique=True),
    )

class NotificationHistory(Base):
    """Модель для истории отправленных уведомлений."""
    __tablename__ = 'notification_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    signal_id = Column(Integer, ForeignKey('signals.id'), nullable=True)
    aggregated_signal_id = Column(Integer, ForeignKey('aggregated_signals.id'), nullable=True)
    channel_type = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), default='pending') # sent, failed, pending
    error_message = Column(Text)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

    user = relationship("User")
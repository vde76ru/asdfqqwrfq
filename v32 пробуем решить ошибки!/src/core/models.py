# Файл: src/core/models.py
# Единый файл для всех моделей базы данных

from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, 
    JSON, Index, Enum as SQLEnum, DECIMAL, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from passlib.context import CryptContext
from flask_login import UserMixin
import enum

# Инициализация контекста для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base = declarative_base()

# ========== ENUMS ==========

class TradeStatus(str, Enum):
    """Статусы сделок"""
    OPEN = "open"
    CLOSED = "CLOSED"
    NEW = "NEW"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class OrderSide(str, Enum):
    """Направление сделки"""
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    """Тип ордера"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"

class SignalAction(str, Enum):
    """Действия сигнала"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class SignalTypeEnum(str, enum.Enum):
    """Типы сигналов"""
    BUY = "buy"
    SELL = "sell"
    NEUTRAL = "neutral"

class FinalSignalTypeEnum(str, enum.Enum):
    """Финальные типы агрегированных сигналов"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"

class TransactionTypeEnum(str, enum.Enum):
    """Типы транзакций китов"""
    TRANSFER = "transfer"
    EXCHANGE_DEPOSIT = "exchange_deposit"
    EXCHANGE_WITHDRAWAL = "exchange_withdrawal"
    DEX_SWAP = "dex_swap"

class AnomalyTypeEnum(str, enum.Enum):
    """Типы аномалий объемов"""
    SPIKE = "spike"
    UNUSUAL_BUY = "unusual_buy"
    UNUSUAL_SELL = "unusual_sell"
    DIVERGENCE = "divergence"

class WhaleReputationTypeEnum(str, enum.Enum):
    """Типы репутации китов"""
    SMART_MONEY = "smart_money"
    INSTITUTION = "institution"
    EXCHANGE = "exchange"
    DEX = "dex"
    UNKNOWN = "unknown"

# ========== МОДЕЛИ ПОЛЬЗОВАТЕЛЕЙ И НАСТРОЕК ==========

class User(Base, UserMixin):
    """Модель пользователя с интегрированными методами безопасности"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    blocked_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    bot_settings = relationship("BotSettings", back_populates="user", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="user", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = pwd_context.hash(password)

    def check_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.password_hash)

    def get_id(self):
        return str(self.id)

# ... (остальные методы класса User без изменений) ...


class BotSettings(Base):
    """Настройки бота для каждого пользователя"""
    __tablename__ = 'bot_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    strategy = Column(String(50), default='multi_indicator')
    risk_level = Column(Float, default=0.02)
    max_positions = Column(Integer, default=1)
    position_size = Column(Float, default=100.0)
    stop_loss_percent = Column(Float, default=2.0)
    take_profit_percent = Column(Float, default=4.0)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="bot_settings")


class BotState(Base):
    """Состояние бота"""
    __tablename__ = 'bot_state'
    
    id = Column(Integer, primary_key=True)
    is_running = Column(Boolean, default=False)
    last_heartbeat = Column(DateTime)
    current_strategy = Column(String(50))
    total_trades = Column(Integer, default=0)
    successful_trades = Column(Integer, default=0)
    failed_trades = Column(Integer, default=0)
    total_profit = Column(Float, default=0.0)
    start_time = Column(DateTime)
    stop_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ========== МОДЕЛИ БАЛАНСА И ТОРГОВЫХ ПАР ==========

class Balance(Base):
    """Балансы пользователей"""
    __tablename__ = 'balances'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    asset = Column(String(20), nullable=False)
    free = Column(Float, default=0.0)
    locked = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    usd_value = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (Index('idx_user_asset', 'user_id', 'asset', unique=True),)


class TradingPair(Base):
    """Торговые пары"""
    __tablename__ = 'trading_pairs'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), unique=True, nullable=False)
    base_asset = Column(String(10), nullable=False)
    quote_asset = Column(String(10), nullable=False)
    is_active = Column(Boolean, default=True)
    strategy = Column(String(50), default='multi_indicator')
    stop_loss_percent = Column(Float, default=2.0)
    take_profit_percent = Column(Float, default=4.0)
    min_position_size = Column(Float)
    max_position_size = Column(Float)
    min_order_size = Column(Float)
    max_order_size = Column(Float)
    price_precision = Column(Integer)
    quantity_precision = Column(Integer)
    status = Column(String(20), default='TRADING')
    position_size_percent = Column(Float, default=10.0)
    risk_level = Column(String(20), default='medium')
    last_strategy_update = Column(DateTime)
    last_analysis_time = Column(DateTime)
    volatility_24h = Column(Float)
    volume_24h = Column(Float)
    price_change_24h = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_trading_pair_symbol', 'symbol'),
        Index('idx_trading_pair_active', 'is_active'),
        Index('idx_trading_pair_strategy', 'strategy'),
        Index('idx_trading_pair_strategy_update', 'last_strategy_update'),
    )

# ========== МОДЕЛИ ТОРГОВЛИ ==========

class Position(Base):
    """Открытые торговые позиции"""
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(SQLEnum(OrderSide), nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    liquidation_price = Column(Float)
    status = Column(String(20), default='OPEN', nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="positions")

    __table_args__ = (Index('idx_position_user_symbol', 'user_id', 'symbol', unique=True),)


class Signal(Base):
    """Торговые сигналы (ЕДИНОЕ ОПРЕДЕЛЕНИЕ)"""
    __tablename__ = 'signals'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    strategy = Column(String(50), nullable=False)
    action = Column(String(10), nullable=False)  # BUY, SELL, HOLD
    price = Column(Float, nullable=False)
    confidence = Column(Float, default=0.0)
    indicators = Column(JSON)  # Значения индикаторов
    reason = Column(Text)
    is_executed = Column(Boolean, default=False)
    executed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    trades = relationship("Trade", back_populates="signal")
    
    __table_args__ = (
        Index('idx_signal_symbol_created', 'symbol', 'created_at'),
        Index('idx_signal_strategy', 'strategy'),
    )


class Trade(Base):
    """История сделок"""
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    signal_id = Column(Integer, ForeignKey('signals.id'))
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # BUY, SELL
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    fee = Column(Float, default=0.0)
    fee_asset = Column(String(10))
    status = Column(String(20), default='NEW')  # NEW, FILLED, CANCELLED
    order_id = Column(String(100))
    strategy = Column(String(50))
    stop_loss = Column(Float)
    take_profit = Column(Float)
    profit_loss = Column(Float)
    profit_loss_percent = Column(Float)
    close_price = Column(Float)
    close_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="trades")
    signal = relationship("Signal", back_populates="trades")
    ml_predictions = relationship("TradeMLPrediction", back_populates="trade")
    
    __table_args__ = (
        Index('idx_trade_user_created', 'user_id', 'created_at'),
        Index('idx_trade_symbol', 'symbol'),
    )


class Order(Base):
    """Активные ордера"""
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    exchange_order_id = Column(String(100), unique=True)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    type = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float)
    stop_price = Column(Float)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ========== МОДЕЛИ РЫНОЧНЫХ ДАННЫХ ==========

class Candle(Base):
    """Свечи для анализа"""
    __tablename__ = 'candles'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    interval = Column(String(10), nullable=False)
    open_time = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    close_time = Column(DateTime, nullable=False)
    
    __table_args__ = (Index('idx_candle_symbol_time', 'symbol', 'interval', 'open_time', unique=True),)


class MarketData(Base):
    """Последние рыночные данные (тикеры)"""
    __tablename__ = 'market_data'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    last_price = Column(Float, nullable=False)
    price_24h_pcnt = Column(Float)
    high_price_24h = Column(Float)
    low_price_24h = Column(Float)
    volume_24h = Column(Float)
    turnover_24h = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MarketCondition(Base):
    """Рыночные условия"""
    __tablename__ = 'market_conditions'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(20), nullable=False)
    condition_type = Column(String(50), nullable=False)
    condition_value = Column(String(50), nullable=False)
    strength = Column(Float)
    indicators = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    trend = Column(String(20))
    volatility = Column(String(20))
    volume_trend = Column(String(20))
    support_level = Column(Float)
    resistance_level = Column(Float)
    rsi = Column(Float)
    macd_signal = Column(String(20))
    market_phase = Column(String(30))
    
    __table_args__ = (
        Index('idx_symbol_timestamp', 'symbol', 'timestamp'),
        Index('idx_condition_type', 'condition_type'),
    )

# ========== МОДЕЛИ СИГНАЛОВ (ПЕРЕНЕСЕННЫЕ) ==========

class AggregatedSignal(Base):
    """Агрегированные (итоговые) сигналы по валютам."""
    __tablename__ = 'aggregated_signals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    final_signal = Column(SQLEnum(FinalSignalTypeEnum), nullable=False, default=FinalSignalTypeEnum.NEUTRAL)
    confidence_score = Column(Float, nullable=False)
    contributing_signals = Column(JSON, nullable=False)
    buy_signals_count = Column(Integer, default=0)
    sell_signals_count = Column(Integer, default=0)
    neutral_signals_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    details = Column(JSON)


class WhaleTransaction(Base):
    """Транзакции китов."""
    __tablename__ = 'whale_transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    blockchain = Column(String(20), nullable=False)
    transaction_hash = Column(String(100), nullable=False)
    from_address = Column(String(100), nullable=False, index=True)
    to_address = Column(String(100), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    amount = Column(DECIMAL(30, 10), nullable=False)
    usd_value = Column(DECIMAL(20, 2), nullable=False, index=True)
    transaction_type = Column(SQLEnum(TransactionTypeEnum), default=TransactionTypeEnum.TRANSFER)
    timestamp = Column(DateTime, nullable=False, index=True)
    block_number = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=func.now())
    is_processed = Column(Boolean, default=False, nullable=False, index=True)

    __table_args__ = (
        Index('idx_unique_tx', 'blockchain', 'transaction_hash', unique=True),
        Index('idx_symbol_processed_timestamp', 'symbol', 'is_processed', 'timestamp'),
    )


class OrderBookSnapshot(Base):
    """Снимки стакана ордеров."""
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

    __table_args__ = (Index('idx_ob_symbol_timestamp', 'symbol', 'timestamp'),)


class VolumeAnomaly(Base):
    """Аномальные объемы."""
    __tablename__ = 'volume_anomalies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    exchange = Column(String(20), nullable=False, default='bybit')
    anomaly_type = Column(SQLEnum(AnomalyTypeEnum), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    volume = Column(DECIMAL(20, 8), nullable=False)
    avg_volume = Column(DECIMAL(20, 8), nullable=False)
    volume_ratio = Column(DECIMAL(10, 4), nullable=False)
    price = Column(DECIMAL(20, 8), nullable=False)
    price_change = Column(DECIMAL(10, 4))
    details = Column(JSON)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (Index('idx_va_symbol_timestamp', 'symbol', 'timestamp'),)


class WhaleAddress(Base):
    """Адреса китов и их репутация."""
    __tablename__ = 'whale_addresses'

    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String(100), nullable=False)
    blockchain = Column(String(20), nullable=False)
    label = Column(String(100))
    reputation_type = Column(SQLEnum(WhaleReputationTypeEnum), default=WhaleReputationTypeEnum.UNKNOWN)
    first_seen = Column(DateTime, default=func.now())
    last_activity = Column(DateTime, default=func.now(), onupdate=func.now())
    total_transactions = Column(Integer, default=0)
    total_volume_usd = Column(DECIMAL(20, 2), default=0)
    win_rate = Column(DECIMAL(5, 2))
    details = Column(JSON)

    __table_args__ = (Index('idx_unique_whale_address', 'address', 'blockchain', unique=True),)


class NotificationHistory(Base):
    """История отправленных уведомлений."""
    __tablename__ = 'notification_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    signal_id = Column(Integer, ForeignKey('signals.id'), nullable=True)
    aggregated_signal_id = Column(Integer, ForeignKey('aggregated_signals.id'), nullable=True)
    channel_type = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), default='pending')
    error_message = Column(Text)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

    user = relationship("User")

# ========== МОДЕЛИ ПРОИЗВОДИТЕЛЬНОСТИ И ML ==========

class StrategyPerformance(Base):
    """Производительность стратегий"""
    __tablename__ = 'strategy_performance'
    
    id = Column(Integer, primary_key=True)
    strategy_name = Column(String(50), nullable=False)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    total_profit = Column(Float, default=0.0)
    total_loss = Column(Float, default=0.0)
    net_profit = Column(Float, default=0.0)
    avg_profit = Column(Float, default=0.0)
    avg_loss = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (Index('idx_strategy_performance', 'strategy_name'),)


class MLModel(Base):
    """Модели машинного обучения"""
    __tablename__ = 'ml_models'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    model_type = Column(String(50), nullable=False)
    version = Column(String(20))
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    parameters = Column(JSON)
    feature_importance = Column(JSON)
    training_data_size = Column(Integer)
    is_active = Column(Boolean, default=False)
    model_path = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MLPrediction(Base):
    """Предсказания ML моделей"""
    __tablename__ = 'ml_predictions'
    
    id = Column(Integer, primary_key=True)
    model_id = Column(Integer, ForeignKey('ml_models.id'))
    symbol = Column(String(20), nullable=False)
    prediction = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    predicted_price = Column(Float)
    actual_price = Column(Float)
    features = Column(JSON)
    is_correct = Column(Boolean)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_ml_prediction_symbol', 'symbol'),
        Index('idx_ml_prediction_created', 'created_at'),
    )


class TradeMLPrediction(Base):
    """ML предсказания для конкретных сделок"""
    __tablename__ = 'trade_ml_predictions'
    
    id = Column(Integer, primary_key=True)
    trade_id = Column(Integer, ForeignKey('trades.id'), nullable=False)
    model_name = Column(String(50), nullable=False)
    prediction = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    predicted_profit = Column(Float)
    actual_profit = Column(Float)
    features_used = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    trade = relationship("Trade", back_populates="ml_predictions")

# ========== МОДЕЛИ АНАЛИЗА НОВОСТЕЙ И СОЦИАЛЬНЫХ СЕТЕЙ ==========

class NewsAnalysis(Base):
    """Анализ новостей"""
    __tablename__ = 'news_analysis'
    
    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text)
    url = Column(String(500))
    sentiment = Column(String(20))
    sentiment_score = Column(Float)
    impact_score = Column(Float)
    related_symbols = Column(JSON)
    keywords = Column(JSON)
    published_at = Column(DateTime)
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_news_published', 'published_at'),
        Index('idx_news_sentiment', 'sentiment'),
    )


class SocialSignal(Base):
    """Социальные сигналы"""
    __tablename__ = 'social_signals'
    
    id = Column(Integer, primary_key=True)
    platform = Column(String(30), nullable=False)
    symbol = Column(String(20))
    content = Column(Text)
    author = Column(String(100))
    sentiment = Column(String(20))
    sentiment_score = Column(Float)
    engagement_score = Column(Float)
    followers_count = Column(Integer)
    is_influencer = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_social_symbol', 'symbol'),
        Index('idx_social_platform', 'platform'),
    )

# ========== МОДЕЛИ ЛОГИРОВАНИЯ ==========

class TradingLog(Base):
    """Логи торговых операций"""
    __tablename__ = 'trading_logs'
    
    id = Column(Integer, primary_key=True)
    log_level = Column(String(20), nullable=False)
    category = Column(String(50))
    message = Column(Text, nullable=False)
    context = Column(JSON)
    symbol = Column(String(20))
    strategy = Column(String(50))
    trade_id = Column(Integer)
    signal_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_log_level', 'log_level'),
        Index('idx_log_category', 'category'),
        Index('idx_log_created', 'created_at'),
    )

# ========== АЛИАСЫ ДЛЯ СОВМЕСТИМОСТИ ==========
SignalExtended = Signal

# ========== ЭКСПОРТ ВСЕХ МОДЕЛЕЙ ==========

__all__ = [
    'Base',
    'TradeStatus', 'OrderSide', 'OrderType', 'SignalAction',
    'SignalTypeEnum', 'FinalSignalTypeEnum', 'TransactionTypeEnum', 
    'AnomalyTypeEnum', 'WhaleReputationTypeEnum',
    'User', 'BotSettings', 'BotState',
    'Balance', 'TradingPair', 'Position', 'Signal', 'Trade', 'Order',
    'Candle', 'MarketData', 'MarketCondition',
    'AggregatedSignal', 'WhaleTransaction', 'OrderBookSnapshot', 
    'VolumeAnomaly', 'WhaleAddress', 'NotificationHistory',
    'StrategyPerformance', 'MLModel', 'MLPrediction', 'TradeMLPrediction',
    'NewsAnalysis', 'SocialSignal',
    'TradingLog',
    'SignalExtended'
]

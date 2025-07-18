"""
Типы данных для BotManager
Файл: src/bot/internal/types.py

Все Enums и Dataclasses, вынесенные из manager.py
"""

from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque


class BotStatus(Enum):
    """Статусы бота"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    PAUSED = "paused"
    EMERGENCY_STOP = "emergency_stop"


class ComponentStatus(Enum):
    """Статусы компонентов"""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing" 
    READY = "ready"
    FAILED = "failed"
    DISABLED = "disabled"
    RECONNECTING = "reconnecting"


class MarketPhase(Enum):
    """Фазы рынка"""
    ACCUMULATION = "accumulation"    # Накопление
    MARKUP = "markup"                # Рост
    DISTRIBUTION = "distribution"    # Распределение  
    MARKDOWN = "markdown"            # Падение
    UNKNOWN = "unknown"              # Неопределенная


class RiskLevel(Enum):
    """Уровни риска"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class TradeDecision(Enum):
    """Решения по сделкам"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    WEAK_BUY = "weak_buy"
    HOLD = "hold"
    WEAK_SELL = "weak_sell"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class TradingOpportunity:
    """Расширенная торговая возможность"""
    symbol: str
    strategy: str
    decision: TradeDecision
    confidence: float               # Уверенность 0-1
    expected_profit: float          # Ожидаемая прибыль %
    expected_loss: float           # Ожидаемый убыток %
    risk_level: RiskLevel
    price: float                   # Цена входа
    stop_loss: float              # Стоп-лосс
    take_profit: float            # Тейк-профит
    market_phase: MarketPhase
    volume_score: float           # Скор объема 0-1
    technical_score: float        # Технический анализ 0-1
    ml_score: float              # ML предсказание 0-1
    news_sentiment: float        # Настроение новостей -1 to 1
    social_sentiment: float      # Социальное настроение -1 to 1
    risk_reward_ratio: float     # Соотношение риск/доходность
    correlation_risk: float      # Риск корреляции 0-1
    volatility: float           # Волатильность
    liquidity_score: float      # Ликвидность 0-1
    timeframe: str              # Таймфрейм анализа
    entry_reasons: List[str]    # Причины входа
    exit_conditions: List[str]  # Условия выхода
    metadata: Dict[str, Any]    # Дополнительные данные
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))


@dataclass
class MarketState:
    """Расширенное состояние рынка"""
    overall_trend: str              # BULLISH, BEARISH, SIDEWAYS
    volatility: str                 # LOW, MEDIUM, HIGH, EXTREME
    fear_greed_index: int          # 0-100
    market_cap: float              # Общая капитализация
    volume_24h: float              # Объем за 24ч
    dominance_btc: float           # Доминирование BTC
    dominance_eth: float           # Доминирование ETH
    active_pairs_count: int        # Количество активных пар
    trending_pairs: List[str]      # Трендовые пары
    declining_pairs: List[str]     # Падающие пары
    correlation_matrix: Dict[str, Dict[str, float]]  # Матрица корреляций
    sector_performance: Dict[str, float]  # Производительность секторов
    market_regime: str             # BULL_MARKET, BEAR_MARKET, SIDEWAYS_MARKET
    risk_level: RiskLevel         # Общий уровень риска
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ComponentInfo:
    """Информация о компоненте системы"""
    name: str
    status: ComponentStatus
    instance: Any = None
    error: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    restart_count: int = 0
    dependencies: List[str] = field(default_factory=list)
    is_critical: bool = False
    health_check_interval: int = 60
    max_restart_attempts: int = 3


@dataclass
class PerformanceMetrics:
    """Метрики производительности"""
    analysis_time_avg: float = 0.0
    trade_execution_time_avg: float = 0.0
    pairs_per_second: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    network_latency_ms: float = 0.0
    error_rate_percent: float = 0.0
    uptime_seconds: float = 0.0
    cycles_per_hour: float = 0.0
    api_calls_per_minute: float = 0.0


@dataclass
class TradingStatistics:
    """Расширенная торговая статистика"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit_usd: float = 0.0
    total_loss_usd: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    average_win: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    trades_per_day: float = 0.0
    average_trade_duration: float = 0.0
    start_balance: float = 0.0
    current_balance: float = 0.0
    peak_balance: float = 0.0
    roi_percent: float = 0.0
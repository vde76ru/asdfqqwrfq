#!/usr/bin/env python3
"""
Агрегатор торговых сигналов
Файл: src/strategies/signal_aggregator.py

Функции:
- Мониторинг новых сигналов от всех стратегий
- Группировка сигналов по валютам
- Вычисление итогового сигнала и уверенности
- Учет весов и приоритетов стратегий
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import numpy as np
from collections import defaultdict

from ..core.database import SessionLocal
from ..core.signal_models import (
    SignalExtended, SignalType, AggregatedSignal, FinalSignalType
)
from ..core.unified_config import unified_config as config

logger = logging.getLogger(__name__)

@dataclass
class StrategyWeight:
    """Вес и параметры стратегии"""
    name: str
    weight: float  # Базовый вес стратегии
    reliability: float  # Надежность (0-1)
    min_confidence: float  # Минимальная уверенность для учета
    priority: int  # Приоритет (выше = важнее)
    
@dataclass
class SignalGroup:
    """Группа сигналов для одной валюты"""
    symbol: str
    signals: List[SignalExtended] = field(default_factory=list)
    buy_count: int = 0
    sell_count: int = 0
    neutral_count: int = 0
    total_confidence: float = 0.0
    weighted_confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

class SignalAggregator:
    """
    Сервис агрегации сигналов от различных стратегий
    """
    
    # Веса стратегий (можно вынести в конфигурацию)
    STRATEGY_WEIGHTS = {
        'whale_hunting': StrategyWeight(
            name='whale_hunting',
            weight=1.5,
            reliability=0.75,
            min_confidence=0.3,
            priority=8
        ),
        'sleeping_giants': StrategyWeight(
            name='sleeping_giants',
            weight=1.2,
            reliability=0.8,
            min_confidence=0.4,
            priority=7
        ),
        'order_book_analysis': StrategyWeight(
            name='order_book_analysis',
            weight=1.0,
            reliability=0.7,
            min_confidence=0.35,
            priority=6
        ),
        'technical_analysis': StrategyWeight(
            name='technical_analysis',
            weight=0.8,
            reliability=0.65,
            min_confidence=0.4,
            priority=5
        )
    }
    
    def __init__(self):
        """Инициализация агрегатора"""
        self.db = SessionLocal()
        self.is_running = False
        
        # Настройки
        self.check_interval = 10  # Проверка каждые 10 секунд
        self.aggregation_window = 60  # Окно агрегации в секундах
        self.min_signals_required = 2  # Минимум сигналов для агрегации
        
        # Кэш обработанных сигналов
        self.processed_signals = set()
        self.last_aggregation = {}
        
        logger.info("📊 SignalAggregator инициализирован")
    
    async def start(self):
        """Запуск агрегатора"""
        logger.info("🚀 Запуск SignalAggregator")
        self.is_running = True
        
        while self.is_running:
            try:
                await self._aggregate_signals()
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле агрегации: {e}")
                await asyncio.sleep(30)
    
    async def stop(self):
        """Остановка агрегатора"""
        logger.info("🛑 Остановка SignalAggregator")
        self.is_running = False
        
        if self.db:
            self.db.close()
    
    async def _aggregate_signals(self):
        """Основной цикл агрегации сигналов"""
        try:
            # Получаем новые сигналы за последнее окно
            window_start = datetime.utcnow() - timedelta(seconds=self.aggregation_window)
            
            signals = self.db.query(SignalExtended).filter(
                SignalExtended.created_at >= window_start,
                SignalExtended.id.notin_(self.processed_signals)
            ).all()
            
            if not signals:
                return
            
            logger.info(f"📥 Найдено {len(signals)} новых сигналов для агрегации")
            
            # Группируем сигналы по символам
            signal_groups = self._group_signals_by_symbol(signals)
            
            # Обрабатываем каждую группу
            for symbol, group in signal_groups.items():
                if len(group.signals) >= self.min_signals_required:
                    aggregated = await self._process_signal_group(group)
                    
                    if aggregated:
                        self._save_aggregated_signal(aggregated, group)
            
            # Добавляем обработанные сигналы в кэш
            for signal in signals:
                self.processed_signals.add(signal.id)
            
            # Очищаем старые записи из кэша
            self._cleanup_cache()
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"❌ Ошибка агрегации: {e}")
            self.db.rollback()
    
    def _group_signals_by_symbol(self, signals: List[SignalExtended]) -> Dict[str, SignalGroup]:
        """Группировка сигналов по символам"""
        groups = defaultdict(lambda: SignalGroup(symbol=''))
        
        for signal in signals:
            group = groups[signal.symbol]
            group.symbol = signal.symbol
            group.signals.append(signal)
            
            # Подсчет типов сигналов
            if signal.signal_type == SignalType.BUY:
                group.buy_count += 1
            elif signal.signal_type == SignalType.SELL:
                group.sell_count += 1
            else:
                group.neutral_count += 1
            
            # Суммируем уверенность
            group.total_confidence += signal.confidence
        
        return dict(groups)
    
    async def _process_signal_group(self, group: SignalGroup) -> Optional[Dict[str, Any]]:
        """Обработка группы сигналов для одного символа"""
        try:
            # Вычисляем взвешенные значения
            weighted_buy = 0.0
            weighted_sell = 0.0
            total_weight = 0.0
            
            strategy_signals = {}  # Сигналы по стратегиям
            
            for signal in group.signals:
                # Получаем вес стратегии
                strategy_weight = self.STRATEGY_WEIGHTS.get(
                    signal.strategy,
                    StrategyWeight(signal.strategy, 1.0, 0.5, 0.3, 5)
                )
                
                # Проверяем минимальную уверенность
                if signal.confidence < strategy_weight.min_confidence:
                    continue
                
                # Вычисляем эффективный вес
                effective_weight = (
                    strategy_weight.weight * 
                    strategy_weight.reliability * 
                    signal.confidence
                )
                
                # Добавляем к соответствующему типу
                if signal.signal_type == SignalType.BUY:
                    weighted_buy += effective_weight
                elif signal.signal_type == SignalType.SELL:
                    weighted_sell += effective_weight
                
                total_weight += effective_weight
                
                # Сохраняем для анализа
                strategy_signals[signal.strategy] = {
                    'signal': signal,
                    'weight': effective_weight,
                    'priority': strategy_weight.priority
                }
            
            if total_weight == 0:
                return None
            
            # Нормализуем веса
            buy_score = weighted_buy / total_weight
            sell_score = weighted_sell / total_weight
            
            # Определяем итоговый сигнал
            final_signal, confidence = self._determine_final_signal(
                buy_score, sell_score, group, strategy_signals
            )
            
            if final_signal == FinalSignalType.NEUTRAL:
                return None  # Не создаем агрегированные нейтральные сигналы
            
            # Формируем метаданные
            metadata = self._generate_metadata(group, strategy_signals)
            
            return {
                'symbol': group.symbol,
                'final_signal': final_signal,
                'confidence_score': confidence,
                'buy_score': buy_score,
                'sell_score': sell_score,
                'contributing_signals': [s.id for s in group.signals],
                'details': metadata
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки группы {group.symbol}: {e}")
            return None
    
    def _determine_final_signal(self, buy_score: float, sell_score: float, 
                                group: SignalGroup, 
                                strategy_signals: Dict) -> Tuple[FinalSignalType, float]:
        """Определение итогового сигнала и уверенности"""
        # Разница между сигналами
        signal_diff = buy_score - sell_score
        abs_diff = abs(signal_diff)
        
        # Учитываем количество стратегий
        strategy_count = len(strategy_signals)
        consensus_factor = min(strategy_count / 3, 1.0)  # Максимум при 3+ стратегиях
        
        # Базовая уверенность
        base_confidence = abs_diff * consensus_factor
        
        # Корректируем на основе приоритетов
        max_priority = max(s['priority'] for s in strategy_signals.values())
        priority_factor = 0.5 + (max_priority / 10) * 0.5  # От 0.5 до 1.0
        
        confidence = min(base_confidence * priority_factor, 1.0)
        
        # Определяем тип сигнала
        if signal_diff > 0.6 and confidence > 0.7:
            return FinalSignalType.STRONG_BUY, confidence
        elif signal_diff > 0.3:
            return FinalSignalType.BUY, confidence
        elif signal_diff < -0.6 and confidence > 0.7:
            return FinalSignalType.STRONG_SELL, confidence
        elif signal_diff < -0.3:
            return FinalSignalType.SELL, confidence
        else:
            return FinalSignalType.NEUTRAL, confidence
    
    def _generate_metadata(self, group: SignalGroup, 
                          strategy_signals: Dict) -> Dict[str, Any]:
        """Генерация метаданных для агрегированного сигнала"""
        # Сортируем стратегии по весу
        sorted_strategies = sorted(
            strategy_signals.items(),
            key=lambda x: x[1]['weight'],
            reverse=True
        )
        
        # Формируем список стратегий с их вкладом
        strategy_contributions = []
        for strategy_name, data in sorted_strategies:
            signal = data['signal']
            contribution = {
                'strategy': strategy_name,
                'signal_type': signal.signal_type.value,
                'confidence': signal.confidence,
                'weight': data['weight'],
                'reason': signal.reason
            }
            strategy_contributions.append(contribution)
        
        # Вычисляем дополнительные метрики
        confidences = [s.confidence for s in group.signals]
        
        metadata = {
            'total_signals': len(group.signals),
            'buy_signals': group.buy_count,
            'sell_signals': group.sell_count,
            'strategy_contributions': strategy_contributions,
            'average_confidence': np.mean(confidences),
            'confidence_std': np.std(confidences),
            'aggregation_timestamp': datetime.utcnow().isoformat(),
            'window_seconds': self.aggregation_window
        }
        
        return metadata
    
    def _save_aggregated_signal(self, aggregated_data: Dict[str, Any], 
                               group: SignalGroup):
        """Сохранение агрегированного сигнала в БД"""
        try:
            # Проверяем, не было ли недавно похожего сигнала
            recent_check = datetime.utcnow() - timedelta(minutes=5)
            existing = self.db.query(AggregatedSignal).filter(
                AggregatedSignal.symbol == aggregated_data['symbol'],
                AggregatedSignal.created_at >= recent_check
            ).first()
            
            if existing and existing.final_signal == aggregated_data['final_signal']:
                # Обновляем существующий сигнал
                existing.confidence_score = max(
                    existing.confidence_score,
                    aggregated_data['confidence_score']
                )
                existing.updated_at = datetime.utcnow()
                logger.info(f"📈 Обновлен существующий агрегированный сигнал {existing.symbol}")
                return
            
            # Создаем новый агрегированный сигнал
            agg_signal = AggregatedSignal(
                symbol=aggregated_data['symbol'],
                final_signal=aggregated_data['final_signal'],
                confidence_score=aggregated_data['confidence_score'],
                contributing_signals=aggregated_data['contributing_signals'],
                buy_signals_count=group.buy_count,
                sell_signals_count=group.sell_count,
                neutral_signals_count=group.neutral_count,
                details=aggregated_data['metadata']
            )
            
            self.db.add(agg_signal)
            
            # Обновляем время последней агрегации
            self.last_aggregation[aggregated_data['symbol']] = datetime.utcnow()
            
            logger.info(
                f"🎯 Новый агрегированный сигнал: {agg_signal.symbol} "
                f"{agg_signal.final_signal.value} (confidence: {agg_signal.confidence_score:.2f})"
            )
            
            # Если сигнал сильный, можем отправить уведомление
            if (agg_signal.final_signal in [FinalSignalType.STRONG_BUY, FinalSignalType.STRONG_SELL] 
                and agg_signal.confidence_score > 0.8):
                logger.warning(
                    f"⚡ СИЛЬНЫЙ СИГНАЛ: {agg_signal.symbol} "
                    f"{agg_signal.final_signal.value} ({agg_signal.confidence_score:.2f})"
                )
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения агрегированного сигнала: {e}")
            raise
    
    def _cleanup_cache(self):
        """Очистка кэша обработанных сигналов"""
        # Удаляем старые ID из кэша (старше 1 часа)
        if len(self.processed_signals) > 10000:
            # Очищаем половину кэша если он слишком большой
            self.processed_signals = set(list(self.processed_signals)[-5000:])
    
    def get_latest_aggregated_signals(self, limit: int = 20) -> List[AggregatedSignal]:
        """Получение последних агрегированных сигналов"""
        try:
            return self.db.query(AggregatedSignal).order_by(
                AggregatedSignal.created_at.desc()
            ).limit(limit).all()
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сигналов: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики работы агрегатора"""
        try:
            since_24h = datetime.utcnow() - timedelta(hours=24)
            
            total_aggregated = self.db.query(AggregatedSignal).filter(
                AggregatedSignal.created_at >= since_24h
            ).count()
            
            by_type = self.db.query(
                AggregatedSignal.final_signal,
                self.db.func.count(AggregatedSignal.id)
            ).filter(
                AggregatedSignal.created_at >= since_24h
            ).group_by(
                AggregatedSignal.final_signal
            ).all()
            
            type_stats = {t.value: c for t, c in by_type}
            
            return {
                'is_running': self.is_running,
                'period': '24h',
                'total_aggregated_signals': total_aggregated,
                'signals_by_type': type_stats,
                'cached_processed_signals': len(self.processed_signals),
                'active_strategies': len(self.STRATEGY_WEIGHTS)
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}

# Функция для запуска агрегатора
async def main():
    """Пример запуска агрегатора"""
    aggregator = SignalAggregator()
    
    try:
        await aggregator.start()
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    finally:
        await aggregator.stop()

if __name__ == "__main__":
    asyncio.run(main())

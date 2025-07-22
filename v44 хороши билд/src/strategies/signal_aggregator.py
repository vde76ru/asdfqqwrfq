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

# ИСПРАВЛЕНО: Правильные импорты из core.models
from ..core.database import SessionLocal
from ..core.models import (
    Signal as SignalExtended,  # Используем алиас из models.py
    SignalTypeEnum as SignalType,  # Правильное имя enum
    AggregatedSignal,
    FinalSignalTypeEnum as FinalSignalType  # Правильное имя enum
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
    
    def __init__(self, aggregation_window: int = 60):
        """
        Инициализация агрегатора
        
        Args:
            aggregation_window: Окно агрегации в секундах
        """
        self.aggregation_window = aggregation_window
        self.is_running = False
        self.db = None
        self.processed_signals = set()  # Кэш обработанных сигналов
        self.last_cleanup = datetime.utcnow()
        
        logger.info(f"SignalAggregator инициализирован (окно={aggregation_window}с)")
    
    async def start(self):
        """Запуск агрегатора"""
        logger.info("🚀 Запуск SignalAggregator")
        self.is_running = True
        
        try:
            while self.is_running:
                await self.run()
                await asyncio.sleep(10)  # Проверка каждые 10 секунд
        except Exception as e:
            logger.error(f"Ошибка в основном цикле агрегатора: {e}")
        finally:
            self.is_running = False
    
    async def stop(self):
        """Остановка агрегатора"""
        logger.info("🛑 Остановка SignalAggregator")
        self.is_running = False
    
    async def run(self):
        """Основной цикл агрегации"""
        try:
            self.db = SessionLocal()
            
            # Получаем новые сигналы
            new_signals = await self._get_new_signals()
            
            if not new_signals:
                return
            
            logger.info(f"📊 Найдено {len(new_signals)} новых сигналов для агрегации")
            
            # Группируем по символам
            signal_groups = self._group_signals_by_symbol(new_signals)
            
            # Обрабатываем каждую группу
            for symbol, group in signal_groups.items():
                aggregated = await self._process_signal_group(group)
                
                if aggregated:
                    self._save_aggregated_signal(aggregated, group)
                    logger.info(
                        f"✅ Агрегирован сигнал для {symbol}: "
                        f"{aggregated['final_signal_type']} "
                        f"(confidence={aggregated['confidence']:.2%})"
                    )
            
            # Добавляем обработанные сигналы в кэш
            for signal in new_signals:
                self.processed_signals.add(signal.id)
            
            # Очищаем старые записи из кэша
            self._cleanup_cache()
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"❌ Ошибка агрегации: {e}")
            if self.db:
                self.db.rollback()
        finally:
            if self.db:
                self.db.close()
                self.db = None
    
    async def _get_new_signals(self) -> List[SignalExtended]:
        """Получение новых сигналов для агрегации"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(seconds=self.aggregation_window)
            
            # Получаем сигналы за последний период
            signals = self.db.query(SignalExtended).filter(
                SignalExtended.created_at > cutoff_time,
                ~SignalExtended.id.in_(self.processed_signals) if self.processed_signals else True
            ).all()
            
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка получения новых сигналов: {e}")
            return []
    
    def _group_signals_by_symbol(self, signals: List[SignalExtended]) -> Dict[str, SignalGroup]:
        """Группировка сигналов по символам"""
        groups = defaultdict(lambda: SignalGroup(symbol=''))
        
        for signal in signals:
            group = groups[signal.symbol]
            group.symbol = signal.symbol
            group.signals.append(signal)
            
            # Подсчет типов сигналов
            # Обработка разных способов хранения типа сигнала
            if hasattr(signal, 'signal_type'):
                signal_type = signal.signal_type
            elif hasattr(signal, 'action'):
                # Преобразуем action в signal_type
                action_to_type = {
                    'BUY': SignalType.BUY,
                    'SELL': SignalType.SELL,
                    'HOLD': SignalType.NEUTRAL
                }
                signal_type = action_to_type.get(signal.action, SignalType.NEUTRAL)
            else:
                signal_type = SignalType.NEUTRAL
            
            if signal_type == SignalType.BUY:
                group.buy_count += 1
            elif signal_type == SignalType.SELL:
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
                
                # Определяем тип сигнала
                if hasattr(signal, 'signal_type'):
                    signal_type = signal.signal_type
                elif hasattr(signal, 'action'):
                    # Преобразуем action в signal_type
                    action_to_type = {
                        'BUY': SignalType.BUY,
                        'SELL': SignalType.SELL,
                        'HOLD': SignalType.NEUTRAL
                    }
                    signal_type = action_to_type.get(signal.action, SignalType.NEUTRAL)
                else:
                    signal_type = SignalType.NEUTRAL
                
                # Добавляем к соответствующему типу
                if signal_type == SignalType.BUY:
                    weighted_buy += effective_weight
                elif signal_type == SignalType.SELL:
                    weighted_sell += effective_weight
                
                total_weight += effective_weight
                
                # Сохраняем сигнал стратегии
                strategy_signals[signal.strategy] = {
                    'signal': signal,
                    'weight': effective_weight,
                    'priority': strategy_weight.priority
                }
            
            # Если нет валидных сигналов
            if total_weight == 0:
                return None
            
            # Нормализуем веса
            weighted_buy /= total_weight
            weighted_sell /= total_weight
            
            # Определяем финальный сигнал
            final_signal_type, confidence = self._determine_final_signal(
                weighted_buy, weighted_sell, strategy_signals
            )
            
            # Если сигнал нейтральный с низкой уверенностью - пропускаем
            if final_signal_type == FinalSignalType.NEUTRAL and confidence < 0.4:
                return None
            
            # Генерируем метаданные
            metadata = self._generate_metadata(group, strategy_signals)
            
            return {
                'symbol': group.symbol,
                'final_signal_type': final_signal_type,
                'confidence': confidence,
                'buy_weight': weighted_buy,
                'sell_weight': weighted_sell,
                'contributing_strategies': list(strategy_signals.keys()),
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Ошибка обработки группы сигналов: {e}")
            return None
    
    def _determine_final_signal(self, weighted_buy: float, weighted_sell: float,
                                strategy_signals: Dict) -> Tuple[FinalSignalType, float]:
        """Определение финального сигнала и уверенности с использованием Enum."""
        signal_diff = weighted_buy - weighted_sell
        base_confidence = abs(signal_diff)
        
        total_strategies = len(strategy_signals)
        if total_strategies > 1:
            buy_strategies = sum(
                1 for s in strategy_signals.values()
                if (hasattr(s['signal'], 'signal_type') and s['signal'].signal_type == SignalType.BUY) or
                   (hasattr(s['signal'], 'action') and s['signal'].action == 'BUY')
            )
            sell_strategies = sum(
                1 for s in strategy_signals.values()
                if (hasattr(s['signal'], 'signal_type') and s['signal'].signal_type == SignalType.SELL) or
                   (hasattr(s['signal'], 'action') and s['signal'].action == 'SELL')
            )
            consensus = max(buy_strategies, sell_strategies) / total_strategies
            base_confidence *= (0.5 + consensus * 0.5)
            
        max_priority = max(s['priority'] for s in strategy_signals.values())
        priority_factor = 0.5 + (max_priority / 10) * 0.5
        
        confidence = min(base_confidence * priority_factor, 1.0)
        
        # ИСПРАВЛЕНО: Возвращаем члены Enum, а не строки
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
            
            # Определяем тип сигнала
            if hasattr(signal, 'signal_type'):
                signal_type_value = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
            elif hasattr(signal, 'action'):
                signal_type_value = signal.action
            else:
                signal_type_value = 'NEUTRAL'
            
            contribution = {
                'strategy': strategy_name,
                'signal_type': signal_type_value,
                'confidence': signal.confidence,
                'weight': data['weight'],
                'reason': signal.reason if hasattr(signal, 'reason') else ''
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
        """Сохранение агрегированного сигнала"""
        try:
            # Находим сигнал с максимальной уверенностью для цены
            max_confidence_signal = max(
                group.signals, 
                key=lambda s: s.confidence
            )
            

            # Преобразуем метаданные в JSON-строку для сохранения в БД
            details_json = json.dumps(aggregated_data.get('metadata', {}))
            
            aggregated_signal = AggregatedSignal(
                symbol=aggregated_data['symbol'],
                final_signal=aggregated_data['final_signal_type'],
                confidence_score=aggregated_data['confidence'],
                buy_signals_count=group.buy_count,
                sell_signals_count=group.sell_count,
                neutral_signals_count=group.neutral_count,
                contributing_signals=aggregated_data['contributing_strategies'],
                details=details_json,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.db.add(aggregated_signal)
            
        except Exception as e:
            logger.error(f"Ошибка сохранения агрегированного сигнала: {e}")
    
    def _cleanup_cache(self):
        """Очистка кэша обработанных сигналов"""
        try:
            # Очищаем кэш раз в час
            if (datetime.utcnow() - self.last_cleanup).total_seconds() > 3600:
                # Оставляем только сигналы за последние 2 часа
                cutoff_time = datetime.utcnow() - timedelta(hours=2)
                
                # Получаем ID старых сигналов
                old_signal_ids = set(
                    self.db.query(SignalExtended.id).filter(
                        SignalExtended.timestamp < cutoff_time
                    ).all()
                )
                
                # Удаляем из кэша
                self.processed_signals -= old_signal_ids
                
                self.last_cleanup = datetime.utcnow()
                logger.info(f"🧹 Очищен кэш сигналов, удалено {len(old_signal_ids)} записей")
                
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")
    
    def aggregate_signals_sync(self, symbol: str, strategies_data: List[Dict]) -> Dict:
        """Синхронная агрегация сигналов для матрицы"""
        buy_weight = 0
        sell_weight = 0
        total_weight = 0
        for strategy in strategies_data:
            strategy_name = strategy['name']
            weight_info = self.STRATEGY_WEIGHTS.get(
                strategy_name,
                StrategyWeight(name=strategy_name, weight=1.0, reliability=0.5, min_confidence=0.3, priority=5)
            )
            if strategy['confidence'] < weight_info.min_confidence:
                continue
            weight = weight_info.weight * weight_info.reliability
            if strategy['status'] == 'BUY':
                buy_weight += weight * strategy['confidence']
            elif strategy['status'] == 'SELL':
                sell_weight += weight * strategy['confidence']
            total_weight += weight
        # Определяем итоговый сигнал
        if total_weight == 0:
            return {
                'action': 'NEUTRAL', 'confidence': 0.0, 'recommended_entry': None,
                'take_profit': None, 'stop_loss': None
            }
        # Нормализуем веса
        buy_score = buy_weight / total_weight
        sell_score = sell_weight / total_weight
        # Определяем действие
        if buy_score > sell_score and buy_score > 0.5:
            action = 'STRONG_BUY' if buy_score > 0.7 else 'BUY'
            confidence = buy_score
        elif sell_score > buy_score and sell_score > 0.5:
            action = 'STRONG_SELL' if sell_score > 0.7 else 'SELL'
            confidence = sell_score
        else:
            action = 'NEUTRAL'
            confidence = max(buy_score, sell_score)
        return {
            'action': action, 'confidence': confidence, 'recommended_entry': None,
            'take_profit': None, 'stop_loss': None
        }


# Пример использования
async def main():
    """Тестовый запуск агрегатора"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    aggregator = SignalAggregator(aggregation_window=60)
    
    try:
        await aggregator.start()
    except KeyboardInterrupt:
        logger.info("Остановка агрегатора...")
        await aggregator.stop()


if __name__ == "__main__":
    asyncio.run(main())
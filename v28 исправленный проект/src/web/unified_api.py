"""
API для веб-интерфейса системы торговых сигналов
Файл: src/web/unified_api.py
"""
from flask import Blueprint, jsonify, request
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import and_, desc, func

from ..core.database import SessionLocal
from ..core.signal_models import SignalExtended, AggregatedSignal, OrderBookSnapshot

logger = logging.getLogger(__name__)

# Создаем Blueprint
signals_api_bp = Blueprint('signals_api', __name__, url_prefix='/api')


@signals_api_bp.route("/")
def root():
    """Корневой эндпоинт"""
    return jsonify({
        "message": "Trading Signals API",
        "version": "1.0.0"
    })


@signals_api_bp.route("/signals/latest", methods=['GET'])
def get_latest_signals():
    """Получение последних агрегированных сигналов"""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        with SessionLocal() as db:
            # Получаем последние агрегированные сигналы
            signals = db.query(AggregatedSignal).order_by(
                desc(AggregatedSignal.confidence_score),
                desc(AggregatedSignal.updated_at)
            ).limit(limit).all()
            
            # Форматируем результаты
            results = []
            for signal in signals:
                results.append({
                    'symbol': signal.symbol,
                    'totalBuySignals': signal.buy_signals_count,
                    'totalSellSignals': signal.sell_signals_count,
                    'neutralSignals': signal.neutral_signals_count,
                    'finalSignal': signal.final_signal.value,
                    'confidenceScore': float(signal.confidence_score),
                    'metadata': signal.metadata,
                    'lastUpdated': signal.updated_at.isoformat()
                })
            
            return jsonify({
                'signals': results,
                'count': len(results)
            })
    
    except Exception as e:
        logger.error(f"Ошибка при получении последних сигналов: {e}")
        return jsonify({'error': str(e)}), 500


@signals_api_bp.route("/signals/details/<symbol>", methods=['GET'])
def get_signal_details(symbol: str):
    """Получение детальной информации по символу"""
    try:
        hours = request.args.get('hours', 24, type=int)
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with SessionLocal() as db:
            # Получаем сырые сигналы
            raw_signals = db.query(SignalExtended).filter(
                and_(
                    SignalExtended.symbol == symbol,
                    SignalExtended.created_at > cutoff_time
                )
            ).order_by(desc(SignalExtended.created_at)).all()
            
            # Получаем последний агрегированный сигнал
            aggregated = db.query(AggregatedSignal).filter(
                AggregatedSignal.symbol == symbol
            ).order_by(desc(AggregatedSignal.updated_at)).first()
            
            # Получаем историю снимков стакана
            price_history = db.query(
                OrderBookSnapshot.timestamp,
                OrderBookSnapshot.bid_volume,
                OrderBookSnapshot.ask_volume,
                OrderBookSnapshot.order_flow_imbalance
            ).filter(
                and_(
                    OrderBookSnapshot.symbol == symbol,
                    OrderBookSnapshot.timestamp > cutoff_time
                )
            ).order_by(desc(OrderBookSnapshot.timestamp)).limit(100).all()
            
            # Форматируем ответ
            result = {
                'symbol': symbol,
                'aggregated': None,
                'rawSignals': [],
                'priceHistory': []
            }
            
            if aggregated:
                result['aggregated'] = {
                    'totalBuySignals': aggregated.buy_signals_count,
                    'totalSellSignals': aggregated.sell_signals_count,
                    'neutralSignals': aggregated.neutral_signals_count,
                    'finalSignal': aggregated.final_signal.value,
                    'confidenceScore': float(aggregated.confidence_score),
                    'metadata': aggregated.metadata,
                    'lastUpdated': aggregated.updated_at.isoformat()
                }
            
            for signal in raw_signals:
                result['rawSignals'].append({
                    'signalType': signal.signal_type.value,
                    'strength': float(signal.strength),
                    'strategy': signal.strategy,
                    'metadata': signal.metadata,
                    'createdAt': signal.created_at.isoformat()
                })
            
            for record in price_history:
                result['priceHistory'].append({
                    'timestamp': record.timestamp.isoformat(),
                    'bidVolume': float(record.bid_volume),
                    'askVolume': float(record.ask_volume),
                    'orderFlowImbalance': float(record.order_flow_imbalance) if record.order_flow_imbalance else 0
                })
            
            return jsonify(result)
    
    except Exception as e:
        logger.error(f"Ошибка при получении деталей по {symbol}: {e}")
        return jsonify({'error': str(e)}), 500


@signals_api_bp.route("/analytics/performance", methods=['GET'])
def get_performance_analytics():
    """Получение аналитики по производительности стратегий"""
    try:
        days = request.args.get('days', 7, type=int)
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        with SessionLocal() as db:
            # Статистика по стратегиям
            strategy_stats = db.query(
                SignalExtended.strategy,
                SignalExtended.signal_type,
                func.count(SignalExtended.id).label('signal_count'),
                func.avg(SignalExtended.strength).label('avg_strength'),
                func.max(SignalExtended.strength).label('max_strength'),
                func.min(SignalExtended.strength).label('min_strength')
            ).filter(
                SignalExtended.created_at > cutoff_time
            ).group_by(
                SignalExtended.strategy,
                SignalExtended.signal_type
            ).all()
            
            # Общая статистика
            total_symbols = db.query(func.count(func.distinct(SignalExtended.symbol))).filter(
                SignalExtended.created_at > cutoff_time
            ).scalar()
            
            total_signals = db.query(func.count(SignalExtended.id)).filter(
                SignalExtended.created_at > cutoff_time
            ).scalar()
            
            # Форматируем результаты
            strategies = {}
            for stat in strategy_stats:
                if stat.strategy not in strategies:
                    strategies[stat.strategy] = {
                        'name': stat.strategy,
                        'signals': {},
                        'totalSignals': 0
                    }
                
                strategies[stat.strategy]['signals'][stat.signal_type.value] = {
                    'count': stat.signal_count,
                    'avgStrength': float(stat.avg_strength) if stat.avg_strength else 0,
                    'maxStrength': float(stat.max_strength) if stat.max_strength else 0,
                    'minStrength': float(stat.min_strength) if stat.min_strength else 0
                }
                strategies[stat.strategy]['totalSignals'] += stat.signal_count
            
            return jsonify({
                'period': f'{days} days',
                'overall': {
                    'totalSymbols': total_symbols,
                    'totalSignals': total_signals
                },
                'strategies': list(strategies.values())
            })
    
    except Exception as e:
        logger.error(f"Ошибка при получении аналитики производительности: {e}")
        return jsonify({'error': str(e)}), 500


@signals_api_bp.route("/strategies/activity", methods=['GET'])
def get_strategy_activity():
    """Получение активности стратегий"""
    try:
        hours = request.args.get('hours', 24, type=int)
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with SessionLocal() as db:
            # Получаем активность по стратегиям
            activity = db.query(
                SignalExtended.strategy,
                func.date_trunc('hour', SignalExtended.created_at).label('hour'),
                func.count(SignalExtended.id).label('signal_count')
            ).filter(
                SignalExtended.created_at > cutoff_time
            ).group_by(
                SignalExtended.strategy,
                func.date_trunc('hour', SignalExtended.created_at)
            ).order_by('hour').all()
            
            # Группируем по стратегиям
            strategies_data = {}
            for record in activity:
                strategy = record.strategy
                if strategy not in strategies_data:
                    strategies_data[strategy] = []
                
                strategies_data[strategy].append({
                    'timestamp': record.hour.isoformat(),
                    'count': record.signal_count
                })
            
            return jsonify({
                'period': f'{hours} hours',
                'strategies': strategies_data
            })
    
    except Exception as e:
        logger.error(f"Ошибка при получении активности стратегий: {e}")
        return jsonify({'error': str(e)}), 500


@signals_api_bp.route("/market/overview", methods=['GET'])
def get_market_overview():
    """Получение обзора рынка"""
    try:
        with SessionLocal() as db:
            # Топ символов по количеству сигналов за последние 24 часа
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            top_symbols = db.query(
                SignalExtended.symbol,
                func.count(SignalExtended.id).label('signal_count'),
                func.sum(func.case(
                    [(SignalExtended.signal_type == 'buy', 1)], else_=0
                )).label('buy_signals'),
                func.sum(func.case(
                    [(SignalExtended.signal_type == 'sell', 1)], else_=0
                )).label('sell_signals')
            ).filter(
                SignalExtended.created_at > cutoff_time
            ).group_by(
                SignalExtended.symbol
            ).order_by(
                desc('signal_count')
            ).limit(20).all()
            
            # Форматируем результаты
            symbols_data = []
            for symbol in top_symbols:
                symbols_data.append({
                    'symbol': symbol.symbol,
                    'totalSignals': symbol.signal_count,
                    'buySignals': symbol.buy_signals,
                    'sellSignals': symbol.sell_signals,
                    'sentiment': 'bullish' if symbol.buy_signals > symbol.sell_signals else 'bearish'
                })
            
            # Общая статистика рынка
            total_signals_24h = db.query(func.count(SignalExtended.id)).filter(
                SignalExtended.created_at > cutoff_time
            ).scalar()
            
            active_symbols = db.query(func.count(func.distinct(SignalExtended.symbol))).filter(
                SignalExtended.created_at > cutoff_time
            ).scalar()
            
            return jsonify({
                'overview': {
                    'totalSignals24h': total_signals_24h,
                    'activeSymbols': active_symbols,
                    'timestamp': datetime.utcnow().isoformat()
                },
                'topSymbols': symbols_data
            })
    
    except Exception as e:
        logger.error(f"Ошибка при получении обзора рынка: {e}")
        return jsonify({'error': str(e)}), 500


@signals_api_bp.route("/health", methods=['GET'])
def health_check():
    """Проверка здоровья API"""
    try:
        with SessionLocal() as db:
            # Проверяем подключение к БД
            db.execute("SELECT 1")
            
            # Получаем последние сигналы
            last_signal = db.query(SignalExtended).order_by(
                desc(SignalExtended.created_at)
            ).first()
            
            last_signal_time = last_signal.created_at.isoformat() if last_signal else None
            
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'lastSignal': last_signal_time,
                'timestamp': datetime.utcnow().isoformat()
            })
    
    except Exception as e:
        logger.error(f"Ошибка при проверке здоровья: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


# Обработчик ошибок для Blueprint
@signals_api_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@signals_api_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

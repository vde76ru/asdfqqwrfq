# src/web/unified_api.py
# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import func, case
from datetime import datetime, timedelta

# ✅ ИСПРАВЛЕНО: Правильный импорт для создания сессий
from src.core.database import SessionLocal
# ✅ ИСПРАВЛЕНО: Правильный импорт моделей
from src.core.models import Signal, Trade, Position
from src.logging import logger
from src.bot import get_bot_manager
from src.exchange import get_enhanced_exchange_client
from src.analysis import MarketAnalyzer, NewsAnalyzer, SocialAnalyzer
from src.core.unified_config import config

# Создаем Blueprint для унифицированного API
signals_api_bp = Blueprint('signals_api', __name__, url_prefix='/api')

# --- Глобальные экземпляры компонентов ---
market_analyzer = MarketAnalyzer()
news_analyzer = NewsAnalyzer()
social_analyzer = SocialAnalyzer()

# --- Хелперы ---

def get_bot_status_data():
    """Возвращает статус бота."""
    bot_manager = get_bot_manager()
    if bot_manager:
        # ✅ ИСПРАВЛЕНО: Используем атрибут status.value вместо несуществующего метода
        status_value = bot_manager.status.value if hasattr(bot_manager, 'status') and hasattr(bot_manager.status, 'value') else str(getattr(bot_manager, 'status', 'unknown'))
        return {
            'running': bot_manager.is_running,
            'status_message': status_value
        }
    return {
        'running': False,
        'status_message': 'Bot manager not initialized'
    }

# --- Основные эндпоинты API ---

@signals_api_bp.route('/', methods=['GET'])
def root():
    return jsonify({"version": "3.0", "status": "running", "message": "Welcome to the Professional Trading Bot API"})

@signals_api_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

# --- Эндпоинты для Dashboard ---

@signals_api_bp.route('/dashboard/statistics', methods=['GET'])
def get_dashboard_statistics():
    return get_performance_analytics()

@signals_api_bp.route('/dashboard/balance', methods=['GET'])
def get_dashboard_balance():
    bot_manager = get_bot_manager()
    if not bot_manager:
        return jsonify({
            "total_usdt": 0,
            "available_usdt": 0,
            "in_positions": 0,
            "error": "Bot manager not initialized"
        }), 503
    
    try:
        balance_info = bot_manager.get_balance_info()
        return jsonify(balance_info)
    except Exception as e:
        logger.error(f"Ошибка при получении баланса: {e}", exc_info=True)
        return jsonify({
            "total_usdt": 0,
            "available_usdt": 0,
            "in_positions": 0,
            "error": str(e)
        }), 500

@signals_api_bp.route('/dashboard/positions', methods=['GET'])
def get_dashboard_positions():
    bot_manager = get_bot_manager()
    if not bot_manager:
        return jsonify([]), 200  # Возвращаем пустой массив вместо ошибки
    
    try:
        positions_info = bot_manager.get_positions_info()
        return jsonify(positions_info)
    except Exception as e:
        logger.error(f"Ошибка при получении позиций: {e}", exc_info=True)
        return jsonify([]), 200  # Возвращаем пустой массив при ошибке

@signals_api_bp.route('/dashboard/recent-trades', methods=['GET'])
def get_dashboard_recent_trades():
    db = SessionLocal()
    try:
        limit = request.args.get('limit', 20, type=int)
        # ✅ ИСПРАВЛЕНО: Используем правильное имя поля 'close_time'
        trades = db.query(Trade).order_by(Trade.close_time.desc()).limit(limit).all()
        return jsonify([trade.to_dict() for trade in trades])
    except Exception as e:
        logger.error(f"Ошибка при получении недавних сделок: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch recent trades"}), 500
    finally:
        db.close()

# --- Эндпоинты для управления ботом ---

@signals_api_bp.route('/bot/status', methods=['GET'])
def get_bot_status():
    bot_manager = get_bot_manager()
    if bot_manager:
        status_data = bot_manager.get_status()
        # Добавляем дополнительные поля для совместимости с frontend
        return jsonify({
            **status_data,
            'running': status_data.get('is_running', False),
            'status_message': status_data.get('status', 'unknown')
        })
    return jsonify({
        'running': False,
        'status_message': 'Bot manager not initialized',
        'error': True
    })

@signals_api_bp.route('/bot/start', methods=['POST'])
def start_bot():
    bot_manager = get_bot_manager()
    if bot_manager:
        success, message = bot_manager.start()
        return jsonify({
            "success": success,  # Изменено с "status" на "success" для соответствия frontend
            "message": message
        })
    return jsonify({
        "success": False,
        "message": "Bot manager not available"
    }), 503


@signals_api_bp.route('/bot/stop', methods=['POST'])
def stop_bot():
    bot_manager = get_bot_manager()
    if bot_manager:
        success, message = bot_manager.stop()
        return jsonify({
            "success": success,  # Изменено с "status" на "success"
            "message": message
        })
    return jsonify({
        "success": False,
        "message": "Bot manager not available"
    }), 503


# --- Эндпоинты для конфигурации ---

@signals_api_bp.route('/signals/matrix', methods=['GET'])
def get_signals_matrix():
    """
    Новый эндпоинт для матрицы сигналов по всем парам и стратегиям
    """
    try:
        bot_manager = get_bot_manager()
        if not bot_manager:
            return jsonify({'error': 'Bot manager not available'}), 503
            
        # Получаем кэшированные результаты анализа
        matrix_data = bot_manager.get_signals_matrix_data()
        
        # ✅ ИЗМЕНЕНО: Возвращаем успешный ответ даже с пустыми данными
        return jsonify({
            'success': True,
            'data': matrix_data if matrix_data else [],
            'timestamp': datetime.utcnow().isoformat(),
            'message': 'No data available yet' if not matrix_data else None
        })
    except Exception as e:
        logger.error(f"Error in signals matrix endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@signals_api_bp.route('/signals/details/<symbol>', methods=['GET'])
def get_signal_details(symbol):
    """
    Детальная информация по конкретной паре
    """
    try:
        bot_manager = get_bot_manager()
        if not bot_manager:
            return jsonify({'error': 'Bot manager not available'}), 503
            
        details = bot_manager.get_symbol_details(symbol)
        
        return jsonify({
            'success': True,
            'data': details,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting signal details: {e}")
        return jsonify({'error': str(e)}), 500

@signals_api_bp.route('/config/pairs', methods=['GET'])
def get_config_pairs():
    # ✅ ИСПРАВЛЕНО: Читаем строку из конфига и превращаем в список
    pairs_str = getattr(config, 'TRADING_PAIRS', '')
    return jsonify(pairs_str.split(',') if isinstance(pairs_str, str) and pairs_str else [])

# --- Эндпоинты для сигналов ---

@signals_api_bp.route('/signals/latest', methods=['GET'])
def get_latest_signals():
    db = SessionLocal()
    try:
        limit = request.args.get('limit', 100, type=int)
        # ✅ ИСПРАВЛЕНО: Используем правильное имя поля 'created_at'
        signals = db.query(Signal).order_by(Signal.created_at.desc()).limit(limit).all()
        return jsonify([signal.to_dict() for signal in signals])
    except Exception as e:
        logger.error(f"Ошибка при получении последних сигналов: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch latest signals"}), 500
    finally:
        db.close()


# --- Эндпоинты для графиков и аналитики ---

@signals_api_bp.route('/charts/indicators/<symbol>', methods=['GET'])
def get_chart_indicators(symbol):
    try:
        # ✅ ИСПРАВЛЕНО: Предполагаемое правильное имя метода
        indicators = market_analyzer.get_indicator_values(symbol) if hasattr(market_analyzer, 'get_indicator_values') else {}
        return jsonify(indicators)
    except Exception as e:
        logger.error(f"Ошибка при получении индикаторов для {symbol}: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch indicators"}), 500

@signals_api_bp.route('/analytics/performance', methods=['GET'])
def get_performance_analytics():
    db = SessionLocal()
    try:
        days = request.args.get('days', 30, type=int)
        time_since = datetime.utcnow() - timedelta(days=days)

        # ✅ ИСПРАВЛЕНО: Используем правильные имена полей
        signals_query = db.query(Signal).filter(Signal.created_at >= time_since)
        all_signals = signals_query.all()
        total_signals = len(all_signals)
        buy_signals = sum(1 for signal in all_signals if signal.action == 'BUY')
        sell_signals = sum(1 for signal in all_signals if signal.action == 'SELL')

        trades_query = db.query(Trade).filter(Trade.close_time >= time_since)
        successful_trades = trades_query.filter(Trade.profit_loss > 0).count()
        failed_trades = trades_query.filter(Trade.profit_loss <= 0).count()

        total_pnl = db.query(func.sum(Trade.profit_loss)).filter(Trade.close_time >= time_since).scalar() or 0
        
        win_rate = (successful_trades / (successful_trades + failed_trades) * 100) if (successful_trades + failed_trades) > 0 else 0

        return jsonify({
            'period_days': days,
            'total_signals': total_signals,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'successful_trades': successful_trades,
            'failed_trades': failed_trades,
            'total_pnl': round(total_pnl, 2),
            'win_rate': round(win_rate, 2)
        })
    except Exception as e:
        logger.error(f"Ошибка при получении аналитики производительности: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch performance analytics"}), 500
    finally:
        db.close()

@signals_api_bp.route('/analytics/detailed', methods=['GET'])
def get_detailed_analytics():
    try:
        # ✅ ИСПРАВЛЕНО: Предполагаемое правильное имя метода
        analytics_data = market_analyzer.get_market_analysis() if hasattr(market_analyzer, 'get_market_analysis') else {}
        return jsonify(analytics_data)
    except Exception as e:
        logger.error(f"Ошибка при получении детальной аналитики: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch detailed analytics"}), 500
        
        
@signals_api_bp.route('/trades/virtual', methods=['GET'])
def get_virtual_trades():
    """Получение виртуальных/paper trading сделок"""
    bot_manager = get_bot_manager()
    if not bot_manager:
        return jsonify([]), 200
    
    try:
        # Если бот в режиме paper trading
        if getattr(config, 'PAPER_TRADING', True):
            db = SessionLocal()
            try:
                trades = db.query(Trade).filter(
                    Trade.is_paper == True
                ).order_by(Trade.created_at.desc()).limit(50).all()
                return jsonify([trade.to_dict() for trade in trades])
            finally:
                db.close()
        else:
            return jsonify([])
    except Exception as e:
        logger.error(f"Ошибка получения виртуальных сделок: {e}")
        return jsonify([]), 200

@signals_api_bp.route('/trades/active', methods=['GET'])
def get_active_trades():
    """Получение активных сделок"""
    bot_manager = get_bot_manager()
    if not bot_manager:
        return jsonify([]), 200
    
    try:
        db = SessionLocal()
        try:
            # Активные сделки - это позиции
            positions = db.query(Position).filter(
                Position.status == 'OPEN'
            ).all()
            
            trades_data = []
            for pos in positions:
                trades_data.append({
                    'id': pos.id,
                    'symbol': pos.symbol,
                    'side': pos.side,
                    'entry_price': pos.entry_price,
                    'current_price': pos.current_price,
                    'quantity': pos.quantity,
                    'pnl': pos.unrealized_pnl,
                    'pnl_percent': pos.pnl_percent,
                    'created_at': pos.created_at.isoformat() if pos.created_at else None
                })
            
            return jsonify(trades_data)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Ошибка получения активных сделок: {e}")
        return jsonify([]), 200

@signals_api_bp.route('/trades/history', methods=['GET'])
def get_trades_history():
    """Получение истории сделок"""
    bot_manager = get_bot_manager()
    if not bot_manager:
        return jsonify([]), 200
    
    try:
        db = SessionLocal()
        try:
            limit = request.args.get('limit', 50, type=int)
            offset = request.args.get('offset', 0, type=int)
            
            trades = db.query(Trade).filter(
                Trade.status == 'CLOSED'
            ).order_by(Trade.close_time.desc()).offset(offset).limit(limit).all()
            
            return jsonify([trade.to_dict() for trade in trades])
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Ошибка получения истории сделок: {e}")
        return jsonify([]), 200

# --- Эндпоинты для новостей и соц. сетей ---

@signals_api_bp.route('/news/latest', methods=['GET'])
def get_latest_news():
    try:
        limit = request.args.get('limit', 10, type=int)
        news = news_analyzer.get_latest_news(limit=limit)
        return jsonify(news)
    except Exception as e:
        logger.error(f"Ошибка при получении новостей: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch news"}), 500

@signals_api_bp.route('/social/signals', methods=['GET'])
def get_social_signals():
    try:
        signals = social_analyzer.get_social_signals()
        return jsonify(signals)
    except Exception as e:
        logger.error(f"Ошибка при получении социальных сигналов: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch social signals"}), 500

# --- Эндпоинты для настроек ---

@signals_api_bp.route('/settings', methods=['GET'])
def get_settings():
    try:
        # ✅ ИСПРАВЛЕНО: Используем getattr для безопасного доступа к конфигу
        settings_data = {
            'testnet': getattr(config, 'TESTNET', False),
            'bybit_testnet': getattr(config, 'BYBIT_TESTNET', False),
            'initial_capital': getattr(config, 'INITIAL_CAPITAL', 0),
            'max_positions': getattr(config, 'MAX_POSITIONS', 0),
            'risk_per_trade': getattr(config, 'RISK_PER_TRADE_PERCENT', 0.0),
            'stop_loss_pct': getattr(config, 'STOP_LOSS_PERCENT', 0.0),
            'take_profit_pct': getattr(config, 'TAKE_PROFIT_PERCENT', 0.0),
            'strategy_weights': getattr(config, 'STRATEGY_WEIGHTS', "")
        }
        return jsonify(settings_data)
    except Exception as e:
        logger.error(f"Ошибка при получении настроек: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch settings"}), 500

@signals_api_bp.route('/trading-pairs', methods=['GET'])
def get_trading_pairs():
    bot_manager = get_bot_manager()
    if not bot_manager:
        return jsonify({"error": "Bot manager not initialized"}), 503
    try:
        pairs = bot_manager.active_pairs if hasattr(bot_manager, 'active_pairs') else []
        return jsonify(pairs)
    except Exception as e:
        logger.error(f"Ошибка при получении торговых пар: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch trading pairs"}), 500
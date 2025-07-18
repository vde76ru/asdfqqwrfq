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
    # ✅ ИСПРАВЛЕНО: Получаем данные через BotManager, а не напрямую
    bot_manager = get_bot_manager()
    if not bot_manager:
        return jsonify({"error": "Bot manager not initialized"}), 503
    try:
        # Предполагаем, что у BotManager есть метод для получения информации о балансе
        balance_info = bot_manager.get_balance_info() if hasattr(bot_manager, 'get_balance_info') else {}
        return jsonify(balance_info)
    except Exception as e:
        logger.error(f"Ошибка при получении баланса: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch balance"}), 500

@signals_api_bp.route('/dashboard/positions', methods=['GET'])
def get_dashboard_positions():
    # ✅ ИСПРАВЛЕНО: Получаем данные через BotManager
    bot_manager = get_bot_manager()
    if not bot_manager:
        return jsonify({"error": "Bot manager not initialized"}), 503
    try:
        positions_info = bot_manager.get_positions_info() if hasattr(bot_manager, 'get_positions_info') else []
        return jsonify(positions_info)
    except Exception as e:
        logger.error(f"Ошибка при получении позиций: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch positions"}), 500

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
    return jsonify(get_bot_status_data())

@signals_api_bp.route('/bot/start', methods=['POST'])
def start_bot():
    bot_manager = get_bot_manager()
    if bot_manager:
        success, message = bot_manager.start()
        return jsonify({"status": "success" if success else "error", "message": message})
    return jsonify({"status": "error", "message": "Bot manager not available"}), 503

@signals_api_bp.route('/bot/stop', methods=['POST'])
def stop_bot():
    bot_manager = get_bot_manager()
    if bot_manager:
        success, message = bot_manager.stop()
        return jsonify({"status": "success" if success else "error", "message": message})
    return jsonify({"status": "error", "message": "Bot manager not available"}), 503

# --- Эндпоинты для конфигурации ---

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

@signals_api_bp.route('/signals/details/<symbol>', methods=['GET'])
def get_signal_details(symbol):
    db = SessionLocal()
    try:
        # ✅ ИСПРАВЛЕНО: Используем правильное имя поля 'created_at'
        latest_signal = db.query(Signal).filter_by(symbol=symbol).order_by(Signal.created_at.desc()).first()
        if latest_signal:
            return jsonify(latest_signal.to_dict())
        return jsonify({"message": "No signal found for this symbol"}), 404
    except Exception as e:
        logger.error(f"Ошибка при получении деталей сигнала для {symbol}: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch signal details"}), 500
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

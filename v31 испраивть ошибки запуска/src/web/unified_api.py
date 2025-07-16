# src/web/unified_api.py
# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import func, case
from datetime import datetime, timedelta
from src.core.database import db
from src.core.models import Signal, Trade, Position
from src.logging import logger
from src.bot import get_bot_manager
from src.exchange import get_enhanced_exchange_client
from src.analysis import MarketAnalyzer, NewsAnalyzer, SocialAnalyzer
from src.core.unified_config import config

# Создаем Blueprint для унифицированного API
unified_api_blueprint = Blueprint('signals_api', __name__, url_prefix='/api')

# --- Глобальные экземпляры компонентов ---
market_analyzer = MarketAnalyzer()
news_analyzer = NewsAnalyzer()
social_analyzer = SocialAnalyzer()

# --- Хелперы ---

def get_bot_status_data():
    """Возвращает статус бота."""
    bot_manager = get_bot_manager()
    if bot_manager:
        return {
            'running': bot_manager.is_running(),
            'status_message': bot_manager.get_status_message()
        }
    return {
        'running': False,
        'status_message': 'Bot manager not initialized'
    }

# --- Основные эндпоинты API ---

@unified_api_blueprint.route('/', methods=['GET'])
def root():
    """Корневой эндпоинт API."""
    return jsonify({
        "version": "3.0",
        "status": "running",
        "message": "Welcome to the Professional Trading Bot API"
    })

@unified_api_blueprint.route('/health', methods=['GET'])
def health_check():
    """Проверка состояния API."""
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

# --- Эндпоинты для Dashboard ---

@unified_api_blueprint.route('/dashboard/statistics', methods=['GET'])
def get_dashboard_statistics():
    # Эта функция может быть объединена с get_performance_analytics
    return get_performance_analytics()

@unified_api_blueprint.route('/dashboard/balance', methods=['GET'])
def get_dashboard_balance():
    exchange_client = get_enhanced_exchange_client()
    if not exchange_client:
        return jsonify({"error": "Exchange client not initialized"}), 503
    try:
        balance = exchange_client.get_balance_info()
        return jsonify(balance)
    except Exception as e:
        logger.error(f"Ошибка при получении баланса: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch balance"}), 500

@unified_api_blueprint.route('/dashboard/positions', methods=['GET'])
def get_dashboard_positions():
    exchange_client = get_enhanced_exchange_client()
    if not exchange_client:
        return jsonify({"error": "Exchange client not initialized"}), 503
    try:
        positions = exchange_client.get_open_positions()
        return jsonify([position.to_dict() for position in positions])
    except Exception as e:
        logger.error(f"Ошибка при получении позиций: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch positions"}), 500

@unified_api_blueprint.route('/dashboard/recent-trades', methods=['GET'])
def get_dashboard_recent_trades():
    try:
        limit = request.args.get('limit', 20, type=int)
        trades = db.session.query(Trade).order_by(Trade.close_timestamp.desc()).limit(limit).all()
        return jsonify([trade.to_dict() for trade in trades])
    except Exception as e:
        logger.error(f"Ошибка при получении недавних сделок: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch recent trades"}), 500

# --- Эндпоинты для управления ботом ---

@unified_api_blueprint.route('/bot/status', methods=['GET'])
def get_bot_status():
    return jsonify(get_bot_status_data())

@unified_api_blueprint.route('/bot/start', methods=['POST'])
def start_bot():
    bot_manager = get_bot_manager()
    if bot_manager:
        bot_manager.start()
        return jsonify({"status": "success", "message": "Bot started"})
    return jsonify({"status": "error", "message": "Bot manager not available"}), 503

@unified_api_blueprint.route('/bot/stop', methods=['POST'])
def stop_bot():
    bot_manager = get_bot_manager()
    if bot_manager:
        bot_manager.stop()
        return jsonify({"status": "success", "message": "Bot stopped"})
    return jsonify({"status": "error", "message": "Bot manager not available"}), 503

# --- Эндпоинты для конфигурации ---

@unified_api_blueprint.route('/config/pairs', methods=['GET'])
def get_config_pairs():
    return jsonify(config.get_trading_pairs())

# --- Эндпоинты для сигналов ---

@unified_api_blueprint.route('/signals/latest', methods=['GET'])
def get_latest_signals():
    """Получение последних торговых сигналов."""
    try:
        limit = request.args.get('limit', 100, type=int)
        signals = db.session.query(Signal).order_by(Signal.timestamp.desc()).limit(limit).all()
        return jsonify([signal.to_dict() for signal in signals])
    except Exception as e:
        logger.error(f"Ошибка при получении последних сигналов: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch latest signals"}), 500

@unified_api_blueprint.route('/signals/details/<symbol>', methods=['GET'])
def get_signal_details(symbol):
    """Получение детальной информации по сигналу для конкретного символа."""
    try:
        latest_signal = db.session.query(Signal).filter_by(symbol=symbol).order_by(Signal.timestamp.desc()).first()
        if latest_signal:
            return jsonify(latest_signal.to_dict())
        return jsonify({"message": "No signal found for this symbol"}), 404
    except Exception as e:
        logger.error(f"Ошибка при получении деталей сигнала для {symbol}: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch signal details"}), 500

# --- Эндпоинты для графиков и аналитики ---

@unified_api_blueprint.route('/charts/indicators/<symbol>', methods=['GET'])
def get_chart_indicators(symbol):
    try:
        indicators = market_analyzer.get_all_indicator_values(symbol)
        return jsonify(indicators)
    except Exception as e:
        logger.error(f"Ошибка при получении индикаторов для {symbol}: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch indicators"}), 500

@unified_api_blueprint.route('/analytics/performance', methods=['GET'])
def get_performance_analytics():
    """Получение аналитики производительности на основе сигналов и сделок."""
    try:
        days = request.args.get('days', 30, type=int)
        time_since = datetime.utcnow() - timedelta(days=days)

        # Подсчет сигналов
        signals_query = db.session.query(Signal).filter(Signal.timestamp >= time_since)
        
        # ======================= ИСПРАВЛЕНИЕ ЗДЕСЬ =======================
        # Ошибка была в том, что вы пытались получить `signal_type` у класса `Signal`, а не у его экземпляра.
        # Теперь мы итерируемся по результатам запроса и обращаемся к атрибуту каждого отдельного сигнала.
        all_signals = signals_query.all()
        total_signals = len(all_signals)
        buy_signals = sum(1 for signal in all_signals if signal.signal_type == 'buy')
        sell_signals = sum(1 for signal in all_signals if signal.signal_type == 'sell')
        # ===================== КОНЕЦ ИСПРАВЛЕНИЯ =======================

        # Подсчет успешных и неудачных сделок
        trades_query = db.session.query(Trade).filter(Trade.close_timestamp >= time_since)
        successful_trades = trades_query.filter(Trade.pnl > 0).count()
        failed_trades = trades_query.filter(Trade.pnl <= 0).count()

        # Общий PnL
        total_pnl = db.session.query(func.sum(Trade.pnl)).filter(Trade.close_timestamp >= time_since).scalar() or 0
        
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

@unified_api_blueprint.route('/analytics/detailed', methods=['GET'])
def get_detailed_analytics():
    try:
        analytics_data = market_analyzer.get_detailed_market_analysis()
        return jsonify(analytics_data)
    except Exception as e:
        logger.error(f"Ошибка при получении детальной аналитики: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch detailed analytics"}), 500

# --- Эндпоинты для новостей и соц. сетей ---

@unified_api_blueprint.route('/news/latest', methods=['GET'])
def get_latest_news():
    try:
        limit = request.args.get('limit', 10, type=int)
        news = news_analyzer.get_latest_news(limit=limit)
        return jsonify(news)
    except Exception as e:
        logger.error(f"Ошибка при получении новостей: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch news"}), 500

@unified_api_blueprint.route('/social/signals', methods=['GET'])
def get_social_signals():
    try:
        signals = social_analyzer.get_social_signals()
        return jsonify(signals)
    except Exception as e:
        logger.error(f"Ошибка при получении социальных сигналов: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch social signals"}), 500

# --- Эндпоинты для настроек ---

@unified_api_blueprint.route('/settings', methods=['GET'])
def get_settings():
    try:
        # Возвращаем только нечувствительные данные
        settings_data = {
            'testnet': config.TESTNET,
            'bybit_testnet': config.BYBIT_TESTNET,
            'initial_capital': config.INITIAL_CAPITAL,
            'max_positions': config.MAX_POSITIONS,
            'risk_per_trade': config.RISK_PER_TRADE,
            'stop_loss_pct': config.STOP_LOSS_PCT,
            'take_profit_pct': config.TAKE_PROFIT_PCT,
            'strategy_weights': config.STRATEGY_WEIGHTS
        }
        return jsonify(settings_data)
    except Exception as e:
        logger.error(f"Ошибка при получении настроек: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch settings"}), 500

@unified_api_blueprint.route('/trading-pairs', methods=['GET'])
def get_trading_pairs():
    """Получение списка доступных торговых пар."""
    exchange_client = get_enhanced_exchange_client()
    if not exchange_client:
        return jsonify({"error": "Exchange client not initialized"}), 503
    try:
        pairs = exchange_client.get_trading_pairs()
        return jsonify(pairs)
    except Exception as e:
        logger.error(f"Ошибка при получении торговых пар: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch trading pairs"}), 500
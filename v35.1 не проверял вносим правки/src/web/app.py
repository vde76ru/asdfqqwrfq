# Файл: src/web/app.py
import os
import logging
import asyncio
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json

# Настройка логирования
logger = logging.getLogger(__name__)

# --- Импорты из нашего проекта ---
try:
    from ..core.database import SessionLocal
    from ..core.models import User, TradingSignal, Trade, Position, AggregatedSignal
    from ..core.unified_config import unified_config as config
    
    # Импортируем менеджер бота
    from ..bot.manager import BotManager
    
    # Импортируем систему уведомлений
    from ..notifications.telegram import NotificationManager
    
    BOT_AVAILABLE = True
    logger.info("✅ Все модули успешно импортированы")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта модулей: {e}")
    BOT_AVAILABLE = False

# Глобальные переменные
app = None
socketio = None
login_manager = None
bot_manager = None
notification_manager = None

def create_app():
    """Создание и настройка Flask приложения"""
    global app, socketio, login_manager, bot_manager, notification_manager
    
    app = Flask(__name__, 
                template_folder='templates', 
                static_folder='static')
    
    # Конфигурация
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    app.config['JSON_AS_ASCII'] = False
    
    # CORS
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # SocketIO
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        ping_timeout=60,
        ping_interval=25,
        logger=False,
        engineio_logger=False
    )
    
    # Login Manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        try:
            db = SessionLocal()
            user = db.query(User).filter(User.id == int(user_id)).first()
            db.close()
            return user
        except:
            return None
    
    # Инициализация компонентов
    if BOT_AVAILABLE:
        try:
            # Создаем экземпляр BotManager
            bot_manager = BotManager()
            logger.info("✅ BotManager создан")
            
            # Создаем NotificationManager
            notification_manager = NotificationManager()
            logger.info("✅ NotificationManager создан")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания менеджеров: {e}")
            bot_manager = None
            notification_manager = None
    
    # Регистрация компонентов
    with app.app_context():
        register_page_routes(app)
        register_api_routes(app)
        register_websocket_handlers(socketio)
        register_error_handlers(app)
    
    logger.info("🚀 Flask приложение готово к запуску")
    return app, socketio

def register_page_routes(app):
    """Регистрация маршрутов страниц"""
    
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
            
        if request.method == 'POST':
            username = request.form.get('username') or request.json.get('username')
            password = request.form.get('password') or request.json.get('password')
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == username).first()
                if user and user.check_password(password):
                    login_user(user, remember=True)
                    return jsonify({'success': True, 'redirect': url_for('dashboard')})
                else:
                    return jsonify({'success': False, 'message': 'Неверные учетные данные'}), 401
            finally:
                db.close()
                
        return render_template('login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html')
    
    @app.route('/charts')
    @login_required
    def charts():
        return render_template('charts.html')
    
    @app.route('/analytics')
    @login_required
    def analytics():
        return render_template('analytics.html')
    
    @app.route('/signals')
    @login_required
    def signals():
        return render_template('signals.html')
    
    @app.route('/settings')
    @login_required
    def settings():
        return render_template('settings.html')

def register_api_routes(app):
    """Регистрация API маршрутов"""
    
    # === BOT CONTROL API ===
    
    @app.route('/api/bot/status', methods=['GET'])
    def get_bot_status():
        """Получение статуса бота"""
        global bot_manager
        
        try:
            if not bot_manager:
                return jsonify({
                    'success': True,
                    'is_running': False,
                    'status': 'Bot manager not initialized'
                })
            
            return jsonify({
                'success': True,
                'is_running': bot_manager.is_running,
                'status': 'running' if bot_manager.is_running else 'stopped',
                'active_pairs': getattr(bot_manager, 'active_pairs', []),
                'open_positions_count': len(getattr(bot_manager, 'positions', {})),
                'cycles_count': getattr(bot_manager, 'analysis_cycles', 0)
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения статуса бота: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bot/start', methods=['POST'])
    async def start_bot():
        """Запуск бота"""
        global bot_manager
        
        try:
            if not bot_manager:
                return jsonify({
                    'success': False,
                    'message': 'Bot manager not initialized'
                }), 503
            
            if bot_manager.is_running:
                return jsonify({
                    'success': False,
                    'message': 'Bot is already running'
                })
            
            # Запускаем бота в отдельной задаче
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Запускаем бота
            await bot_manager.start()
            
            return jsonify({
                'success': True,
                'message': 'Bot started successfully'
            })
            
        except Exception as e:
            logger.error(f"Ошибка запуска бота: {e}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
    
    @app.route('/api/bot/stop', methods=['POST'])
    async def stop_bot():
        """Остановка бота"""
        global bot_manager
        
        try:
            if not bot_manager:
                return jsonify({
                    'success': False,
                    'message': 'Bot manager not initialized'
                }), 503
            
            if not bot_manager.is_running:
                return jsonify({
                    'success': False,
                    'message': 'Bot is not running'
                })
            
            await bot_manager.stop()
            
            return jsonify({
                'success': True,
                'message': 'Bot stopped successfully'
            })
            
        except Exception as e:
            logger.error(f"Ошибка остановки бота: {e}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
    
    # === DASHBOARD API ===
    
    @app.route('/api/dashboard/balance', methods=['GET'])
    def get_balance():
        """Получение баланса"""
        try:
            # Получаем баланс из exchange client
            if bot_manager and hasattr(bot_manager, 'exchange_client'):
                balance = bot_manager.exchange_client.get_balance()
                
                return jsonify({
                    'success': True,
                    'total_usdt': balance.get('USDT', {}).get('total', 0),
                    'free_usdt': balance.get('USDT', {}).get('free', 0),
                    'locked_usdt': balance.get('USDT', {}).get('used', 0)
                })
            else:
                # Демо данные
                return jsonify({
                    'success': True,
                    'total_usdt': 10000.0,
                    'free_usdt': 8500.0,
                    'locked_usdt': 1500.0
                })
                
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/dashboard/positions', methods=['GET'])
    def get_positions():
        """Получение открытых позиций"""
        try:
            db = SessionLocal()
            positions = db.query(Position).filter(
                Position.status == 'open'
            ).all()
            
            positions_data = []
            for pos in positions:
                positions_data.append({
                    'id': pos.id,
                    'symbol': pos.symbol,
                    'side': pos.side,
                    'quantity': float(pos.quantity),
                    'entry_price': float(pos.entry_price),
                    'current_price': float(pos.current_price or pos.entry_price),
                    'unrealized_pnl': float(pos.unrealized_pnl or 0),
                    'pnl_percent': float(pos.pnl_percent or 0),
                    'strategy': pos.strategy,
                    'created_at': pos.created_at.isoformat()
                })
            
            return jsonify({
                'success': True,
                'positions': positions_data
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения позиций: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/dashboard/statistics', methods=['GET'])
    def get_statistics():
        """Получение статистики"""
        try:
            db = SessionLocal()
            
            # Статистика за сегодня
            today = datetime.utcnow().date()
            today_trades = db.query(Trade).filter(
                Trade.created_at >= today
            ).all()
            
            today_profit = sum(float(t.profit_loss or 0) for t in today_trades)
            today_wins = len([t for t in today_trades if t.profit_loss > 0])
            today_losses = len([t for t in today_trades if t.profit_loss <= 0])
            today_win_rate = (today_wins / len(today_trades) * 100) if today_trades else 0
            
            # Общая статистика
            all_trades = db.query(Trade).all()
            total_profit = sum(float(t.profit_loss or 0) for t in all_trades)
            
            return jsonify({
                'success': True,
                'today_profit': today_profit,
                'today_trades': len(today_trades),
                'today_win_rate': today_win_rate,
                'total_profit': total_profit
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/dashboard/recent-trades', methods=['GET'])
    def get_recent_trades():
        """Получение последних сделок"""
        try:
            db = SessionLocal()
            limit = request.args.get('limit', 10, type=int)
            
            trades = db.query(Trade).order_by(
                Trade.created_at.desc()
            ).limit(limit).all()
            
            trades_data = []
            for trade in trades:
                trades_data.append({
                    'id': trade.id,
                    'symbol': trade.symbol,
                    'side': trade.side,
                    'price': float(trade.price),
                    'quantity': float(trade.quantity),
                    'profit_loss': float(trade.profit_loss or 0),
                    'status': trade.status,
                    'strategy': trade.strategy,
                    'created_at': trade.created_at.isoformat()
                })
            
            return jsonify({
                'success': True,
                'trades': trades_data
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения сделок: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    # === SIGNALS API ===
    
    @app.route('/api/signals/latest', methods=['GET'])
    def get_latest_signals():
        """Получение последних сигналов"""
        try:
            db = SessionLocal()
            
            # Получаем агрегированные сигналы
            aggregated = db.query(AggregatedSignal).order_by(
                AggregatedSignal.created_at.desc()
            ).limit(50).all()
            
            # Группируем по символам
            symbols_data = {}
            
            for signal in aggregated:
                symbol = signal.symbol
                if symbol not in symbols_data:
                    symbols_data[symbol] = {
                        'symbol': symbol,
                        'buySignals': 0,
                        'sellSignals': 0,
                        'neutralSignals': 0,
                        'sentiment': 'neutral',
                        'strategies': []
                    }
                
                # Подсчитываем сигналы
                if signal.final_signal == 'BUY':
                    symbols_data[symbol]['buySignals'] += 1
                    symbols_data[symbol]['sentiment'] = 'bullish'
                elif signal.final_signal == 'SELL':
                    symbols_data[symbol]['sellSignals'] += 1
                    symbols_data[symbol]['sentiment'] = 'bearish'
                else:
                    symbols_data[symbol]['neutralSignals'] += 1
                
                # Добавляем стратегии
                strategies = signal.contributing_signals.split(',') if signal.contributing_signals else []
                for strategy in strategies:
                    if strategy and strategy not in symbols_data[symbol]['strategies']:
                        symbols_data[symbol]['strategies'].append(strategy)
            
            return jsonify({
                'success': True,
                'symbols': list(symbols_data.values()),
                'totalSignals24h': len(aggregated)
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения сигналов: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    @app.route('/api/signals/details/<symbol>', methods=['GET'])
    def get_signal_details(symbol):
        """Получение деталей сигнала для символа"""
        try:
            db = SessionLocal()
            
            # Последний агрегированный сигнал
            aggregated = db.query(AggregatedSignal).filter(
                AggregatedSignal.symbol == symbol
            ).order_by(AggregatedSignal.created_at.desc()).first()
            
            # Последние сырые сигналы
            raw_signals = db.query(TradingSignal).filter(
                TradingSignal.symbol == symbol
            ).order_by(TradingSignal.created_at.desc()).limit(20).all()
            
            response_data = {
                'success': True,
                'symbol': symbol
            }
            
            if aggregated:
                response_data['aggregated'] = {
                    'finalSignal': aggregated.final_signal,
                    'confidenceScore': float(aggregated.confidence_score),
                    'totalBuySignals': aggregated.buy_signals_count,
                    'totalSellSignals': aggregated.sell_signals_count,
                    'neutralSignals': aggregated.neutral_signals_count
                }
            
            response_data['rawSignals'] = [
                {
                    'signalType': signal.action.lower(),
                    'strength': float(signal.strength),
                    'strategy': signal.strategy,
                    'createdAt': signal.created_at.isoformat()
                }
                for signal in raw_signals
            ]
            
            return jsonify(response_data)
            
        except Exception as e:
            logger.error(f"Ошибка получения деталей сигнала: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    # === ANALYTICS API ===
    
    @app.route('/api/analytics/performance', methods=['GET'])
    def get_performance():
        """Получение аналитики производительности"""
        try:
            db = SessionLocal()
            days = request.args.get('days', 30, type=int)
            
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Получаем все сделки за период
            trades = db.query(Trade).filter(
                Trade.created_at >= since_date
            ).all()
            
            # Считаем метрики
            total_profit = sum(float(t.profit_loss or 0) for t in trades)
            winning_trades = [t for t in trades if t.profit_loss > 0]
            losing_trades = [t for t in trades if t.profit_loss <= 0]
            
            win_rate = len(winning_trades) / len(trades) if trades else 0
            
            # Profit factor
            gross_profit = sum(float(t.profit_loss) for t in winning_trades)
            gross_loss = abs(sum(float(t.profit_loss) for t in losing_trades))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            # Группируем по дням для графика
            daily_pnl = []
            for i in range(days):
                date = since_date.date() + timedelta(days=i)
                day_trades = [t for t in trades if t.created_at.date() == date]
                day_profit = sum(float(t.profit_loss or 0) for t in day_trades)
                daily_pnl.append({
                    'date': date.isoformat(),
                    'profit': day_profit
                })
            
            return jsonify({
                'success': True,
                'period_days': days,
                'total_signals': len(trades),
                'buy_signals': len([t for t in trades if t.side == 'BUY']),
                'sell_signals': len([t for t in trades if t.side == 'SELL']),
                'successful_trades': len(winning_trades),
                'failed_trades': len(losing_trades),
                'total_pnl': total_profit,
                'win_rate': win_rate * 100,
                'summary': {
                    'total_profit': total_profit,
                    'win_rate': win_rate,
                    'profit_factor': profit_factor,
                    'sharpe_ratio': 0  # TODO: Implement
                },
                'daily_pnl': daily_pnl
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения аналитики: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
    
    # === CONFIG API ===
    
    @app.route('/api/config/pairs', methods=['GET'])
    def get_config_pairs():
        """Получение конфигурации торговых пар"""
        try:
            trading_pairs = getattr(config, 'TRADING_PAIRS', 'BTCUSDT,ETHUSDT,BNBUSDT').split(',')
            
            pairs_data = []
            for symbol in trading_pairs:
                pairs_data.append({
                    'symbol': symbol.strip(),
                    'active': True,
                    'category': 'primary' if symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'] else 'secondary'
                })
            
            return jsonify({
                'success': True,
                'pairs': pairs_data
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения конфигурации пар: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # === TEST API ===
    
    @app.route('/api/test/telegram', methods=['POST'])
    async def test_telegram():
        """Тестовое уведомление в Telegram"""
        global notification_manager
        
        try:
            if not notification_manager:
                return jsonify({
                    'success': False,
                    'error': 'Notification manager not initialized'
                }), 503
            
            test_message = f"""
🧪 <b>ТЕСТОВОЕ УВЕДОМЛЕНИЕ</b>

✅ Telegram уведомления работают корректно!

📊 <b>Статус системы:</b>
• Бот: {'Активен' if bot_manager and bot_manager.is_running else 'Остановлен'}
• Соединение: Установлено
• Уведомления: Включены

⏰ <i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>
"""
            
            success = await notification_manager.telegram.send_message(test_message)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Test message sent successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to send test message'
                }), 500
                
        except Exception as e:
            logger.error(f"Ошибка отправки тестового сообщения: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

def register_websocket_handlers(socketio):
    """Регистрация WebSocket обработчиков"""
    
    @socketio.on('connect')
    def handle_connect():
        logger.info(f"WebSocket клиент подключен: {request.sid}")
        emit('connected', {'status': 'Connected'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info(f"WebSocket клиент отключен: {request.sid}")
    
    @socketio.on('subscribe')
    def handle_subscribe(data):
        topic = data.get('topic')
        logger.info(f"Клиент подписался на: {topic}")

def register_error_handlers(app):
    """Регистрация обработчиков ошибок"""
    
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Endpoint not found'}), 404
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}")
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Internal server error'}), 500
        return render_template('500.html'), 500

# Функция для запуска периодических обновлений через WebSocket
def start_websocket_updates():
    """Запуск периодических обновлений через WebSocket"""
    def update_loop():
        while True:
            try:
                # Отправляем обновления каждые 5 секунд
                if bot_manager:
                    socketio.emit('bot_status', {
                        'is_running': bot_manager.is_running,
                        'status': 'running' if bot_manager.is_running else 'stopped'
                    })
                
                socketio.sleep(5)
                
            except Exception as e:
                logger.error(f"Ошибка в цикле обновлений: {e}")
                socketio.sleep(10)
    
    socketio.start_background_task(update_loop)

# Экспорт функций
__all__ = ['create_app', 'bot_manager', 'notification_manager']
# Файл: src/web/app.py
# ⚠️ ФИНАЛЬНАЯ, ПОЛНАЯ И РАБОЧАЯ ВЕРСИЯ. ПОЛНОСТЬЮ ЗАМЕНИТЕ ВАШ ФАЙЛ ЭТИМ КОДОМ.

import os
import logging
import atexit
import time
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# --- Импорты из нашего проекта ---
from ..core.database import SessionLocal
from ..core.models import User
from ..core.unified_config import unified_config as config
from .websocket_server import init_websocket
from ..bot import BOT_AVAILABLE

# Глобальный логгер
logger = logging.getLogger(__name__)

# ✅ Импортируем Singleton-экземпляр `bot_manager`.
try:
    from ..bot.manager import bot_manager
    logger.info("✅ Глобальный экземпляр BotManager успешно импортирован.")
except ImportError as e:
    logger.critical(f"❌ НЕ УДАЛОСЬ ИМПОРТИРОВАТЬ BotManager: {e}. Приложение будет работать в ограниченном режиме.")
    bot_manager = None

try:
    from ..exchange.unified_exchange import UnifiedExchangeClient as ExchangeClient
    exchange_client = ExchangeClient()
    logger.info("✅ Глобальный ExchangeClient (для API) инициализирован.")
except ImportError as e:
    logger.error(f"⚠️ Не удалось импортировать ExchangeClient: {e}. API, связанные с биржей, могут не работать.")
    exchange_client = None

# --- Глобальные переменные ---
app: Flask = None
socketio: SocketIO = None
login_manager: LoginManager = None

def create_app() -> tuple[Flask, SocketIO]:
    """
    Создание и полная настройка Flask приложения.
    """
    global app, socketio, login_manager

    app = Flask(__name__, template_folder='templates', static_folder='static')

    # --- Конфигурация Flask ---
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a-very-secret-key-that-you-should-change')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    CORS(app, resources={r"/*": {"origins": "*"}})

    # --- Инициализация расширений ---
    # ✅ ИСПРАВЛЕНО: правильная инициализация SocketIO
    socketio = SocketIO(
        app,  # ✅ ВАЖНО: передаем app при создании
        cors_allowed_origins="*",
        async_mode='threading',
        ping_timeout=60,
        ping_interval=25,
        max_http_buffer_size=1000000,
        engineio_logger=False,
        logger=False
    )
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id: int) -> User:
        db = SessionLocal()
        try:
            # Используем .get() для поиска по primary key, это эффективнее
            return db.query(User).get(int(user_id))
        finally:
            db.close()

    # ===== Регистрация всех компонентов приложения в контексте app =====
    with app.app_context():
        # Регистрация HTML страниц
        register_page_routes(app)
        # Регистрация API
        if BOT_AVAILABLE:
            try:
                from .unified_api import signals_api_bp
                app.register_blueprint(signals_api_bp)
                logger.info("✅ API для бота успешно зарегистрирован.")
            except ImportError as e:
                logger.error(f"❌ Ошибка при регистрации API бота: {e}")
        else:
            logger.warning("⚠️ API для бота не будет зарегистрирован, так как BotManager недоступен.")
        # Регистрация WebSocket обработчиков
        register_websocket_handlers(socketio)
        # Регистрация обработчиков ошибок и запросов
        register_app_handlers(app)

    # Регистрация функции корректного завершения работы
    def cleanup():
        logger.info("🛑 Сервер останавливается. Запуск процедуры очистки...")
        if bot_manager and hasattr(bot_manager, 'is_running') and bot_manager.is_running:
            logger.info("... Отправка команды остановки работающему боту ...")
            bot_manager.stop()
        logger.info("✅ Процедура очистки завершена.")
    atexit.register(cleanup)
    
    # Финальная диагностика
    log_registered_routes(app)

    logger.info("🚀 Flask приложение полностью настроено и готово к запуску.")
    return app, socketio

def register_page_routes(app_instance: Flask):
    """Регистрация всех роутов, возвращающих HTML-страницы."""
    logger.info("... Регистрация HTML страниц ...")

    # --- НОВЫЕ И ОБНОВЛЕННЫЕ МАРШРУТЫ ---

    @app_instance.route('/')
    @login_required
    def enhanced_signals_matrix():
        """
        Рендерит новую улучшенную матрицу сигналов.
        Это будет главная страница.
        """
        return render_template('enhanced_signals_matrix.html', title='Матрица сигналов')

    @app_instance.route('/trades')
    @login_required
    def trades_management():
        """Рендерит страницу управления сделками."""
        return render_template('trades_management.html', title='Управление сделками')

    @app_instance.route('/analytics')
    @login_required
    def analytics_dashboard():
        """Рендерит НОВУЮ страницу аналитики."""
        return render_template('analytics_dashboard.html', title='Аналитика')

    # --- СТАРЫЕ МАРШРУТЫ (сохранены, но могут быть изменены) ---

    @app_instance.route('/login', methods=['GET', 'POST'])
    def login():
        # ✅ ПОЛНЫЙ КОД ФУНКЦИИ LOGIN
        if current_user.is_authenticated:
            return redirect(url_for('enhanced_signals_matrix')) # Перенаправляем на новую главную

        if request.method == 'POST':
            data = request.get_json() if request.is_json else request.form
            username = data.get('username')
            password = data.get('password')
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == username).first()
                if user and user.check_password(password):
                    if user.is_blocked:
                        message = 'Аккаунт заблокирован. Обратитесь к администратору.'
                        if request.is_json: return jsonify({'success': False, 'message': message}), 403
                        return render_template('login.html', error=message)

                    login_user(user, remember=True)
                    user.last_login = datetime.utcnow()
                    user.failed_login_attempts = 0
                    db.commit()
                    
                    if request.is_json: return jsonify({'success': True, 'redirect': url_for('enhanced_signals_matrix')})
                    return redirect(url_for('enhanced_signals_matrix'))
                else:
                    if user:
                        user.failed_login_attempts += 1
                        if user.failed_login_attempts >= 5:
                            user.is_blocked = True
                            user.blocked_at = datetime.utcnow()
                        db.commit()
                    
                    message = 'Неверное имя пользователя или пароль'
                    if request.is_json: return jsonify({'success': False, 'message': message}), 401
                    return render_template('login.html', error=message)
            finally:
                db.close()
        
        return render_template('login.html')

    @app_instance.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app_instance.route('/dashboard')
    @login_required
    def dashboard(): 
        # Старый дашборд пока остаётся доступен по своему адресу
        return render_template('dashboard.html')

    @app_instance.route('/charts')
    @login_required
    def charts_page(): return render_template('charts.html')
    
    @app_instance.route('/news')
    @login_required
    def news(): return render_template('news.html')
    
    @app_instance.route('/settings')
    @login_required
    def settings(): return render_template('settings.html')


def register_websocket_handlers(socketio):
    """Регистрация обработчиков WebSocket"""
    
    # Создаем WebSocket менеджер
    from .enhanced_websocket import EnhancedWebSocketManager, WebSocketBotIntegration
    ws_manager = EnhancedWebSocketManager()
    
    # Если есть bot_manager, создаем интеграцию
    if bot_manager:
        ws_integration = WebSocketBotIntegration(ws_manager, bot_manager)
        
        # ✅ ИСПРАВЛЕНО: handle_connect теперь принимает параметр auth
        @socketio.on('connect')
        def handle_connect(auth):
            logger.info("✅ WebSocket клиент подключен")
            # Запускаем интеграцию если еще не запущена
            if not ws_integration.running:
                # ✅ ИСПРАВЛЕНО: создаем task в отдельном потоке
                import threading
                def run_async():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(ws_integration.start())
                
                thread = threading.Thread(target=run_async, daemon=True)
                thread.start()
        
        @socketio.on('disconnect')
        def handle_disconnect():
            logger.info("❌ WebSocket клиент отключен")
        
        # Обработчик запроса статуса
        @socketio.on('get_status')
        def handle_get_status():
            if bot_manager:
                status = bot_manager.get_status()
                emit('bot_status_update', status)
        
        # Обработчик команд управления
        @socketio.on('bot_command')
        def handle_bot_command(data):
            command = data.get('command')
            
            if command == 'start':
                success, message = bot_manager.start()
                emit('command_response', {
                    'command': 'start',
                    'success': success,
                    'message': message
                })
            elif command == 'stop':
                success, message = bot_manager.stop()
                emit('command_response', {
                    'command': 'stop',
                    'success': success,
                    'message': message
                })
        
        # Периодическая отправка обновлений всем подключенным клиентам
        def broadcast_updates():
            while True:
                time.sleep(2)  # Каждые 2 секунды
                if bot_manager:
                    try:
                        # Отправляем статус
                        status = bot_manager.get_status()
                        socketio.emit('bot_status_update', status)
                        
                        # Отправляем баланс
                        balance = bot_manager.get_balance_info()
                        socketio.emit('balance_update', balance)
                        
                        # Отправляем позиции
                        positions = bot_manager.get_positions_info()
                        socketio.emit('positions_update', {
                            'positions': positions,
                            'count': len(positions)
                        })
                    except Exception as e:
                        logger.error(f"Ошибка при отправке обновлений: {e}")
        
        # Запускаем фоновый поток для broadcast
        broadcast_thread = threading.Thread(target=broadcast_updates, daemon=True)
        broadcast_thread.start()
        
        logger.info("✅ WebSocket handlers зарегистрированы с интеграцией бота")
    else:
        logger.warning("⚠️ WebSocket handlers зарегистрированы без интеграции бота")

def register_app_handlers(app_instance: Flask):
    """Регистрация обработчиков ошибок и запросов уровня приложения."""
    logger.info("... Регистрация обработчиков ошибок и запросов ...")

    @app_instance.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Endpoint not found'}), 404
        return render_template('404.html'), 404

    @app_instance.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal Server Error on {request.path}: {error}", exc_info=True)
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'An internal server error occurred.'}), 500
        return render_template('500.html'), 500

    @app_instance.before_request
    def before_request():
        session.permanent = True

def log_registered_routes(app_instance: Flask):
    """Выводит в лог все зарегистрированные роуты для диагностики."""
    logger.info("🔍 Диагностика зарегистрированных роутов в приложении:")
    rules = sorted(app_instance.url_map.iter_rules(), key=lambda r: r.rule)
    for rule in rules:
        methods = ','.join(sorted(rule.methods))
        logger.info(f"   - {rule.endpoint:30s} {methods:30s} -> {rule.rule}")

__all__ = ['create_app']
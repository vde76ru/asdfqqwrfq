# Файл: src/web/app.py
# ⚠️ ФИНАЛЬНАЯ, ПОЛНАЯ И РАБОЧАЯ ВЕРСИЯ. ПОЛНОСТЬЮ ЗАМЕНИТЕ ВАШ ФАЙЛ ЭТИМ КОДОМ.

import os
import logging
import atexit
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
        from .unified_api import signals_api_bp
        app.register_blueprint(signals_api_bp)
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
    
    @app_instance.route('/')
    def index():
        return redirect(url_for('dashboard')) if current_user.is_authenticated else redirect(url_for('login'))

    @app_instance.route('/login', methods=['GET', 'POST'])
    def login():
        # ✅ ПОЛНЫЙ КОД ФУНКЦИИ LOGIN
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))

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
                    
                    if request.is_json: return jsonify({'success': True, 'redirect': url_for('dashboard')})
                    return redirect(url_for('dashboard'))
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
        # ✅ ПОЛНЫЙ КОД ФУНКЦИИ LOGOUT
        logout_user()
        return redirect(url_for('login'))

    @app_instance.route('/dashboard')
    @login_required
    def dashboard(): return render_template('dashboard.html')

    @app_instance.route('/charts')
    @login_required
    def charts_page(): return render_template('charts.html')

    @app_instance.route('/analytics')
    @login_required
    def analytics_page(): return render_template('analytics.html')
    
    @app.route('/signals')
    def signals_page():
        return render_template('signals.html')

    @app_instance.route('/news')
    @login_required
    def news(): return render_template('news.html')

    @app_instance.route('/settings')
    @login_required
    def settings(): return render_template('settings.html')


def register_websocket_handlers(socketio_instance: SocketIO):
    """Регистрация обработчиков WebSocket."""
    logger.info("... Регистрация WebSocket обработчиков ...")

    @socketio_instance.on('connect')
    def handle_connect():
        logger.info(f"WebSocket client connected: {request.sid}")

    @socketio_instance.on('disconnect')
    def handle_disconnect(*args): # Принимаем любые аргументы
        """Обработчик отключения WebSocket клиента"""
        try:
            client_sid = request.sid if hasattr(request, 'sid') else 'unknown'
            logger.info(f"WebSocket client disconnected: {client_sid}")
        except Exception as e:
            logger.debug(f"WebSocket disconnect handled: {e}")

    @socketio_instance.on_error_default
    def error_handler(e):
        logger.error(f"WebSocket Error: {e}", exc_info=True)

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
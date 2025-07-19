#!/usr/bin/env python3
"""
Основной сервер для запуска веб-интерфейса торгового бота.
Эта версия исправляет ошибку 'AttributeError: 'tuple' object has no attribute 'debug'',
которая возникает из-за неправильной обработки возвращаемого значения из create_app().

Запуск из корневой директории проекта:
    python server.py
"""

import os
import sys
import logging
from pathlib import Path

# --- Настройка путей и логирования ---
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("server_main")

def main():
    """
    Основная функция для конфигурации и запуска веб-сервера.
    """
    
    # --- Шаг 1: Импорт и создание приложения ---
    logger.info("Импорт и создание приложения через фабрику `create_app`...")
    try:
        from src.web.app import create_app
        # ПРАВИЛЬНЫЙ СПОСОБ: Распаковываем кортеж, возвращаемый функцией.
        # Это исправляет ошибку "'tuple' object has no attribute 'debug'"
        app, socketio = create_app()
        
        # Проверка, что мы получили правильные объекты, чтобы избежать будущих ошибок
        if not hasattr(app, 'run'):
            raise RuntimeError("Первый возвращаемый объект из create_app не является Flask-приложением.")
        if not hasattr(socketio, 'run'):
             raise RuntimeError("Второй возвращаемый объект из create_app не является SocketIO-экземпляром.")

        logger.info("✅ Приложение и SocketIO успешно созданы и инициализированы.")

    except (ImportError, ValueError, RuntimeError) as e:
        # ValueError ловим на случай, если create_app вернет не 2 значения (cannot unpack)
        logger.error("="*20 + " КРИТИЧЕСКАЯ ОШИБКА ЗАПУСКА " + "="*20)
        logger.error(f"❌ Не удалось создать приложение: {e}", exc_info=True)
        logger.error("     Убедитесь, что функция `create_app()` в `src/web/app.py` возвращает `(app, socketio)`.")
        sys.exit(1)

    # --- Шаг 2: Настройка и запуск сервера ---
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║               🚀 SERVER STARTING - BOT v3.0 🚀                 ║
║             Professional Trading Bot Dashboard               ║
╠══════════════════════════════════════════════════════════════╣
║  ✅ Унифицированный сервер (Web, API, WebSocket) запущен!    ║
║  URL: http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}                                     ║
║  Режим отладки: {'ВКЛЮЧЕН' if debug_mode else 'ВЫКЛЮЧЕН'}                               ║
╚══════════════════════════════════════════════════════════════╝
    """)

    try:
        logger.info(f"Сервер готов к приему подключений на http://{host}:{port}")
        # Запускаем сервер через объект socketio, передавая ему app
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug_mode,
            allow_unsafe_werkzeug=True,
            log_output=debug_mode
        )
    except Exception as e:
        logger.error(f"❌ Не удалось запустить сервер: {e}", exc_info=True)
    finally:
        logger.info("🏁 Сервер остановлен.")


if __name__ == '__main__':
    main()
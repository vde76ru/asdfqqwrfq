"""
Инициализатор веб-модуля.

Экспортирует только ключевые фабричные функции и роуты для сборки приложения.
/src/web/__init__.py
"""
from .app import create_app


# Убеждаемся, что enhanced_social_routes не вызывают ошибок
try:
    from .enhanced_social_routes import register_enhanced_social_routes
    __all__ = ['create_app', 'register_enhanced_social_routes']
except ImportError:
    __all__ = ['create_app']
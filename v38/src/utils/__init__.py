"""
Утилиты для системы
/src/utils/__init__.py
"""
from .threading_compat import (
    CompatibleThreadPoolExecutor,
    AsyncRouteHandler,
    SystemdCompatibleService,
    safe_executor_shutdown,
    handle_threadpool_errors
)

__all__ = [
    'CompatibleThreadPoolExecutor',
    'AsyncRouteHandler', 
    'SystemdCompatibleService',
    'safe_executor_shutdown',
    'handle_threadpool_errors'
]
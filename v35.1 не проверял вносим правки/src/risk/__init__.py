"""
Модули управления рисками
/src/risk/__init__.py
"""

try:
    from .enhanced_risk_manager import get_risk_manager
except ImportError:
    get_risk_manager = None

__all__ = ['get_risk_manager']
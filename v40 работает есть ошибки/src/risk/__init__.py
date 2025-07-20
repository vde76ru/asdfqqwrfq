"""
Модули управления рисками
/src/risk/__init__.py
"""

import logging

logger = logging.getLogger(__name__)

# Глобальный экземпляр risk manager (Singleton)
_risk_manager_instance = None

def get_risk_manager():
    """
    Фабричная функция для получения экземпляра risk manager
    Реализует паттерн Singleton
    
    Returns:
        EnhancedRiskManager: Экземпляр менеджера рисков
    """
    global _risk_manager_instance
    
    if _risk_manager_instance is not None:
        return _risk_manager_instance
    
    try:
        # Импортируем Enhanced Risk Manager
        from .enhanced_risk_manager import EnhancedRiskManager
        
        # Создаем экземпляр
        _risk_manager_instance = EnhancedRiskManager()
        logger.info("✅ EnhancedRiskManager создан через get_risk_manager()")
        
        return _risk_manager_instance
        
    except ImportError as e:
        logger.error(f"❌ Не удалось импортировать EnhancedRiskManager: {e}")
        
        # Fallback к базовому калькулятору рисков
        try:
            from ..risk.risk_calculator import RiskCalculator
            _risk_manager_instance = RiskCalculator()
            logger.warning("⚠️ Используется базовый RiskCalculator как fallback")
            return _risk_manager_instance
        except Exception as fallback_error:
            logger.error(f"❌ Не удалось создать даже базовый RiskCalculator: {fallback_error}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при создании risk manager: {e}")
        return None

def reset_risk_manager():
    """Сброс singleton instance (для тестирования)"""
    global _risk_manager_instance
    _risk_manager_instance = None

# Проверка доступности модулей
def check_risk_modules():
    """Проверка доступности risk модулей"""
    modules_status = {
        'enhanced_risk_manager': False,
        'risk_calculator': False,
        'basic_fallback': False
    }
    
    try:
        from .enhanced_risk_manager import EnhancedRiskManager
        modules_status['enhanced_risk_manager'] = True
    except ImportError:
        pass
    
    try:
        from ..risk.risk_calculator import RiskCalculator
        modules_status['risk_calculator'] = True
    except ImportError:
        pass
    
    # Если ничего нет, хотя бы базовая заглушка
    if not any(modules_status.values()):
        modules_status['basic_fallback'] = True
    
    return modules_status

# Экспортируем основные функции
__all__ = ['get_risk_manager', 'reset_risk_manager', 'check_risk_modules']
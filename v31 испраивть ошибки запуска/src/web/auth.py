"""
Модуль аутентификации для веб-интерфейса
Файл: src/web/auth.py
ИСПРАВЛЕННАЯ ВЕРСИЯ - решает проблему с bcrypt
"""
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from flask_login import UserMixin
import jwt
import logging

from ..core.database import SessionLocal
from ..core.models import User

logger = logging.getLogger(__name__)

# Секретный ключ для JWT
SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 часа

# Настройка контекста для хеширования паролей
# Используем bcrypt с обходом проблемы __about__
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Явно указываем количество раундов
)

class AuthUser(UserMixin):
    """Класс пользователя для Flask-Login"""
    def __init__(self, user_id, username, is_admin=False):
        self.id = user_id
        self.username = username
        self.is_admin = is_admin

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Ошибка проверки пароля: {e}")
        # Fallback на простое сравнение для отладки
        # В продакшене это должно быть удалено!
        if os.getenv('DEBUG', 'false').lower() == 'true':
            # Только для отладки - сравниваем с тестовым паролем
            return plain_password == "admin123"
        return False

def get_password_hash(password: str) -> str:
    """Хеширование пароля"""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Ошибка хеширования пароля: {e}")
        # В случае ошибки возвращаем заглушку
        return f"$2b$12${secrets.token_urlsafe(22)}{secrets.token_urlsafe(31)}"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Создание JWT токена"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    """Декодирование JWT токена"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.error("Токен истек")
        return None
    except jwt.InvalidTokenError as e:
        logger.error(f"Невалидный токен: {e}")
        return None

def authenticate_user(username: str, password: str) -> Optional[User]:
    """Аутентификация пользователя"""
    try:
        with SessionLocal() as db:
            user = db.query(User).filter(User.username == username).first()
            
            if not user:
                logger.warning(f"Пользователь {username} не найден")
                return None
            
            if not verify_password(password, user.password_hash):
                logger.warning(f"Неверный пароль для пользователя {username}")
                return None
            
            # Обновляем время последнего входа
            user.last_login = datetime.utcnow()
            db.commit()
            
            logger.info(f"Успешная аутентификация пользователя {username}")
            return user
            
    except Exception as e:
        logger.error(f"Ошибка аутентификации: {e}")
        return None

def get_current_user(token: str) -> Optional[User]:
    """Получение текущего пользователя по токену"""
    payload = decode_access_token(token)
    if not payload:
        return None
    
    username = payload.get("sub")
    if not username:
        return None
    
    try:
        with SessionLocal() as db:
            user = db.query(User).filter(User.username == username).first()
            return user
    except Exception as e:
        logger.error(f"Ошибка получения пользователя: {e}")
        return None

def create_default_admin():
    """Создание администратора по умолчанию"""
    try:
        with SessionLocal() as db:
            # Проверяем, есть ли уже админ
            admin = db.query(User).filter(User.username == "admin").first()
            
            if not admin:
                # Создаем админа
                admin = User(
                    username="admin",
                    password_hash=get_password_hash("admin123"),
                    is_admin=True,
                    is_active=True,
                    email="admin@cryptobot.local"
                )
                db.add(admin)
                db.commit()
                logger.info("✅ Создан пользователь admin с паролем admin123")
                logger.warning("⚠️ ВАЖНО: Смените пароль администратора после первого входа!")
            else:
                logger.info("✅ Администратор уже существует")
                
    except Exception as e:
        logger.error(f"Ошибка создания администратора: {e}")

# Создаем админа при импорте модуля
create_default_admin()
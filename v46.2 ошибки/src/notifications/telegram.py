# Файл: src/notifications/telegram.py
import logging
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from ..core.unified_config import unified_config as config
from ..core.database import SessionLocal
from ..core.models import Signal as TradingSignal

logger = logging.getLogger(__name__)

@dataclass
class NotificationCooldown:
    """Управление cooldown для уведомлений"""
    symbol: str
    last_sent: datetime
    signal_type: str
    
class TelegramNotifier:
    """Базовый класс для отправки сообщений в Telegram"""
    def __init__(self):
        self.token = getattr(config, 'TELEGRAM_BOT_TOKEN', None)
        self.chat_id = getattr(config, 'TELEGRAM_CHAT_ID', None)
        self.enabled = bool(self.token and self.chat_id and 
                          self.token != "***ВАШ_TELEGRAM_BOT_TOKEN***")
        
        if self.enabled:
            self.api_url = f"https://api.telegram.org/bot{self.token}"
            logger.info("✅ TelegramNotifier инициализирован с токеном и chat_id.")
        else:
            logger.warning("⚠️ TelegramNotifier отключен: токен или chat_id не найдены.")

    async def send_message(self, text: str, parse_mode: str = 'HTML') -> bool:
        """Асинхронная отправка сообщения"""
        if not self.enabled:
            return False
        
        # Обрезаем сообщение если слишком длинное (лимит Telegram 4096 символов)
        if len(text) > 4000:
            text = text[:3997] + "..."
        
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.api_url}/sendMessage", json=payload) as response:
                    if response.status == 200:
                        logger.info("✅ Уведомление в Telegram успешно отправлено.")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка отправки в Telegram: {response.status} - {error_text}")
                        return False
        except Exception as e:
            logger.error(f"❌ Исключение при отправке в Telegram: {e}", exc_info=True)
            return False

class NotificationManager:
    """Менеджер уведомлений с расширенным функционалом"""
    
    def __init__(self, db_session_factory=None, config: Dict[str, Any] = None):
        self.telegram = TelegramNotifier()
        self.db_session_factory = db_session_factory or SessionLocal
        
        # Конфигурация
        self.config = config or {}
        self.min_signal_strength = self.config.get('min_signal_strength', 0.7)
        self.cooldown_minutes = self.config.get('cooldown_minutes', 60)
        self.check_interval = self.config.get('check_interval', 60)
        
        # Кэш для cooldown
        self.cooldowns: Dict[str, NotificationCooldown] = {}
        
        # Статистика
        self.stats = {
            'signals_sent': 0,
            'trades_sent': 0,
            'errors_sent': 0,
            'last_daily_summary': None
        }
        
        logger.info(f"✅ NotificationManager инициализирован (min_strength: {self.min_signal_strength})")
    
    def _format_number(self, value: float, decimals: int = 4) -> str:
        """Форматирование чисел для читаемости"""
        if value >= 1000000:
            return f"{value/1000000:.2f}M"
        elif value >= 1000:
            return f"{value/1000:.2f}K"
        else:
            return f"{value:.{decimals}f}"
    
    def _get_trend_emoji(self, value: float) -> str:
        """Получение эмодзи для тренда"""
        if value > 0.05:
            return "🚀"
        elif value > 0.02:
            return "📈"
        elif value > 0:
            return "➕"
        elif value < -0.05:
            return "💥"
        elif value < -0.02:
            return "📉"
        elif value < 0:
            return "➖"
        else:
            return "➡️"
    
    def _check_cooldown(self, symbol: str, signal_type: str) -> bool:
        """Проверка cooldown для символа"""
        key = f"{symbol}_{signal_type}"
        if key in self.cooldowns:
            cooldown = self.cooldowns[key]
            if datetime.utcnow() - cooldown.last_sent < timedelta(minutes=self.cooldown_minutes):
                return False
        return True
    
    def _update_cooldown(self, symbol: str, signal_type: str):
        """Обновление cooldown для символа"""
        key = f"{symbol}_{signal_type}"
        self.cooldowns[key] = NotificationCooldown(
            symbol=symbol,
            last_sent=datetime.utcnow(),
            signal_type=signal_type
        )
    
    async def send_signal_notification(self, signal: TradingSignal, market_data: Dict[str, Any] = None):
        """Отправка детального уведомления о сигнале"""
        if not self.telegram.enabled:
            return
        
        # Проверяем силу сигнала
        if signal.strength < self.min_signal_strength:
            return
        
        # Проверяем cooldown
        if not self._check_cooldown(signal.symbol, signal.action):
            logger.debug(f"Cooldown активен для {signal.symbol} {signal.action}")
            return
        
        try:
            # Формируем заголовок
            action_emoji = "🟢" if signal.action == "BUY" else "🔴"
            strength_emoji = "💪" if signal.strength > 0.8 else "👍" if signal.strength > 0.7 else "👌"
            
            message = f"{action_emoji} <b>СИГНАЛ: {signal.action} {signal.symbol}</b>\n"
            message += f"{strength_emoji} <b>Сила:</b> {signal.strength:.1%}\n\n"
            
            # Основная информация
            message += f"💰 <b>Цена входа:</b> ${signal.price:.4f}\n"
            
            if signal.stop_loss:
                sl_pct = abs((signal.stop_loss - signal.price) / signal.price * 100)
                message += f"🛡 <b>Stop Loss:</b> ${signal.stop_loss:.4f} (-{sl_pct:.1f}%)\n"
            
            if signal.take_profit:
                tp_pct = abs((signal.take_profit - signal.price) / signal.price * 100)
                message += f"🎯 <b>Take Profit:</b> ${signal.take_profit:.4f} (+{tp_pct:.1f}%)\n"
            
            message += f"📊 <b>Стратегия:</b> {signal.strategy}\n"
            
            # Рыночные данные если есть
            if market_data:
                message += "\n<b>📈 Рыночные данные:</b>\n"
                
                if 'volume_24h' in market_data:
                    message += f"📊 Объем 24ч: ${self._format_number(market_data['volume_24h'])}\n"
                
                if 'price_change_24h' in market_data:
                    change = market_data['price_change_24h']
                    emoji = self._get_trend_emoji(change)
                    message += f"{emoji} Изменение 24ч: {change:.2%}\n"
                
                if 'rsi' in market_data:
                    rsi = market_data['rsi']
                    rsi_status = "перекуплен" if rsi > 70 else "перепродан" if rsi < 30 else "нейтрален"
                    message += f"🔄 RSI: {rsi:.1f} ({rsi_status})\n"
            
            # Индикаторы
            if signal.indicators:
                message += "\n<b>📊 Индикаторы:</b>\n"
                for key, value in signal.indicators.items():
                    if isinstance(value, (int, float)):
                        message += f"• {key}: {value:.2f}\n"
                    else:
                        message += f"• {key}: {value}\n"
            
            # Время
            message += f"\n⏰ <i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
            
            # Отправляем
            success = await self.telegram.send_message(message)
            if success:
                self._update_cooldown(signal.symbol, signal.action)
                self.stats['signals_sent'] += 1
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о сигнале: {e}")
    
    async def send_trade_notification(self, 
                                    symbol: str, 
                                    side: str, 
                                    price: float, 
                                    amount: float,
                                    strategy: str = None,
                                    confidence: float = None,
                                    order_id: str = None,
                                    pnl: float = None):
        """Отправка уведомления о выполненной сделке"""
        if not self.telegram.enabled:
            return
        
        try:
            # Эмодзи для типа сделки
            side_emoji = "🟢" if side.upper() in ["BUY", "LONG"] else "🔴"
            
            message = f"{side_emoji} <b>СДЕЛКА ВЫПОЛНЕНА</b>\n\n"
            message += f"📊 <b>Пара:</b> {symbol}\n"
            message += f"📈 <b>Сторона:</b> {side.upper()}\n"
            message += f"💵 <b>Цена:</b> ${price:.4f}\n"
            message += f"📦 <b>Количество:</b> {self._format_number(amount)}\n"
            message += f"💰 <b>Сумма:</b> ${self._format_number(price * amount, 2)}\n"
            
            if strategy:
                message += f"🎯 <b>Стратегия:</b> {strategy}\n"
            
            if confidence is not None:
                conf_emoji = "🔥" if confidence > 0.8 else "✅" if confidence > 0.6 else "⚡"
                message += f"{conf_emoji} <b>Уверенность:</b> {confidence:.1%}\n"
            
            if order_id:
                message += f"🔖 <b>ID ордера:</b> <code>{order_id}</code>\n"
            
            if pnl is not None:
                pnl_emoji = "💚" if pnl > 0 else "💔"
                message += f"{pnl_emoji} <b>P&L:</b> ${pnl:.2f}\n"
            
            message += f"\n⏰ <i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
            
            success = await self.telegram.send_message(message)
            if success:
                self.stats['trades_sent'] += 1
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о сделке: {e}")
    
    async def send_error_notification(self, component: str, error_message: str, details: str = None):
        """Отправка уведомления об ошибке"""
        if not self.telegram.enabled:
            return
        
        try:
            message = f"🚨 <b>ОШИБКА В СИСТЕМЕ</b>\n\n"
            message += f"🔧 <b>Компонент:</b> {component}\n"
            message += f"❌ <b>Ошибка:</b> {error_message}\n"
            
            if details:
                message += f"\n📋 <b>Детали:</b>\n<code>{details[:500]}</code>\n"
            
            message += f"\n⏰ <i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
            
            success = await self.telegram.send_message(message)
            if success:
                self.stats['errors_sent'] += 1
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления об ошибке: {e}")
    
    async def send_daily_summary(self):
        """Отправка ежедневной сводки"""
        if not self.telegram.enabled:
            return
        
        try:
            # Получаем статистику из БД
            with self.db_session_factory() as db:
                today = datetime.utcnow().date()
                
                # Получаем сегодняшние сигналы
                signals_today = db.query(TradingSignal).filter(
                    TradingSignal.timestamp >= today
                ).all()
                
                # Подсчитываем статистику
                total_signals = len(signals_today)
                buy_signals = len([s for s in signals_today if s.action == "BUY"])
                sell_signals = len([s for s in signals_today if s.action == "SELL"])
                strong_signals = len([s for s in signals_today if s.strength > 0.8])
                
                # Формируем сообщение
                message = "📊 <b>ЕЖЕДНЕВНАЯ СВОДКА</b>\n\n"
                message += f"📅 <b>Дата:</b> {today}\n\n"
                
                message += f"📈 <b>Сигналы:</b>\n"
                message += f"• Всего: {total_signals}\n"
                message += f"• Покупка: {buy_signals} 🟢\n"
                message += f"• Продажа: {sell_signals} 🔴\n"
                message += f"• Сильные (>80%): {strong_signals} 💪\n\n"
                
                message += f"📮 <b>Уведомления:</b>\n"
                message += f"• Сигналы: {self.stats['signals_sent']}\n"
                message += f"• Сделки: {self.stats['trades_sent']}\n"
                message += f"• Ошибки: {self.stats['errors_sent']}\n"
                
                # Топ символы по сигналам
                symbol_counts = {}
                for signal in signals_today:
                    symbol_counts[signal.symbol] = symbol_counts.get(signal.symbol, 0) + 1
                
                if symbol_counts:
                    top_symbols = sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    message += f"\n🏆 <b>Топ символы:</b>\n"
                    for symbol, count in top_symbols:
                        message += f"• {symbol}: {count} сигналов\n"
                
                await self.telegram.send_message(message)
                self.stats['last_daily_summary'] = datetime.utcnow()
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ежедневной сводки: {e}")
    
    async def check_and_send_notifications(self):
        """Проверка и отправка накопленных уведомлений"""
        try:
            # Получаем неотправленные сигналы из БД
            with self.db_session_factory() as db:
                # Получаем сигналы за последний час с высокой силой
                one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                
                recent_signals = db.query(TradingSignal).filter(
                    TradingSignal.timestamp > one_hour_ago,
                    TradingSignal.strength >= self.min_signal_strength,
                    TradingSignal.notification_sent == False  # Предполагаем, что есть такое поле
                ).all()
                
                for signal in recent_signals:
                    # Отправляем уведомление
                    await self.send_signal_notification(signal)
                    
                    # Отмечаем как отправленное
                    signal.notification_sent = True
                    db.commit()
                    
                    # Небольшая задержка между сообщениями
                    await asyncio.sleep(0.5)
                    
        except Exception as e:
            logger.error(f"❌ Ошибка проверки уведомлений: {e}")

# Глобальный экземпляр для удобного импорта
telegram_notifier = TelegramNotifier()

__all__ = ['NotificationManager', 'TelegramNotifier', 'telegram_notifier']
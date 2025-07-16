"""
Менеджер уведомлений для отправки торговых сигналов
Файл: src/notifications/telegram.py
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import aiohttp
import os
from decimal import Decimal
import json
from sqlalchemy import and_, desc, func

logger = logging.getLogger(__name__)


class NotificationManager:
    """Менеджер для отправки уведомлений о торговых сигналах"""
    
    def __init__(self, db_session_factory, config: Dict = None):
        self.db_session_factory = db_session_factory
        self.config = config or {}
        
        # Telegram конфигурация
        self.telegram_token = self.config.get('telegram_token', os.getenv('TELEGRAM_BOT_TOKEN'))
        self.telegram_chat_id = self.config.get('telegram_chat_id', os.getenv('TELEGRAM_CHAT_ID'))
        
        # Параметры уведомлений
        self.min_signal_strength = self.config.get('min_signal_strength', 0.7)
        self.cooldown_minutes = self.config.get('cooldown_minutes', 60)
        self.check_interval = self.config.get('check_interval', 60)
        
        # Кэш отправленных уведомлений
        self.sent_notifications: Dict[str, datetime] = {}
        
        # Telegram API URL
        self.telegram_api_url = f"https://api.telegram.org/bot{self.telegram_token}"
        
        logger.info("NotificationManager инициализирован")
    
    async def check_and_send_notifications(self):
        """Проверка новых сигналов и отправка уведомлений"""
        try:
            from ..core.signal_models import AggregatedSignal, FinalSignalType
            
            with self.db_session_factory() as db:
                # Получаем последние сильные сигналы
                cutoff_time = datetime.utcnow() - timedelta(minutes=5)
                
                strong_signals = db.query(AggregatedSignal).filter(
                    and_(
                        AggregatedSignal.updated_at > cutoff_time,
                        AggregatedSignal.confidence_score >= self.min_signal_strength,
                        AggregatedSignal.final_signal.in_([
                            FinalSignalType.STRONG_BUY,
                            FinalSignalType.STRONG_SELL
                        ])
                    )
                ).all()
                
                for signal in strong_signals:
                    await self._process_signal(signal)
        
        except Exception as e:
            logger.error(f"Ошибка при проверке сигналов для уведомлений: {e}")
    
    async def _process_signal(self, signal):
        """Обработка отдельного сигнала"""
        try:
            # Проверяем cooldown
            last_sent = self.sent_notifications.get(signal.symbol)
            if last_sent and (datetime.utcnow() - last_sent).total_seconds() < self.cooldown_minutes * 60:
                return
            
            # Формируем сообщение
            emoji = "🟢" if "buy" in signal.final_signal.value.lower() else "🔴"
            signal_type = "ПОКУПКА" if "buy" in signal.final_signal.value.lower() else "ПРОДАЖА"
            
            message = f"{emoji} <b>СИЛЬНЫЙ СИГНАЛ: {signal_type}</b>\n\n"
            message += f"📊 <b>Символ:</b> {signal.symbol}\n"
            message += f"💪 <b>Уверенность:</b> {signal.confidence_score:.1%}\n"
            message += f"📈 <b>Сигналов BUY:</b> {signal.buy_signals_count}\n"
            message += f"📉 <b>Сигналов SELL:</b> {signal.sell_signals_count}\n"
            
            # Добавляем детали из метаданных
            if signal.metadata:
                metadata = json.loads(signal.metadata) if isinstance(signal.metadata, str) else signal.metadata
                if 'strategies' in metadata:
                    message += f"🎯 <b>Стратегии:</b> {', '.join(metadata['strategies'])}\n"
            
            message += f"\n⏰ <i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
            
            # Отправляем сообщение
            await self.send_telegram_message(message, parse_mode='HTML')
            
            # Обновляем кэш
            self.sent_notifications[signal.symbol] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сигнала для {signal.symbol}: {e}")
    
    async def send_telegram_message(self, text: str, parse_mode: str = None) -> bool:
        """Отправка сообщения в Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("Telegram не настроен - токен или chat_id отсутствуют")
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'chat_id': self.telegram_chat_id,
                    'text': text
                }
                
                if parse_mode:
                    data['parse_mode'] = parse_mode
                
                async with session.post(
                    f"{self.telegram_api_url}/sendMessage",
                    json=data
                ) as response:
                    result = await response.json()
                    
                    if result.get('ok'):
                        logger.info("Telegram сообщение успешно отправлено")
                        return True
                    else:
                        logger.error(f"Ошибка отправки Telegram сообщения: {result}")
                        return False
        
        except Exception as e:
            logger.error(f"Ошибка при отправке Telegram сообщения: {e}")
            return False
    
    async def send_daily_summary(self):
        """Отправка ежедневной сводки"""
        try:
            from ..core.signal_models import SignalExtended, AggregatedSignal, SignalType
            
            with self.db_session_factory() as db:
                # Получаем статистику за последние 24 часа
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                
                # Общая статистика
                total_symbols = db.query(func.count(func.distinct(SignalExtended.symbol))).filter(
                    SignalExtended.created_at > cutoff_time
                ).scalar() or 0
                
                total_signals = db.query(func.count(SignalExtended.id)).filter(
                    SignalExtended.created_at > cutoff_time
                ).scalar() or 0
                
                buy_signals = db.query(func.count(SignalExtended.id)).filter(
                    and_(
                        SignalExtended.created_at > cutoff_time,
                        SignalExtended.signal_type == SignalType.BUY
                    )
                ).scalar() or 0
                
                sell_signals = db.query(func.count(SignalExtended.id)).filter(
                    and_(
                        SignalExtended.created_at > cutoff_time,
                        SignalExtended.signal_type == SignalType.SELL
                    )
                ).scalar() or 0
                
                # Количество символов с сильными сигналами
                strong_signal_symbols = db.query(func.count(func.distinct(AggregatedSignal.symbol))).filter(
                    and_(
                        AggregatedSignal.updated_at > cutoff_time,
                        AggregatedSignal.confidence_score >= self.min_signal_strength
                    )
                ).scalar() or 0
                
                # Топ-5 самых активных символов
                top_symbols = db.query(
                    SignalExtended.symbol,
                    func.count(SignalExtended.id).label('signal_count')
                ).filter(
                    SignalExtended.created_at > cutoff_time
                ).group_by(
                    SignalExtended.symbol
                ).order_by(
                    desc('signal_count')
                ).limit(5).all()
                
                # Форматируем сообщение
                message = "<b>📊 Ежедневная сводка торговых сигналов</b>\n\n"
                message += f"<b>За последние 24 часа:</b>\n"
                message += f"• Активных символов: {total_symbols}\n"
                message += f"• Всего сигналов: {total_signals}\n"
                message += f"• Сигналов BUY: {buy_signals}\n"
                message += f"• Сигналов SELL: {sell_signals}\n"
                message += f"• Символов с сильными сигналами: {strong_signal_symbols}\n"
                
                if top_symbols:
                    message += "\n<b>Топ-5 самых активных символов:</b>\n"
                    for i, (symbol, count) in enumerate(top_symbols, 1):
                        message += f"{i}. {symbol} - {count} сигналов\n"
                
                message += f"\n<i>Отчет сгенерирован: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
                
                await self.send_telegram_message(message, parse_mode='HTML')
                
        except Exception as e:
            logger.error(f"Ошибка при отправке ежедневной сводки: {e}")
    
    async def send_error_notification(self, error_message: str, component: str = "System"):
        """Отправка уведомления об ошибке"""
        try:
            message = f"🚨 <b>ОШИБКА В СИСТЕМЕ</b>\n\n"
            message += f"🔧 <b>Компонент:</b> {component}\n"
            message += f"❌ <b>Ошибка:</b> {error_message}\n"
            message += f"⏰ <i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
            
            await self.send_telegram_message(message, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об ошибке: {e}")

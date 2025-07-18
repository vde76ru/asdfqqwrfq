"""
Исполнение торговых сделок
Файл: src/bot/internal/trade_execution.py
"""

import asyncio
import logging
import traceback
import uuid
import inspect
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from src.core.unified_config import UnifiedConfig

logger = logging.getLogger(__name__)

def get_trade_execution(bot_instance):
    """Возвращает объект с методами исполнения сделок"""
    
    class TradeExecution:
        def __init__(self, bot):
            self.bot = bot
            
        async def execute_trade_decision(self, decision):
            """Исполнение торгового решения"""
            return await execute_trade_decision(self.bot, decision)
            
        async def place_order_with_retry(self, order_params):
            """Размещение ордера с повторными попытками"""
            return await place_order_with_retry(self.bot, order_params)
    
    return TradeExecution(bot_instance)

async def _execute_best_trades(bot_instance, opportunities: list) -> int:
    """Исполнение лучших торговых возможностей с ИСПРАВЛЕННЫМ вызовом calculate_position_size"""
    try:
        trades_executed = 0
        
        # Проверяем есть ли возможности
        if not opportunities:
            logger.debug("📊 Нет торговых возможностей для исполнения")
            return 0
        
        # Фильтруем и ранжируем возможности
        logger.info(f"📊 Найдено торговых возможностей: {len(opportunities)}")
        
        # Проверяем лимиты
        max_trades = min(
            getattr(bot_instance.config, 'MAX_DAILY_TRADES', 50) - getattr(bot_instance, 'trades_today', 0),
            getattr(bot_instance.config, 'MAX_POSITIONS', 15) - len(getattr(bot_instance, 'positions', {})),
            3  # Максимум 3 сделки за цикл
        )
        
        if max_trades <= 0:
            logger.warning("⚠️ Достигнут лимит сделок или позиций")
            return 0
        
        # Сортируем по уверенности
        sorted_opportunities = sorted(
            opportunities,
            key=lambda x: x.get('confidence', 0),
            reverse=True
        )
        
        # Исполняем лучшие сделки
        for opportunity in sorted_opportunities[:max_trades]:
            symbol = opportunity['symbol']
            signal = opportunity['signal']
            confidence = opportunity.get('confidence', 0.6)
            price = opportunity['price']
            
            # Проверяем минимальную уверенность
            min_confidence = getattr(bot_instance.config, 'MIN_CONFIDENCE', 0.6)
            if confidence < min_confidence:
                logger.debug(f"⏭️ Пропускаем {symbol}: низкая уверенность {confidence:.2f} < {min_confidence}")
                continue
            
            # ИСПРАВЛЕНО: Проверяем, является ли метод асинхронным
            if hasattr(bot_instance._calculate_position_size, '__call__'):
                # Проверяем, является ли метод корутиной
                if inspect.iscoroutinefunction(bot_instance._calculate_position_size):
                    position_size = await bot_instance._calculate_position_size(symbol, price)
                else:
                    # Метод синхронный - вызываем без await
                    position_size = bot_instance._calculate_position_size(symbol, price)
            else:
                # Если метода нет, используем базовый расчет
                logger.warning("⚠️ Метод _calculate_position_size не найден, используем базовый расчет")
                # Базовый расчет размера позиции
                balance = getattr(bot_instance, 'available_balance', 10000)
                risk_amount = balance * (getattr(bot_instance.config, 'RISK_PER_TRADE_PERCENT', 1.5) / 100)
                position_size = risk_amount / price
                
            if position_size <= 0:
                logger.warning(f"⚠️ Нулевой размер позиции для {symbol}")
                continue
            
            # Округляем размер позиции до разумных значений
            # Для Bybit минимальный размер обычно 0.001
            min_size = 0.001
            if position_size < min_size:
                logger.warning(f"⚠️ Размер позиции {position_size} меньше минимального {min_size}")
                position_size = min_size
            
            # Округляем до 3 знаков после запятой
            position_size = round(position_size, 3)
            
            # Подготавливаем данные для сделки
            trade_data = {
                'confidence': confidence,
                'stop_loss': opportunity.get('stop_loss'),
                'take_profit': opportunity.get('take_profit'),
                'strategy': opportunity.get('strategy', 'unknown'),
                'indicators': opportunity.get('indicators', {}),
                'market_conditions': opportunity.get('market_conditions', {}),
                'risk_reward_ratio': opportunity.get('risk_reward_ratio')
            }
            
            # Рассчитываем risk/reward если не предоставлен
            if not trade_data.get('risk_reward_ratio') and trade_data.get('stop_loss') and trade_data.get('take_profit'):
                if signal.upper() == 'BUY':
                    risk = price - trade_data['stop_loss']
                    reward = trade_data['take_profit'] - price
                else:  # SELL
                    risk = trade_data['stop_loss'] - price
                    reward = price - trade_data['take_profit']
                
                if risk > 0:
                    trade_data['risk_reward_ratio'] = reward / risk
            
            # Логируем подготовку сделки
            logger.info("🎯 ПОДГОТОВКА СДЕЛКИ:")
            logger.info(f"📊 Символ: {symbol}")
            logger.info(f"📈 Сигнал: {signal}")
            logger.info(f"💵 Цена: ${price:.4f}")
            logger.info(f"📏 Размер: {position_size}")
            if trade_data.get('stop_loss'):
                logger.info(f"🛑 Стоп-лосс: ${trade_data['stop_loss']:.4f}")
            if trade_data.get('take_profit'):
                logger.info(f"🎯 Тейк-профит: ${trade_data['take_profit']:.4f}")
            if trade_data.get('risk_reward_ratio'):
                logger.info(f"⚖️ Risk/Reward: 1:{trade_data['risk_reward_ratio']:.2f}")
            logger.info(f"📊 Уверенность: {confidence:.2f}")
            logger.info(f"🔧 Стратегия: {trade_data.get('strategy')}")
            
            # Проверяем режим торговли
            paper_trading = bot_instance.config.PAPER_TRADING
            testnet = bot_instance.config.TESTNET
            live_trading = bot_instance.config.LIVE_TRADING
            
            # Логируем режим
            logger.debug(f"🔍 Режимы: PAPER_TRADING={paper_trading}, TESTNET={testnet}, LIVE_TRADING={live_trading}")
            
             # Определяем режим исполнения (приоритет — paper → live → testnet → fallback)
            if paper_trading:
                logger.info("📝 РЕЖИМ PAPER TRADING - симуляция сделки")
                success = await _simulate_trade(bot_instance, symbol, signal, position_size, price, trade_data)
            elif live_trading:
                if testnet:
                    logger.info("🧪 РЕЖИМ TESTNET - реальная сделка на тестовой бирже")
                else:
                    logger.info("💸 РЕЖИМ LIVE TRADING - реальная сделка на основной бирже")
                success = await _execute_real_order(bot_instance, symbol, signal, position_size, price, trade_data)
            else:
                logger.warning("⚠️ Не указаны LIVE_TRADING или PAPER_TRADING — переходим в симуляцию")
                success = await _simulate_trade(bot_instance, symbol, signal, position_size, price, trade_data)
                
            if success:
                trades_executed += 1
                bot_instance.trades_today = getattr(bot_instance, 'trades_today', 0) + 1
                logger.info(f"✅ Сделка #{trades_executed} выполнена успешно")
                
                # Обновляем позиции
                if not hasattr(bot_instance, 'positions'):
                    bot_instance.positions = {}
                    
                bot_instance.positions[symbol] = {
                    'side': signal,
                    'size': position_size,
                    'entry_price': price,
                    'stop_loss': trade_data.get('stop_loss'),
                    'take_profit': trade_data.get('take_profit'),
                    'strategy': trade_data.get('strategy'),
                    'confidence': confidence,
                    'timestamp': datetime.utcnow()
                }
                
                # Отправляем уведомление
                if hasattr(bot_instance, 'notifier') and bot_instance.notifier:
                    try:
                        await bot_instance.notifier.send_trade_notification(
                            symbol=symbol,
                            side=signal,
                            price=price,
                            amount=position_size,
                            strategy=trade_data.get('strategy'),
                            confidence=confidence
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка отправки уведомления: {e}")
            else:
                logger.error(f"❌ Не удалось выполнить сделку для {symbol}")
                
                # Добавляем символ в черный список на некоторое время
                if hasattr(bot_instance, 'trade_cooldown'):
                    bot_instance.trade_cooldown[symbol] = datetime.utcnow() + timedelta(minutes=30)
                    logger.info(f"⏰ {symbol} добавлен в cooldown на 30 минут")
        
        # Обновляем статистику
        if trades_executed > 0:
            logger.info(f"📊 Итого выполнено сделок в этом цикле: {trades_executed}")
            logger.info(f"📊 Всего сделок за сегодня: {bot_instance.trades_today}")
            logger.info(f"📊 Открытых позиций: {len(bot_instance.positions)}")
        
        return trades_executed
        
    except Exception as e:
        logger.error(f"❌ Ошибка исполнения сделок: {e}")
        import traceback
        traceback.print_exc()
        return 0

async def _execute_trade(bot_instance, opportunity: Dict[str, Any]) -> bool:
    """
    Единый метод для выполнения сделки. 
    Определяет, симулировать сделку (Paper Trading) или выполнить реально.
    """
    symbol = opportunity['symbol']
    signal = opportunity['signal']
    price = opportunity['price']

    logger.info(f"🎯 ИСПОЛНЕНИЕ СДЕЛКИ для {symbol}...")

    try:
        # 1. Расчет размера позиции
        # Этот метод должен быть единственным источником для расчета размера
        position_size = _calculate_position_size(bot_instance, symbol, price)
        if position_size <= 0:
            logger.warning(f"⚠️ Нулевой или некорректный размер позиции ({position_size}) для {symbol}. Сделка отменена.")
            return False

        # 2. Определяем режим торговли из unified_config
        is_paper_trading = getattr(bot_instance.config, 'PAPER_TRADING', True)
        is_live_trading = getattr(bot_instance.config, 'LIVE_TRADING', False)

        trade_data = {
            'confidence': opportunity.get('confidence', 0.6),
            'stop_loss': opportunity.get('stop_loss'),
            'take_profit': opportunity.get('take_profit'),
            'strategy': opportunity.get('strategy', 'unknown'),
            'indicators': opportunity.get('indicators', {})
        }

        success = False
        if is_paper_trading:
            logger.info(f"📝 РЕЖИМ PAPER TRADING: Симуляция сделки для {symbol}")
            success = await _simulate_trade(bot_instance, symbol, signal, position_size, price, trade_data)
        elif is_live_trading:
            logger.info(f"💸 РЕЖИМ LIVE TRADING: Выполнение реальной сделки для {symbol}")
            # _execute_real_order_internal будет содержать логику реального ордера
            success = await _execute_real_order_internal(bot_instance, symbol, signal, position_size, price, trade_data)
        else:
            logger.warning(f"⚠️ Не определен режим торговли (PAPER_TRADING или LIVE_TRADING). Сделка не выполнена.")
            return False

        if success:
            logger.info(f"✅ Сделка для {symbol} ({signal}) успешно выполнена.")
            await _save_trade_to_db(bot_instance, symbol, trade_data, success=True)
            await _send_trade_notification(bot_instance, symbol, signal, position_size, price)
        else:
            logger.error(f"❌ Не удалось выполнить сделку для {symbol}.")

        return success

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при выполнении сделки для {symbol}: {e}")
        logger.error(traceback.format_exc())
        return False

async def _execute_real_order_internal(bot_instance, symbol: str, signal: str, position_size: float, 
                                     price: float, trade_data: Dict[str, Any]) -> bool:
    """
    Внутренний метод для отправки РЕАЛЬНОГО ордера на биржу.
    Используем enhanced_exchange_client как приоритетный.
    """
    client = bot_instance.enhanced_exchange_client or bot_instance.exchange_client
    if not client:
        logger.error(f"❌ Нет доступного клиента биржи для выполнения реальной сделки.")
        return False

    try:
        # Используем самые продвинутые методы, если они есть
        if hasattr(client, 'place_order_from_signal'):
             # Создаем унифицированный сигнал для продвинутого клиента
            from ..common.types import UnifiedTradingSignal, SignalAction
            unified_signal = UnifiedTradingSignal(
                symbol=symbol,
                action=SignalAction(signal.upper()),
                price=price,
                stop_loss=trade_data.get('stop_loss'),
                take_profit=trade_data.get('take_profit'),
                strategy=trade_data.get('strategy', 'unknown'),
                confidence=trade_data.get('confidence', 0.6)
            )
            result = await client.place_order_from_signal(signal=unified_signal, amount=position_size)
        else: # Fallback для простого клиента
             result = await client.place_order(
                symbol=symbol,
                side=signal.lower(),
                amount=position_size,
                order_type='market',
                params={
                    'stopLoss': trade_data.get('stop_loss'),
                    'takeProfit': trade_data.get('take_profit'),
                }
            )

        # Унифицированная проверка результата
        if result and (result.get('success') or (result.get('retCode') == 0 and result.get('result'))):
            order_id = result.get('order_id') or result.get('result', {}).get('orderId', 'N/A')
            logger.info(f"✅ Ордер для {symbol} успешно размещен. ID: {order_id}")
            return True
        else:
            error_msg = result.get('error') or result.get('retMsg', 'Неизвестная ошибка биржи')
            logger.error(f"❌ Ошибка размещения ордера для {symbol}: {error_msg}")
            return False

    except Exception as e:
        logger.error(f"❌ Исключение при размещении реального ордера для {symbol}: {e}")
        return False

async def _simulate_trade(bot_instance, symbol: str, signal: str, position_size: float,
                         price: float, trade_data: Dict[str, Any]) -> bool:
    """
    Симуляция торговой операции для режима Paper Trading
    
    Args:
        symbol: Торговая пара
        signal: Тип сигнала (BUY/SELL)
        position_size: Размер позиции
        price: Цена входа
        trade_data: Дополнительные данные сделки
        
    Returns:
        bool: True если симуляция выполнена успешно
    """
    try:
        logger.info("📝 СИМУЛЯЦИЯ СДЕЛКИ (Paper Trading)")
        logger.info(f"📊 Символ: {symbol}")
        logger.info(f"📈 Направление: {signal}")
        logger.info(f"💵 Цена входа: ${price:.4f}")
        logger.info(f"📏 Размер позиции: {position_size}")
        
        # Генерируем уникальный ID для симулированного ордера
        order_id = f"PAPER_{uuid.uuid4().hex[:8]}"
        
        # Рассчитываем стоимость позиции
        position_value = position_size * price
        
        # Проверяем достаточность баланса
        available_balance = getattr(bot_instance, 'paper_balance', UnifiedConfig.INITIAL_CAPITAL)
        if position_value > available_balance:
            logger.error(f"❌ Недостаточно средств: нужно ${position_value:.2f}, доступно ${available_balance:.2f}")
            return False
        
        # Создаем запись о симулированной сделке
        simulated_trade = {
            'order_id': order_id,
            'symbol': symbol,
            'side': signal,
            'size': position_size,
            'entry_price': price,
            'position_value': position_value,
            'stop_loss': trade_data.get('stop_loss'),
            'take_profit': trade_data.get('take_profit'),
            'strategy': trade_data.get('strategy', 'unknown'),
            'confidence': trade_data.get('confidence', 0.6),
            'timestamp': datetime.utcnow(),
            'status': 'FILLED',
            'pnl': 0.0,
            'pnl_percent': 0.0,
            'commission': position_value * 0.001  # 0.1% комиссия
        }
        
        # Обновляем paper баланс
        bot_instance.paper_balance = available_balance - position_value - simulated_trade['commission']
        
        # Сохраняем в paper позиции
        if not hasattr(bot_instance, 'paper_positions'):
            bot_instance.paper_positions = {}
        
        bot_instance.paper_positions[symbol] = simulated_trade
        
        # Сохраняем в историю paper сделок
        if not hasattr(bot_instance, 'paper_trades_history'):
            bot_instance.paper_trades_history = []
        
        bot_instance.paper_trades_history.append(simulated_trade.copy())
        
        # Логируем детали сделки
        logger.info(f"✅ Симулированная сделка выполнена!")
        logger.info(f"🔖 Order ID: {order_id}")
        logger.info(f"💰 Стоимость позиции: ${position_value:.2f}")
        logger.info(f"💸 Комиссия: ${simulated_trade['commission']:.2f}")
        logger.info(f"💵 Остаток баланса: ${bot_instance.paper_balance:.2f}")
        
        if trade_data.get('stop_loss'):
            potential_loss = abs(price - trade_data['stop_loss']) * position_size
            logger.info(f"🛑 Stop Loss: ${trade_data['stop_loss']:.4f} (риск: ${potential_loss:.2f})")
            
        if trade_data.get('take_profit'):
            potential_profit = abs(trade_data['take_profit'] - price) * position_size
            logger.info(f"🎯 Take Profit: ${trade_data['take_profit']:.4f} (потенциал: ${potential_profit:.2f})")
        
        if trade_data.get('risk_reward_ratio'):
            logger.info(f"⚖️ Risk/Reward: 1:{trade_data['risk_reward_ratio']:.2f}")
        
        # Запускаем мониторинг симулированной позиции
        if hasattr(bot_instance, '_monitor_paper_position'):
            asyncio.create_task(_monitor_paper_position(bot_instance, symbol, simulated_trade))
        
        # Обновляем статистику
        if not hasattr(bot_instance, 'paper_stats'):
            bot_instance.paper_stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_pnl': 0.0,
                'total_commission': 0.0,
                'max_drawdown': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0,
                'average_win': 0.0,
                'average_loss': 0.0,
                'win_rate': 0.0,
                'profit_factor': 0.0
            }
        
        bot_instance.paper_stats['total_trades'] += 1
        bot_instance.paper_stats['total_commission'] += simulated_trade['commission']
        
        # Отправляем уведомление о симулированной сделке
        if hasattr(bot_instance, 'notifier') and bot_instance.notifier:
            try:
                message = f"📝 PAPER TRADE EXECUTED\n"
                message += f"Symbol: {symbol}\n"
                message += f"Side: {signal}\n"
                message += f"Price: ${price:.4f}\n"
                message += f"Size: {position_size}\n"
                message += f"Value: ${position_value:.2f}\n"
                message += f"Strategy: {trade_data.get('strategy', 'unknown')}\n"
                message += f"Balance: ${bot_instance.paper_balance:.2f}"
                
                await bot_instance.notifier.send_message(message)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отправки уведомления: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка симуляции сделки: {e}")
        import traceback
        traceback.print_exc()
        return False

async def _monitor_paper_position(bot_instance, symbol: str, position: Dict[str, Any]):
    """
    Мониторинг симулированной позиции для обновления P&L
    
    Args:
        symbol: Торговая пара
        position: Данные позиции
    """
    try:
        while symbol in bot_instance.paper_positions:
            await asyncio.sleep(10)  # Проверяем каждые 10 секунд
            
            # Получаем текущую цену
            current_price = await _get_current_price(bot_instance, symbol)
            if not current_price:
                continue
            
            # Рассчитываем P&L
            entry_price = position['entry_price']
            size = position['size']
            side = position['side']
            
            if side.upper() == 'BUY':
                pnl = (current_price - entry_price) * size
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
            else:  # SELL
                pnl = (entry_price - current_price) * size
                pnl_percent = ((entry_price - current_price) / entry_price) * 100
            
            # Обновляем позицию
            bot_instance.paper_positions[symbol]['current_price'] = current_price
            bot_instance.paper_positions[symbol]['pnl'] = pnl
            bot_instance.paper_positions[symbol]['pnl_percent'] = pnl_percent
            
            # Проверяем стоп-лосс
            if position.get('stop_loss'):
                if (side.upper() == 'BUY' and current_price <= position['stop_loss']) or \
                   (side.upper() == 'SELL' and current_price >= position['stop_loss']):
                    logger.warning(f"🛑 STOP LOSS сработал для {symbol} @ ${current_price:.4f}")
                    await _close_paper_position(bot_instance, symbol, current_price, 'STOP_LOSS')
                    break
            
            # Проверяем тейк-профит
            if position.get('take_profit'):
                if (side.upper() == 'BUY' and current_price >= position['take_profit']) or \
                   (side.upper() == 'SELL' and current_price <= position['take_profit']):
                    logger.info(f"🎯 TAKE PROFIT сработал для {symbol} @ ${current_price:.4f}")
                    await _close_paper_position(bot_instance, symbol, current_price, 'TAKE_PROFIT')
                    break
            
    except Exception as e:
        logger.error(f"❌ Ошибка мониторинга paper позиции: {e}")

async def _close_paper_position(bot_instance, symbol: str, exit_price: float, reason: str):
    """
    Закрытие симулированной позиции
    
    Args:
        symbol: Торговая пара
        exit_price: Цена выхода
        reason: Причина закрытия
    """
    try:
        if symbol not in bot_instance.paper_positions:
            return
        
        position = bot_instance.paper_positions[symbol]
        
        # Финальный расчет P&L
        entry_price = position['entry_price']
        size = position['size']
        side = position['side']
        
        if side.upper() == 'BUY':
            pnl = (exit_price - entry_price) * size
        else:  # SELL
            pnl = (entry_price - exit_price) * size
        
        # Комиссия за закрытие
        exit_commission = size * exit_price * 0.001
        total_commission = position['commission'] + exit_commission
        net_pnl = pnl - exit_commission
        
        # Обновляем баланс
        bot_instance.paper_balance += position['position_value'] + net_pnl
        
        # Обновляем статистику
        bot_instance.paper_stats['total_pnl'] += net_pnl
        
        if net_pnl > 0:
            bot_instance.paper_stats['winning_trades'] += 1
            bot_instance.paper_stats['best_trade'] = max(bot_instance.paper_stats['best_trade'], net_pnl)
        else:
            bot_instance.paper_stats['losing_trades'] += 1
            bot_instance.paper_stats['worst_trade'] = min(bot_instance.paper_stats['worst_trade'], net_pnl)
        
        # Рассчитываем win rate
        total = bot_instance.paper_stats['winning_trades'] + bot_instance.paper_stats['losing_trades']
        if total > 0:
            bot_instance.paper_stats['win_rate'] = (bot_instance.paper_stats['winning_trades'] / total) * 100
        
        # Логируем закрытие
        logger.info(f"📝 PAPER POSITION CLOSED: {symbol}")
        logger.info(f"📤 Причина: {reason}")
        logger.info(f"💵 Цена выхода: ${exit_price:.4f}")
        logger.info(f"💰 P&L: ${net_pnl:.2f} ({(net_pnl/position['position_value'])*100:.2f}%)")
        logger.info(f"💵 Новый баланс: ${bot_instance.paper_balance:.2f}")
        logger.info(f"📊 Win Rate: {bot_instance.paper_stats['win_rate']:.1f}%")
        
        # Удаляем позицию
        del bot_instance.paper_positions[symbol]
        
    except Exception as e:
        logger.error(f"❌ Ошибка закрытия paper позиции: {e}")

async def _get_current_price(bot_instance, symbol: str) -> Optional[float]:
    """
    Получает текущую цену для символа
    
    Args:
        symbol: Торговая пара
        
    Returns:
        Optional[float]: Текущая цена или None
    """
    try:
        # Способ 1: Через enhanced exchange client с кешем
        if hasattr(bot_instance, 'enhanced_exchange_client') and bot_instance.enhanced_exchange_client:
            # Проверяем кеш цен если есть
            if hasattr(bot_instance.enhanced_exchange_client, 'price_cache'):
                cached_price = bot_instance.enhanced_exchange_client.price_cache.get(symbol)
                if cached_price and cached_price.get('timestamp'):
                    # Проверяем актуальность (не старше 5 секунд)
                    age = (datetime.utcnow() - cached_price['timestamp']).total_seconds()
                    if age < 5:
                        return cached_price['price']
            
            # Пробуем через V5 API
            if hasattr(bot_instance.enhanced_exchange_client, 'v5_client'):
                try:
                    ticker = await bot_instance.enhanced_exchange_client.v5_client.get_ticker(
                        category='linear',
                        symbol=symbol
                    )
                    if ticker and ticker.get('retCode') == 0:
                        result = ticker.get('result', {})
                        if result.get('list'):
                            return float(result['list'][0].get('lastPrice', 0))
                except Exception as e:
                    logger.debug(f"V5 ticker error: {e}")
        
        # Способ 2: Через базовый exchange client
        if hasattr(bot_instance, 'exchange_client') and bot_instance.exchange_client:
            try:
                # Метод fetch_ticker для CCXT
                if hasattr(bot_instance.exchange_client, 'fetch_ticker'):
                    ticker = await bot_instance.exchange_client.fetch_ticker(symbol)
                    if ticker and 'last' in ticker:
                        return float(ticker['last'])
                # Альтернативный метод get_ticker
                elif hasattr(bot_instance.exchange_client, 'get_ticker'):
                    ticker = await bot_instance.exchange_client.get_ticker(symbol)
                    if ticker:
                        return float(ticker.get('last', 0))
            except Exception as e:
                logger.debug(f"Exchange client ticker error: {e}")
        
        # Способ 3: Через WebSocket данные если есть
        if hasattr(bot_instance, 'websocket_manager') and bot_instance.websocket_manager:
            ws_data = getattr(bot_instance.websocket_manager, 'market_data', {})
            if symbol in ws_data and 'price' in ws_data[symbol]:
                return float(ws_data[symbol]['price'])
        
        # Способ 4: Из последних свечей
        if hasattr(bot_instance, 'data_collector') and bot_instance.data_collector:
            try:
                # Получаем последнюю свечу
                candles = await bot_instance.data_collector.get_latest_candles(symbol, limit=1)
                if candles and len(candles) > 0:
                    return float(candles[-1]['close'])
            except Exception as e:
                logger.debug(f"Data collector error: {e}")
        
        # Если ничего не сработало, пробуем простой API запрос
        logger.warning(f"⚠️ Не удалось получить цену для {symbol} стандартными методами")
        
        # Fallback: прямой запрос к Bybit API
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"https://api-testnet.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
                if not getattr(bot_instance.config, 'TESTNET', True):
                    url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('retCode') == 0:
                            result = data.get('result', {})
                            if result.get('list'):
                                return float(result['list'][0].get('lastPrice', 0))
        except Exception as e:
            logger.error(f"❌ Fallback API error: {e}")
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения текущей цены для {symbol}: {e}")
        return None

def _validate_trade_params(bot_instance, symbol: str, signal: str, 
                          position_size: float, price: float) -> bool:
    """
    Валидация параметров сделки
    
    Args:
        symbol: Торговая пара
        signal: Тип сигнала
        position_size: Размер позиции
        price: Цена
        
    Returns:
        bool: True если все параметры валидны
    """
    # Проверка символа
    if not symbol or not isinstance(symbol, str):
        logger.error(f"❌ Некорректный символ: {symbol}")
        return False
    
    if not symbol.endswith('USDT'):
        logger.warning(f"⚠️ Необычный символ (не USDT пара): {symbol}")
    
    # Проверка сигнала
    if signal.upper() not in ['BUY', 'SELL']:
        logger.error(f"❌ Некорректный сигнал: {signal}")
        return False
    
    # Проверка размера позиции
    if not isinstance(position_size, (int, float)) or position_size <= 0:
        logger.error(f"❌ Некорректный размер позиции: {position_size}")
        return False
    
    # Проверка цены
    if not isinstance(price, (int, float)) or price <= 0:
        logger.error(f"❌ Некорректная цена: {price}")
        return False
    
    # Дополнительные проверки
    min_position_size = 0.001  # Минимальный размер для BTC
    if position_size < min_position_size:
        logger.warning(f"⚠️ Размер позиции меньше минимального: {position_size} < {min_position_size}")
    
    logger.info(f"✅ Параметры сделки валидны: {symbol} {signal} size={position_size} price={price}")
    return True

def _validate_stop_loss(bot_instance, signal: str, price: float, stop_loss: Optional[float]) -> Optional[float]:
    """Валидация и коррекция stop loss"""
    if not stop_loss:
        return None
        
    if signal.upper() == 'BUY':
        # Для покупки SL должен быть ниже цены
        if stop_loss >= price:
            corrected = price * 0.97  # 3% ниже
            logger.warning(f"⚠️ SL скорректирован: {stop_loss} -> {corrected}")
            return corrected
    else:
        # Для продажи SL должен быть выше цены
        if stop_loss <= price:
            corrected = price * 1.03  # 3% выше
            logger.warning(f"⚠️ SL скорректирован: {stop_loss} -> {corrected}")
            return corrected
    
    return stop_loss

def _validate_take_profit(bot_instance, signal: str, price: float, take_profit: Optional[float]) -> Optional[float]:
    """Валидация и коррекция take profit"""
    if not take_profit:
        return None
        
    if signal.upper() == 'BUY':
        # Для покупки TP должен быть выше цены
        if take_profit <= price:
            corrected = price * 1.06  # 6% выше
            logger.warning(f"⚠️ TP скорректирован: {take_profit} -> {corrected}")
            return corrected
    else:
        # Для продажи TP должен быть ниже цены
        if take_profit >= price:
            corrected = price * 0.94  # 6% ниже
            logger.warning(f"⚠️ TP скорректирован: {take_profit} -> {corrected}")
            return corrected
    
    return take_profit

def _save_order_info(bot_instance, order_result: Dict[str, Any], signal):
    """Сохранение информации об ордере"""
    if not hasattr(bot_instance, 'active_orders'):
        bot_instance.active_orders = {}
    
    order_id = order_result.get('order_id') or order_result.get('id')
    if order_id:
        bot_instance.active_orders[order_id] = {
            'symbol': signal.symbol,
            'side': signal.side_str,
            'action': signal.action_str,
            'size': order_result.get('amount'),
            'price': signal.price,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'timestamp': datetime.utcnow(),
            'strategy': signal.strategy,
            'confidence': signal.confidence
        }

async def _set_position_sl_tp(bot_instance, symbol: str, stop_loss: float = None, take_profit: float = None):
    """Установка SL/TP для позиции"""
    try:
        logger.info(f"📊 Установка SL/TP для {symbol}: SL={stop_loss}, TP={take_profit}")
        
        # Попытка установить через enhanced client
        if hasattr(bot_instance, 'enhanced_exchange_client') and bot_instance.enhanced_exchange_client:
            if hasattr(bot_instance.enhanced_exchange_client, 'set_position_sl_tp'):
                result = await bot_instance.enhanced_exchange_client.set_position_sl_tp(
                    symbol=symbol,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                )
                if result:
                    logger.info(f"✅ SL/TP установлены для {symbol}")
                    return True
        
        # Здесь можно добавить другие способы установки SL/TP
        logger.warning(f"⚠️ Не удалось установить SL/TP для {symbol}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка установки SL/TP: {e}")

async def _save_trade_to_db(bot_instance, symbol: str, trade_data: dict, success: bool):
    """Сохранение информации о сделке в БД"""
    try:
        # Здесь будет код сохранения в БД
        logger.debug(f"💾 Сохранение сделки {symbol} в БД (success={success})")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения в БД: {e}")

async def _send_trade_notification(bot_instance, symbol: str, signal: str, size: float, price: float):
    """Отправка уведомления о сделке"""
    try:
        if hasattr(bot_instance, 'notifier') and bot_instance.notifier:
            message = f"🎯 Выполнена сделка:\n{symbol} {signal}\nРазмер: {size}\nЦена: ${price:.4f}"
            await bot_instance.notifier.send_message(message)
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления: {e}")

def _calculate_position_size(bot_instance, symbol: str, price: float) -> float:
    """
    Рассчитывает размер позиции на основе риск-менеджмента
    
    Args:
        symbol: Торговая пара
        price: Текущая цена актива
        
    Returns:
        float: Размер позиции в базовой валюте (например, BTC для BTCUSDT)
    """
    try:
        # Получаем доступный баланс
        available_balance = getattr(bot_instance, 'available_balance', 10000)
        
        # Если есть enhanced_exchange_client, получаем актуальный баланс
        if hasattr(bot_instance, 'enhanced_exchange_client') and bot_instance.enhanced_exchange_client:
            try:
                # ИСПРАВЛЕНО: Правильная работа с балансом
                if hasattr(bot_instance.enhanced_exchange_client, 'get_balance'):
                    balance_info = bot_instance.enhanced_exchange_client.get_balance()
                    # Проверяем, является ли результат корутиной
                    import inspect
                    if inspect.iscoroutine(balance_info):
                        # Если это корутина, используем стандартный баланс
                        logger.debug("get_balance возвращает корутину, используем стандартный баланс")
                    elif balance_info and isinstance(balance_info, dict) and 'USDT' in balance_info:
                        available_balance = float(balance_info['USDT'].get('free', available_balance))
                        logger.debug(f"Получен баланс из enhanced_exchange_client: ${available_balance:.2f}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось получить баланс: {e}")
        
        # Получаем параметры риск-менеджмента
        risk_per_trade = getattr(bot_instance.config, 'RISK_PER_TRADE_PERCENT', 1.5) / 100
        max_position_percent = getattr(bot_instance.config, 'MAX_POSITION_SIZE_PERCENT', 10) / 100
        
        # Рассчитываем максимальный риск в долларах
        risk_amount = available_balance * risk_per_trade
        
        # Рассчитываем максимальный размер позиции в долларах
        max_position_value = available_balance * max_position_percent
        
        # Получаем процент стоп-лосса
        stop_loss_percent = getattr(bot_instance.config, 'STOP_LOSS_PERCENT', 3.0) / 100
        
        # Рассчитываем размер позиции на основе риска
        # Размер = Риск / (Цена * Процент_стоп_лосса)
        position_size_by_risk = risk_amount / (price * stop_loss_percent)
        
        # Рассчитываем размер позиции на основе максимального процента
        position_size_by_max = max_position_value / price
        
        # Берем меньший размер для безопасности
        position_size = min(position_size_by_risk, position_size_by_max)
        
        # Проверяем минимальный размер для Bybit
        min_order_size = _get_min_order_size(bot_instance, symbol)
        if position_size < min_order_size:
            logger.warning(f"⚠️ Размер позиции {position_size:.4f} меньше минимального {min_order_size}")
            return 0.0
        
        # Проверяем количество открытых позиций
        current_positions = len(getattr(bot_instance, 'positions', {}))
        max_positions = getattr(bot_instance.config, 'MAX_POSITIONS', 15)
        
        if current_positions >= max_positions:
            logger.warning(f"⚠️ Достигнут лимит позиций: {current_positions}/{max_positions}")
            return 0.0
        
        # Корректируем размер с учетом количества позиций
        # Чем больше позиций, тем меньше размер новой
        position_adjustment = 1.0 - (current_positions / max_positions * 0.5)
        position_size *= position_adjustment
        
        # Округляем до нужной точности
        position_size = _round_to_precision(bot_instance, position_size, symbol)
        
        logger.debug(f"💰 Расчет позиции для {symbol}:")
        logger.debug(f"   Баланс: ${available_balance:.2f}")
        logger.debug(f"   Риск на сделку: ${risk_amount:.2f} ({risk_per_trade*100:.1f}%)")
        logger.debug(f"   Размер по риску: {position_size_by_risk:.4f}")
        logger.debug(f"   Размер по максимуму: {position_size_by_max:.4f}")
        logger.debug(f"   Итоговый размер: {position_size:.4f}")
        
        return position_size
        
    except Exception as e:
        logger.error(f"❌ Ошибка расчета размера позиции: {e}")
        import traceback
        traceback.print_exc()
        return 0.0

def _get_min_order_size(bot_instance, symbol: str) -> float:
    """
    Получает минимальный размер ордера для символа
    
    Args:
        symbol: Торговая пара
        
    Returns:
        float: Минимальный размер ордера
    """
    # Стандартные минимальные размеры для популярных пар
    min_sizes = {
        'BTCUSDT': 0.001,
        'ETHUSDT': 0.01,
        'BNBUSDT': 0.01,
        'SOLUSDT': 0.1,
        'ADAUSDT': 10,
        'DOTUSDT': 1,
        'MATICUSDT': 10,
        'AVAXUSDT': 0.1,
        'LINKUSDT': 0.1,
        'ATOMUSDT': 0.1
    }
    
    # Пытаемся получить из биржи
    if hasattr(bot_instance, 'exchange_client') and bot_instance.exchange_client:
        try:
            markets = bot_instance.exchange_client.exchange.markets
            if markets and symbol in markets:
                market = markets[symbol]
                if 'limits' in market and 'amount' in market['limits']:
                    return market['limits']['amount']['min']
        except Exception as e:
            logger.debug(f"Не удалось получить лимиты с биржи: {e}")
    
    # Возвращаем стандартное значение
    return min_sizes.get(symbol, 0.001)

def _round_to_precision(bot_instance, value: float, symbol: str) -> float:
    """
    Округляет значение до нужной точности для символа
    
    Args:
        value: Значение для округления
        symbol: Торговая пара
        
    Returns:
        float: Округленное значение
    """
    # Стандартная точность для популярных пар
    precision = {
        'BTCUSDT': 3,
        'ETHUSDT': 3,
        'BNBUSDT': 2,
        'SOLUSDT': 1,
        'ADAUSDT': 0,
        'DOTUSDT': 1,
        'MATICUSDT': 0,
        'AVAXUSDT': 1,
        'LINKUSDT': 1,
        'ATOMUSDT': 1
    }
    
    # Пытаемся получить из биржи
    if hasattr(bot_instance, 'exchange_client') and bot_instance.exchange_client:
        try:
            markets = bot_instance.exchange_client.exchange.markets
            if markets and symbol in markets:
                market = markets[symbol]
                if 'precision' in market and 'amount' in market['precision']:
                    decimals = market['precision']['amount']
                    return round(value, decimals)
        except Exception as e:
            logger.debug(f"Не удалось получить точность с биржи: {e}")
    
    # Используем стандартную точность
    decimals = precision.get(symbol, 3)
    return round(value, decimals)

def _calculate_stop_loss(bot_instance, entry_price: float, side: str) -> float:
    """Расчет стоп-лосса"""
    try:
        sl_percent = getattr(bot_instance.config, 'STOP_LOSS_PERCENT', 2.0) / 100
        
        if side == 'BUY':
            return entry_price * (1 - sl_percent)
        else:  # SELL
            return entry_price * (1 + sl_percent)
            
    except Exception as e:
        logger.error(f"❌ Ошибка расчета стоп-лосса: {e}")
        return entry_price * 0.98 if side == 'BUY' else entry_price * 1.02

def _calculate_take_profit(bot_instance, entry_price: float, side: str) -> float:
    """Расчет тейк-профита"""
    try:
        tp_percent = getattr(bot_instance.config, 'TAKE_PROFIT_PERCENT', 4.0) / 100
        
        if side == 'BUY':
            return entry_price * (1 + tp_percent)
        else:  # SELL
            return entry_price * (1 - tp_percent)
            
    except Exception as e:
        logger.error(f"❌ Ошибка расчета тейк-профита: {e}")
        return entry_price * 1.04 if side == 'BUY' else entry_price * 0.96
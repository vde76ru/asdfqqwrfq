"""
Объединенный API для всех функций веб-интерфейса
Файл: src/web/unified_api.py
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import jsonify, request
from flask_login import login_required
from sqlalchemy import func, case, and_, or_, desc
from sqlalchemy.orm import Session
import asyncio

from ..core.database import SessionLocal
from ..core.models import (
    Trade, Signal, Balance, Position, MarketData,
    BotState, TradingPair, BotSettings,
    TradeStatus, OrderSide, SignalAction
)
from ..core.unified_config import unified_config
from ..logging.smart_logger import get_logger

logger = get_logger(__name__)

def register_unified_api_routes(app, bot_manager=None, exchange_client=None):
    """
    Регистрация всех API роутов для веб-интерфейса
    """
    logger.info("🚀 Регистрация unified API routes...")
    
    # ===== BOT CONTROL API =====
    
    @app.route('/api/bot/status')
    @login_required
    def get_bot_status():
        """Получение статуса бота"""
        try:
            db = SessionLocal()
            try:
                # Получаем состояние из БД
                bot_state = db.query(BotState).first()
                if not bot_state:
                    bot_state = BotState()
                    db.add(bot_state)
                    db.commit()
                
                # Если есть bot_manager, получаем актуальный статус
                if bot_manager:
                    status_data = bot_manager.get_status()
                    is_running = status_data.get('is_running', False)
                else:
                    is_running = bot_state.is_running
                
                # Обновляем статус в БД
                bot_state.is_running = is_running
                db.commit()
                
                return jsonify({
                    'success': True,
                    'is_running': is_running,
                    'start_time': bot_state.start_time.isoformat() if bot_state.start_time else None,
                    'uptime': bot_manager.get_uptime() if bot_manager and is_running else '0h 0m',
                    'total_trades': bot_state.total_trades,
                    'successful_trades': bot_state.successful_trades,
                    'failed_trades': bot_state.failed_trades,
                    'cycles_count': bot_state.cycles_count,
                    'trades_today': bot_state.trades_today,
                    'active_pairs': bot_state.active_pairs or [],
                    'current_strategy': bot_state.current_strategy,
                    'last_heartbeat': bot_state.last_heartbeat.isoformat() if bot_state.last_heartbeat else None
                })
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка получения статуса бота: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'is_running': False
            }), 500
    
    @app.route('/api/bot/start', methods=['POST'])
    @login_required
    def start_bot():
        """Запуск бота"""
        try:
            if not bot_manager:
                return jsonify({
                    'success': False,
                    'message': 'Bot manager not available'
                }), 503
            
            # Запускаем бота асинхронно
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(bot_manager.start())
            
            if result:
                # Обновляем состояние в БД
                db = SessionLocal()
                try:
                    bot_state = db.query(BotState).first()
                    if not bot_state:
                        bot_state = BotState()
                        db.add(bot_state)
                    
                    bot_state.is_running = True
                    bot_state.start_time = datetime.utcnow()
                    bot_state.status = 'running'
                    db.commit()
                finally:
                    db.close()
                
                return jsonify({
                    'success': True,
                    'message': 'Бот успешно запущен'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Не удалось запустить бота'
                }), 500
                
        except Exception as e:
            logger.error(f"Ошибка запуска бота: {e}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
    
    @app.route('/api/bot/stop', methods=['POST'])
    @login_required
    def stop_bot():
        """Остановка бота"""
        try:
            if not bot_manager:
                return jsonify({
                    'success': False,
                    'message': 'Bot manager not available'
                }), 503
            
            # Останавливаем бота
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(bot_manager.stop())
            
            # Обновляем состояние в БД
            db = SessionLocal()
            try:
                bot_state = db.query(BotState).first()
                if bot_state:
                    bot_state.is_running = False
                    bot_state.stop_time = datetime.utcnow()
                    bot_state.status = 'stopped'
                    db.commit()
            finally:
                db.close()
            
            return jsonify({
                'success': True,
                'message': 'Бот успешно остановлен'
            })
            
        except Exception as e:
            logger.error(f"Ошибка остановки бота: {e}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500
    
    # ===== DASHBOARD API =====
    
    @app.route('/api/dashboard/balance')
    @login_required
    def get_balance():
        """Получение баланса"""
        try:
            db = SessionLocal()
            try:
                # Получаем последний баланс USDT
                balance = db.query(Balance).filter(
                    Balance.asset == 'USDT'
                ).order_by(Balance.updated_at.desc()).first()
                
                if balance:
                    return jsonify({
                        'success': True,
                        'total_usdt': float(balance.total),
                        'free_usdt': float(balance.free),
                        'locked_usdt': float(balance.locked),
                        'updated_at': balance.updated_at.isoformat()
                    })
                else:
                    # Если баланса нет, пробуем получить с биржи
                    if exchange_client:
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            balance_data = loop.run_until_complete(exchange_client.get_balance())
                            
                            usdt_balance = balance_data.get('USDT', {})
                            return jsonify({
                                'success': True,
                                'total_usdt': float(usdt_balance.get('total', 0)),
                                'free_usdt': float(usdt_balance.get('free', 0)),
                                'locked_usdt': float(usdt_balance.get('locked', 0)),
                                'updated_at': datetime.utcnow().isoformat()
                            })
                        except Exception as e:
                            logger.error(f"Ошибка получения баланса с биржи: {e}")
                    
                    return jsonify({
                        'success': True,
                        'total_usdt': 0,
                        'free_usdt': 0,
                        'locked_usdt': 0,
                        'updated_at': datetime.utcnow().isoformat()
                    })
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/dashboard/positions')
    @login_required
    def get_positions():
        """Получение открытых позиций"""
        try:
            db = SessionLocal()
            try:
                positions = db.query(Position).filter(
                    Position.status == 'OPEN'
                ).order_by(Position.created_at.desc()).all()
                
                positions_data = []
                for pos in positions:
                    positions_data.append({
                        'id': pos.id,
                        'symbol': pos.symbol,
                        'side': pos.side,
                        'quantity': float(pos.quantity),
                        'entry_price': float(pos.entry_price),
                        'current_price': float(pos.current_price) if pos.current_price else None,
                        'unrealized_pnl': float(pos.unrealized_pnl) if pos.unrealized_pnl else 0,
                        'pnl_percent': _calculate_pnl_percent(pos),
                        'strategy': _get_position_strategy(db, pos),
                        'created_at': pos.created_at.isoformat()
                    })
                
                return jsonify({
                    'success': True,
                    'positions': positions_data,
                    'count': len(positions_data)
                })
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка получения позиций: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'positions': []
            }), 500
    
    @app.route('/api/dashboard/statistics')
    @login_required
    def get_statistics():
        """Получение статистики"""
        try:
            db = SessionLocal()
            try:
                # Статистика за сегодня
                today = datetime.utcnow().date()
                today_start = datetime.combine(today, datetime.min.time())
                
                # Прибыль за сегодня
                today_profit = db.query(func.sum(Trade.profit_loss)).filter(
                    and_(
                        Trade.created_at >= today_start,
                        Trade.profit_loss.isnot(None)
                    )
                ).scalar() or 0
                
                # Количество сделок за сегодня
                today_trades = db.query(func.count(Trade.id)).filter(
                    Trade.created_at >= today_start
                ).scalar() or 0
                
                # Win rate за сегодня
                today_wins = db.query(func.count(Trade.id)).filter(
                    and_(
                        Trade.created_at >= today_start,
                        Trade.profit_loss > 0
                    )
                ).scalar() or 0
                
                win_rate = (today_wins / today_trades * 100) if today_trades > 0 else 0
                
                # Общая статистика
                total_trades = db.query(func.count(Trade.id)).scalar() or 0
                total_profit = db.query(func.sum(Trade.profit_loss)).filter(
                    Trade.profit_loss.isnot(None)
                ).scalar() or 0
                
                return jsonify({
                    'success': True,
                    'today_profit': float(today_profit),
                    'today_trades': today_trades,
                    'today_win_rate': round(win_rate, 2),
                    'total_trades': total_trades,
                    'total_profit': float(total_profit)
                })
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/dashboard/recent-trades')
    @login_required
    def get_recent_trades():
        """Получение последних сделок"""
        try:
            limit = request.args.get('limit', 20, type=int)
            
            db = SessionLocal()
            try:
                trades = db.query(Trade).order_by(
                    Trade.created_at.desc()
                ).limit(limit).all()
                
                trades_data = []
                for trade in trades:
                    trades_data.append({
                        'id': trade.id,
                        'symbol': trade.symbol,
                        'side': trade.side,
                        'quantity': float(trade.quantity),
                        'price': float(trade.price),
                        'profit_loss': float(trade.profit_loss) if trade.profit_loss else 0,
                        'profit_loss_percent': float(trade.profit_loss_percent) if trade.profit_loss_percent else 0,
                        'status': trade.status,
                        'strategy': trade.strategy,
                        'created_at': trade.created_at.isoformat()
                    })
                
                return jsonify({
                    'success': True,
                    'trades': trades_data,
                    'count': len(trades_data)
                })
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка получения последних сделок: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'trades': []
            }), 500
    
    # ===== CHARTS API =====
    
    @app.route('/api/charts/candles/<symbol>')
    @login_required
    def get_candles(symbol):
        """Получение свечей для графика"""
        try:
            interval = request.args.get('interval', '5m')
            limit = int(request.args.get('limit', 100))
            
            if not exchange_client:
                return jsonify({
                    'success': False,
                    'error': 'Exchange client not available'
                }), 503
            
            # Получаем свечи с биржи
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            candles = loop.run_until_complete(
                exchange_client.fetch_ohlcv(symbol, interval, limit)
            )
            
            # Форматируем данные
            formatted_candles = []
            for candle in candles:
                formatted_candles.append({
                    'time': candle[0],
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5])
                })
            
            return jsonify({
                'success': True,
                'symbol': symbol,
                'interval': interval,
                'candles': formatted_candles
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения свечей: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/charts/indicators/<symbol>')
    @login_required
    def get_indicators(symbol):
        """Получение индикаторов для символа"""
        try:
            if not bot_manager:
                return jsonify({
                    'success': False,
                    'error': 'Bot manager not available'
                }), 503
            
            # Получаем индикаторы из анализатора бота
            indicators = bot_manager.get_symbol_indicators(symbol)
            
            return jsonify({
                'success': True,
                'symbol': symbol,
                'indicators': indicators
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения индикаторов: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ===== ANALYTICS API =====
    
    @app.route('/api/analytics/performance')
    @login_required
    def get_performance():
        """Получение данных производительности"""
        try:
            days = request.args.get('days', 30, type=int)
            start_date = datetime.utcnow() - timedelta(days=days)
            
            db = SessionLocal()
            try:
                # Суммарная статистика
                total_trades = db.query(func.count(Trade.id)).filter(
                    Trade.created_at >= start_date
                ).scalar() or 0
                
                profitable_trades = db.query(func.count(Trade.id)).filter(
                    and_(
                        Trade.created_at >= start_date,
                        Trade.profit_loss > 0
                    )
                ).scalar() or 0
                
                total_profit = db.query(func.sum(Trade.profit_loss)).filter(
                    and_(
                        Trade.created_at >= start_date,
                        Trade.profit_loss.isnot(None)
                    )
                ).scalar() or 0
                
                # Win rate
                win_rate = (profitable_trades / total_trades) if total_trades > 0 else 0
                
                # Profit factor
                total_wins = db.query(func.sum(Trade.profit_loss)).filter(
                    and_(
                        Trade.created_at >= start_date,
                        Trade.profit_loss > 0
                    )
                ).scalar() or 0
                
                total_losses = abs(db.query(func.sum(Trade.profit_loss)).filter(
                    and_(
                        Trade.created_at >= start_date,
                        Trade.profit_loss < 0
                    )
                ).scalar() or 0)
                
                profit_factor = (total_wins / total_losses) if total_losses > 0 else float('inf')
                
                # Дневная прибыль
                daily_pnl = db.query(
                    func.date(Trade.created_at).label('date'),
                    func.sum(Trade.profit_loss).label('profit')
                ).filter(
                    and_(
                        Trade.created_at >= start_date,
                        Trade.profit_loss.isnot(None)
                    )
                ).group_by(func.date(Trade.created_at)).all()
                
                # Производительность по стратегиям
                strategy_performance = db.query(
                    Trade.strategy,
                    func.count(Trade.id).label('trades'),
                    func.sum(case((Trade.profit_loss > 0, 1), else_=0)).label('wins'),
                    func.sum(Trade.profit_loss).label('total_profit')
                ).filter(
                    Trade.created_at >= start_date
                ).group_by(Trade.strategy).all()
                
                # Топ прибыльные пары
                top_pairs = db.query(
                    Trade.symbol,
                    func.count(Trade.id).label('trades'),
                    func.sum(Trade.profit_loss).label('profit'),
                    func.sum(case((Trade.profit_loss > 0, 1), else_=0)).label('wins')
                ).filter(
                    Trade.created_at >= start_date
                ).group_by(Trade.symbol).order_by(
                    func.sum(Trade.profit_loss).desc()
                ).limit(10).all()
                
                # Форматируем данные
                daily_pnl_data = [
                    {
                        'date': str(day.date),
                        'profit': float(day.profit) if day.profit else 0
                    }
                    for day in daily_pnl
                ]
                
                strategy_data = []
                for strat in strategy_performance:
                    win_rate_strat = (strat.wins / strat.trades * 100) if strat.trades > 0 else 0
                    strategy_data.append({
                        'strategy': strat.strategy,
                        'trades': strat.trades,
                        'win_rate': round(win_rate_strat, 2),
                        'total_profit': float(strat.total_profit) if strat.total_profit else 0
                    })
                
                pairs_data = []
                for pair in top_pairs:
                    win_rate_pair = (pair.wins / pair.trades * 100) if pair.trades > 0 else 0
                    pairs_data.append({
                        'symbol': pair.symbol,
                        'trades': pair.trades,
                        'profit': float(pair.profit) if pair.profit else 0,
                        'win_rate': round(win_rate_pair, 2)
                    })
                
                # Sharpe ratio (упрощенный расчет)
                if daily_pnl_data:
                    daily_returns = [d['profit'] for d in daily_pnl_data]
                    if len(daily_returns) > 1:
                        avg_return = sum(daily_returns) / len(daily_returns)
                        std_return = (sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
                        sharpe_ratio = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0
                    else:
                        sharpe_ratio = 0
                else:
                    sharpe_ratio = 0
                
                return jsonify({
                    'success': True,
                    'summary': {
                        'total_trades': total_trades,
                        'profitable_trades': profitable_trades,
                        'total_profit': float(total_profit),
                        'win_rate': round(win_rate, 4),
                        'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999,
                        'sharpe_ratio': round(sharpe_ratio, 2)
                    },
                    'daily_pnl': daily_pnl_data,
                    'strategy_performance': strategy_data,
                    'top_pairs': pairs_data
                })
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка получения производительности: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ===== CONFIG API =====
    
    @app.route('/api/config/pairs')
    @login_required
    def get_config_pairs():
        """Получение списка торговых пар из конфигурации"""
        try:
            # Основные пары
            primary_pairs = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
            
            # Дополнительные пары
            secondary_pairs = ['ADAUSDT', 'DOGEUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT']
            
            # Волатильные пары
            volatile_pairs = ['SHIBUSDT', 'PEPEUSDT', 'FLOKIUSDT']
            
            pairs_data = []
            
            # Добавляем основные пары
            for symbol in primary_pairs:
                pairs_data.append({
                    'symbol': symbol,
                    'category': 'primary',
                    'active': True
                })
            
            # Добавляем дополнительные пары
            for symbol in secondary_pairs:
                pairs_data.append({
                    'symbol': symbol,
                    'category': 'secondary',
                    'active': False
                })
            
            # Добавляем волатильные пары
            for symbol in volatile_pairs:
                pairs_data.append({
                    'symbol': symbol,
                    'category': 'volatile',
                    'active': False
                })
            
            return jsonify({
                'success': True,
                'pairs': pairs_data
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения конфигурации пар: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ===== SETTINGS API =====
    
    @app.route('/api/settings')
    @login_required
    def get_settings():
        """Получение настроек"""
        try:
            db = SessionLocal()
            try:
                settings = db.query(BotSettings).first()
                if not settings:
                    # Создаем настройки по умолчанию
                    settings = BotSettings()
                    db.add(settings)
                    db.commit()
                
                return jsonify({
                    'success': True,
                    'settings': {
                        'bot_mode': 'testnet' if unified_config.TESTNET else 'mainnet',
                        'default_strategy': settings.strategy,
                        'max_positions': settings.max_positions,
                        'position_size': float(settings.position_size),
                        'stop_loss_percent': float(settings.stop_loss_percent),
                        'take_profit_percent': float(settings.take_profit_percent),
                        'risk_level': float(settings.risk_level),
                        'is_active': settings.is_active
                    }
                })
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка получения настроек: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/settings/general', methods=['POST'])
    @login_required
    def update_general_settings():
        """Обновление основных настроек"""
        try:
            data = request.get_json()
            
            db = SessionLocal()
            try:
                settings = db.query(BotSettings).first()
                if not settings:
                    settings = BotSettings()
                    db.add(settings)
                
                # Обновляем настройки
                if 'default_strategy' in data:
                    settings.strategy = data['default_strategy']
                if 'max_positions' in data:
                    settings.max_positions = int(data['max_positions'])
                if 'position_size' in data:
                    settings.position_size = float(data['position_size'])
                
                db.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Настройки сохранены'
                })
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка обновления настроек: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/settings/risk', methods=['POST'])
    @login_required
    def update_risk_settings():
        """Обновление настроек риска"""
        try:
            data = request.get_json()
            
            db = SessionLocal()
            try:
                settings = db.query(BotSettings).first()
                if not settings:
                    settings = BotSettings()
                    db.add(settings)
                
                # Обновляем настройки риска
                if 'stop_loss_percent' in data:
                    settings.stop_loss_percent = float(data['stop_loss_percent'])
                if 'take_profit_percent' in data:
                    settings.take_profit_percent = float(data['take_profit_percent'])
                if 'risk_level' in data:
                    settings.risk_level = float(data['risk_level'])
                
                db.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Настройки риска сохранены'
                })
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка обновления настроек риска: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/trading-pairs')
    @login_required
    def get_trading_pairs():
        """Получение торговых пар"""
        try:
            db = SessionLocal()
            try:
                pairs = db.query(TradingPair).all()
                
                pairs_data = []
                for pair in pairs:
                    pairs_data.append({
                        'id': pair.id,
                        'symbol': pair.symbol,
                        'is_active': pair.is_active,
                        'strategy': pair.strategy,
                        'stop_loss_percent': float(pair.stop_loss_percent),
                        'take_profit_percent': float(pair.take_profit_percent),
                        'last_price': float(pair.last_price) if pair.last_price else None,
                        'volume_24h': float(pair.volume_24h) if pair.volume_24h else None,
                        'price_change_24h': float(pair.price_change_24h) if pair.price_change_24h else None
                    })
                
                return jsonify({
                    'success': True,
                    'pairs': pairs_data
                })
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка получения торговых пар: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'pairs': []
            }), 500
    
    @app.route('/api/trading-pairs/<int:pair_id>/toggle', methods=['POST'])
    @login_required
    def toggle_trading_pair(pair_id):
        """Включение/выключение торговой пары"""
        try:
            data = request.get_json()
            is_active = data.get('active', False)
            
            db = SessionLocal()
            try:
                pair = db.query(TradingPair).filter(TradingPair.id == pair_id).first()
                if not pair:
                    return jsonify({
                        'success': False,
                        'message': 'Пара не найдена'
                    }), 404
                
                pair.is_active = is_active
                db.commit()
                
                return jsonify({
                    'success': True,
                    'message': f"Пара {pair.symbol} {'активирована' if is_active else 'деактивирована'}"
                })
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Ошибка переключения пары: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ===== NEWS API =====
    
    @app.route('/api/news/latest')
    @login_required
    def get_latest_news():
        """Получение последних новостей"""
        try:
            # Здесь должна быть интеграция с новостными API
            # Пока возвращаем заглушку
            news_data = [
                {
                    'id': 1,
                    'title': 'Bitcoin достиг нового максимума',
                    'source': 'CoinDesk',
                    'content': 'Цена Bitcoin превысила отметку в $45,000...',
                    'sentiment': 0.8,
                    'impact': 'high',
                    'url': 'https://example.com/news/1',
                    'published_at': datetime.utcnow().isoformat(),
                    'coins': ['BTC', 'ETH']
                }
            ]
            
            return jsonify({
                'success': True,
                'news': news_data
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения новостей: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'news': []
            }), 500
    
    @app.route('/api/social/signals')
    @login_required
    def get_social_signals():
        """Получение социальных сигналов"""
        try:
            # Здесь должна быть интеграция с социальными API
            # Пока возвращаем заглушку
            signals_data = [
                {
                    'id': 1,
                    'source': 'Twitter',
                    'author': '@crypto_analyst',
                    'content': 'Bullish on $SOL! Technical analysis shows...',
                    'sentiment': 0.7,
                    'confidence': 0.85,
                    'engagement': 1523,
                    'coins': ['SOL'],
                    'timestamp': datetime.utcnow().isoformat()
                }
            ]
            
            return jsonify({
                'success': True,
                'signals': signals_data
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения социальных сигналов: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'signals': []
            }), 500
    
    # ===== SYSTEM API =====
    
    @app.route('/api/system/stats')
    @login_required
    def get_system_stats():
        """Получение системной статистики"""
        try:
            stats = {
                'bot_manager': bot_manager is not None,
                'exchange_client': exchange_client is not None,
                'websocket': hasattr(app, 'socketio') and app.socketio is not None
            }
            
            if bot_manager:
                bot_status = bot_manager.get_status()
                stats['bot'] = {
                    'is_running': bot_status.get('is_running', False),
                    'uptime': bot_status.get('uptime', '0h 0m'),
                    'cycles': bot_status.get('cycles_completed', 0)
                }
            
            return jsonify({
                'success': True,
                'stats': stats,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/ticker/<symbol>')
    @login_required
    def get_ticker(symbol):
        """Получение текущей цены символа"""
        try:
            if exchange_client:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                ticker = loop.run_until_complete(exchange_client.fetch_ticker(symbol))
                
                return jsonify({
                    'success': True,
                    'symbol': symbol,
                    'price': float(ticker.get('last', 0)),
                    'bid': float(ticker.get('bid', 0)),
                    'ask': float(ticker.get('ask', 0)),
                    'volume': float(ticker.get('baseVolume', 0)),
                    'change_24h': float(ticker.get('percentage', 0))
                })
            else:
                # Заглушка если нет exchange_client
                return jsonify({
                    'success': True,
                    'symbol': symbol,
                    'price': 0,
                    'bid': 0,
                    'ask': 0,
                    'volume': 0,
                    'change_24h': 0
                })
                
        except Exception as e:
            logger.error(f"Ошибка получения тикера: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ===== HELPER METHODS =====
    
    def _calculate_pnl_percent(position):
        """Расчет процента прибыли/убытка"""
        if position.entry_price and position.current_price:
            if position.side == 'BUY':
                return ((position.current_price - position.entry_price) / position.entry_price) * 100
            else:  # SELL
                return ((position.entry_price - position.current_price) / position.entry_price) * 100
        return 0
    
    def _get_position_strategy(db, position):
        """Получение стратегии позиции"""
        # Пытаемся найти связанную сделку
        trade = db.query(Trade).filter(
            and_(
                Trade.symbol == position.symbol,
                Trade.created_at >= position.created_at - timedelta(minutes=5),
                Trade.created_at <= position.created_at + timedelta(minutes=5)
            )
        ).first()
        
        return trade.strategy if trade else 'unknown'
    
    logger.info("✅ Unified API routes зарегистрированы")
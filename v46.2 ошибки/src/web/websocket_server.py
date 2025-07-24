"""
WebSocket сервер для real-time обновлений
"""
from flask_socketio import SocketIO, emit
from flask import Flask
import threading
import time
from datetime import datetime
from ..core.database import SessionLocal
from ..core.models import Trade, Balance, Signal

socketio = None

def init_websocket(app: Flask):
    """Инициализация WebSocket сервера"""
    global socketio
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    @socketio.on('connect')
    def handle_connect():
        print(f"Client connected: {datetime.now()}")
        emit('connected', {'data': 'Connected to server'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        print(f"Client disconnected: {datetime.now()}")
    
    @socketio.on('subscribe')
    def handle_subscribe(data):
        """Подписка на обновления определенного символа"""
        symbol = data.get('symbol')
        if symbol:
            print(f"Client subscribed to {symbol}")
            # Здесь можно добавить логику подписки на конкретный символ
    
    # Запускаем фоновый поток для отправки обновлений
    thread = threading.Thread(target=broadcast_updates)
    thread.daemon = True
    thread.start()
    
    return socketio

def broadcast_updates():
    """Фоновый процесс для отправки обновлений всем клиентам"""
    while True:
        try:
            db = SessionLocal()
            try:
                # Получаем последние данные
                # 1. Баланс
                balance = db.query(Balance).order_by(Balance.created_at.desc()).first()
                if balance:
                    socketio.emit('balance_update', {
                        'total_usdt': float(balance.total_balance),
                        'available_usdt': float(balance.available_balance),
                        'in_positions': float(balance.total_balance - balance.available_balance)
                    })
                
                # 2. Последние сделки
                recent_trades = db.query(Trade).order_by(
                    Trade.created_at.desc()
                ).limit(5).all()
                
                trades_data = []
                for trade in recent_trades:
                    trades_data.append({
                        'id': trade.id,
                        'symbol': trade.symbol,
                        'side': trade.side,
                        'quantity': float(trade.quantity),
                        'entry_price': float(trade.entry_price),
                        'profit': float(trade.profit_loss) if trade.profit_loss else 0,
                        'status': trade.status,
                        'created_at': trade.created_at.isoformat()
                    })
                
                if trades_data:
                    socketio.emit('trades_update', trades_data)
                
                # 3. Активные позиции
                open_positions = db.query(Trade).filter(
                    Trade.status == 'OPEN'
                ).all()
                
                positions_data = []
                for pos in open_positions:
                    positions_data.append({
                        'id': pos.id,
                        'symbol': pos.symbol,
                        'side': pos.side,
                        'quantity': float(pos.quantity),
                        'entry_price': float(pos.entry_price),
                        'strategy': pos.strategy
                    })
                
                socketio.emit('positions_update', {
                    'count': len(positions_data),
                    'positions': positions_data
                })
                
                # 4. Последние сигналы
                recent_signals = db.query(Signal).order_by(
                    Signal.created_at.desc()
                ).limit(10).all()
                
                signals_data = []
                for signal in recent_signals:
                    signals_data.append({
                        'symbol': signal.symbol,
                        'type': signal.signal_type,
                        'strength': float(signal.strength),
                        'price': float(signal.price),
                        'created_at': signal.created_at.isoformat()
                    })
                
                if signals_data:
                    socketio.emit('signals_update', signals_data)
                    
            finally:
                db.close()
                
        except Exception as e:
            print(f"Error in broadcast_updates: {e}")
        
        time.sleep(5)  # Обновляем каждые 5 секунд

def emit_trade_update(trade_data):
    """Отправка обновления о новой сделке"""
    if socketio:
        socketio.emit('new_trade', trade_data)

def emit_position_update(position_data):
    """Отправка обновления о позиции"""
    if socketio:
        socketio.emit('position_update', position_data)

def emit_bot_status(status_data):
    """Отправка статуса бота"""
    if socketio:
        socketio.emit('bot_status', status_data)
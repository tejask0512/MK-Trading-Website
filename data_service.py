# data_service.py - Run this as a separate process
import websocket
import json
import time
import sqlite3
import threading
import os
from datetime import datetime

# Database setup
DB_PATH = os.path.join("data", "market_data.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def ensure_db_setup():
    """Create database and tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables for different timeframes
    timeframes = ['5m', '15m', '1h']
    for tf in timeframes:
        cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS btc_candles_{tf} (
            time INTEGER PRIMARY KEY,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            formatted_time TEXT,
            mid_price REAL
        )''')
        
        # Table for signals
        cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS signals_{tf} (
            time INTEGER PRIMARY KEY,
            signal TEXT,
            price REAL,
            formatted_time TEXT
        )''')
    
    conn.commit()
    conn.close()

def on_message(ws, timeframe, message):
    """Process incoming websocket messages"""
    try:
        data = json.loads(message)
        
        if 'k' in data:
            kline = data['k']
            
            # Extract data
            timestamp = kline['t']
            formatted_time = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
            open_price = float(kline['o'])
            high_price = float(kline['h'])
            low_price = float(kline['l'])
            close_price = float(kline['c'])
            volume = float(kline['v'])
            mid_price = (high_price + low_price) / 2
            is_candle_closed = kline['x']
            
            # Create candle object
            candle = {
                'time': timestamp,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume,
                'formatted_time': formatted_time,
                'mid_price': mid_price
            }
            
            # Save to database
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute(f'''
            INSERT OR REPLACE INTO btc_candles_{timeframe}
            (time, open, high, low, close, volume, formatted_time, mid_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                formatted_time,
                mid_price
            ))
            
            conn.commit()
            
            # Run strategy on closed candles
            if is_candle_closed:
                # Simple trend detection strategy
                cursor.execute(f'''
                SELECT close FROM btc_candles_{timeframe}
                ORDER BY time DESC LIMIT 20
                ''')
                prices = [row[0] for row in cursor.fetchall()]
                
                if len(prices) >= 5:
                    signal = None
                    current_price = prices[0]
                    prev_prices = prices[1:5]
                    
                    # Simple trend detection
                    if all(current_price > p for p in prev_prices):
                        signal = "BUY"
                    elif all(current_price < p for p in prev_prices):
                        signal = "SELL"
                    
                    if signal:
                        cursor.execute(f'''
                        INSERT OR REPLACE INTO signals_{timeframe}
                        (time, signal, price, formatted_time)
                        VALUES (?, ?, ?, ?)
                        ''', (
                            timestamp,
                            signal,
                            close_price,
                            formatted_time
                        ))
                        
                        print(f"[{formatted_time}] {timeframe} Signal: {signal} at {close_price}")
            
            conn.close()
            
            # Print update every minute (reduce console spam)
            if int(timestamp / 1000) % 60 == 0:
                print(f"[{formatted_time}] Updated {timeframe} data: {close_price}")
                
    except Exception as e:
        print(f"Error processing message for {timeframe}: {str(e)}")

def on_error(ws, timeframe, error):
    print(f"WebSocket Error ({timeframe}): {str(error)}")

def on_close(ws, timeframe, close_status_code, close_msg):
    print(f"WebSocket Closed ({timeframe}): {close_status_code} - {close_msg}")

def on_open(ws, timeframe):
    print(f"WebSocket Connection Opened for {timeframe}")

def connect_websocket(timeframe):
    """Connect to Binance WebSocket for a specific timeframe"""
    websocket_url = f"wss://fstream.binance.com/ws/btcusdt@kline_{timeframe}"
    
    ws = websocket.WebSocketApp(
        websocket_url,
        on_message=lambda ws, msg: on_message(ws, timeframe, msg),
        on_error=lambda ws, err: on_error(ws, timeframe, err),
        on_close=lambda ws, close_status_code, close_msg: on_close(ws, timeframe, close_status_code, close_msg),
        on_open=lambda ws: on_open(ws, timeframe)
    )
    
    while True:
        try:
            ws.run_forever(ping_interval=30, ping_timeout=10)
            print(f"Connection lost for {timeframe}, reconnecting in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"Error in WebSocket connection for {timeframe}: {str(e)}")
            time.sleep(5)

def run_websocket_threads():
    """Start WebSocket connections for all timeframes"""
    timeframes = ['5m', '15m', '1h']
    threads = []
    
    for tf in timeframes:
        t = threading.Thread(target=connect_websocket, args=(tf,), daemon=True)
        threads.append(t)
        t.start()
        print(f"Started thread for {tf} timeframe")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(60)
            print("Data service running... " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    except KeyboardInterrupt:
        print("Data service stopping...")

if __name__ == "__main__":
    print("Starting BTC data service...")
    ensure_db_setup()
    run_websocket_threads()
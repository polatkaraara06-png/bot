import time
import pandas as pd
import ta
from core.shared_state import shared_state
import random

CANDLE_INTERVAL_SEC = 300

def aggregate_ticks():
    now = time.time()
    
    for (market, symbol), tick_data in list(shared_state.ticks.items()):
        
        price = tick_data.get("price")
        ts = tick_data.get("ts")
        volume_increment = random.uniform(0.1, 5.0)
        
        if not price or not ts:
            continue
            
        key = (market, symbol, CANDLE_INTERVAL_SEC)
        current_candle = shared_state.get_current_candle_state(key)
        
        if current_candle["start_ts"] == 0:
            start_ts = (int(ts) // CANDLE_INTERVAL_SEC) * CANDLE_INTERVAL_SEC
            current_candle.update({
                "start_ts": start_ts, "open": price, "high": price, "low": price, "close": price, "volume": volume_increment
            })
            
        elif ts >= current_candle["start_ts"] + CANDLE_INTERVAL_SEC:
            closed_candle = dict(current_candle)
            shared_state.add_candle(market, symbol, CANDLE_INTERVAL_SEC, closed_candle)
            start_ts = (int(ts) // CANDLE_INTERVAL_SEC) * CANDLE_INTERVAL_SEC
            current_candle.update({
                "start_ts": start_ts, "open": price, "high": price, "low": price, "volume": volume_increment
            })
            
        current_candle["high"] = max(current_candle["high"], price)
        current_candle["low"] = min(current_candle["low"], price)
        current_candle["close"] = price
        current_candle["volume"] += volume_increment
        
        shared_state.update_candle_state(key, current_candle)

def calculate_atr(market, symbol, interval=CANDLE_INTERVAL_SEC, period=14):
    candles = shared_state.get_historical_candles(market, symbol, interval)
    if len(candles) < period:
        return 0.0
        
    df = pd.DataFrame(candles)
    if not all(col in df.columns for col in ['high', 'low', 'close']):
        return 0.0
        
    df.rename(columns={'high':'High', 'low':'Low', 'close':'Close'}, inplace=True)
    
    try:
        atr_values = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=period)
        if atr_values.empty: return 0.0
        last_atr = atr_values.iloc[-1]
        current_price = df['Close'].iloc[-1]
        if current_price > 0: return (last_atr / current_price) * 100.0
    except Exception: pass
    return 0.0

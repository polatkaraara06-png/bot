import random
import numpy as np
import pandas as pd
import ta.momentum as tam
from core.shared_state import shared_state
from core.ai.online_rl import agent, RLAgent

TRADING_THRESHOLD = 0.2 
BASE_LEVERAGE = 5.0 
EXTREME_VOLATILITY_THRESHOLD = 1.0
MIN_PROFIT_THRESHOLD_PCT = 0.20 

def _analyze_features(features: dict, strategy: str) -> dict:
    symbol = features["symbol"]
    candles = features.get("candles", [])

    MIN_CANDLES_RSI = 15 
    MIN_CANDLES_SMA = 11
    MIN_CANDLES_ENGULF = 2

    if len(candles) < MIN_CANDLES_ENGULF:
        return {"action": None, "score": 0.0, "details": "Not enough candles"}

    df = pd.DataFrame(candles)
    if not all(col in df.columns for col in ['open', 'high', 'low', 'close']):
         return {"action": None, "score": 0.0, "details": "Candle data incomplete"}
         
    df.rename(columns={'open':'Open', 'high':'High', 'low':'Low', 'close':'Close'}, inplace=True) 

    t_score = 0.0
    p_score = 0.0
    
    try:
        if len(df) >= MIN_CANDLES_RSI:
            df['RSI'] = tam.rsi(df['Close'], window=14)
            rsi_val = df['RSI'].iloc[-1]
            if rsi_val < 35: t_score += 0.3
            if rsi_val > 65: t_score -= 0.3
            
        if len(df) >= MIN_CANDLES_SMA:
            df['SMA_10'] = df['Close'].rolling(window=10).mean()
            if df['Close'].iloc[-1] > df['SMA_10'].iloc[-1]: t_score += 0.1
            else: t_score -= 0.1

        if len(df) >= MIN_CANDLES_ENGULF:
            o, h, l, c = df['Open'].values, df['High'].values, df['Low'].values, df['Close'].values
            bull_eng = (o[-2] > c[-2]) and (o[-1] < c[-1]) and (c[-1] > o[-2]) and (o[-1] < c[-2])
            bear_eng = (o[-2] < c[-2]) and (o[-1] > c[-1]) and (c[-1] < o[-2]) and (o[-1] > c[-2])
            if bull_eng: p_score = 0.6
            elif bear_eng: p_score = -0.6
            else:
                bull_har = (o[-2] < c[-2]) and (o[-1] > c[-1]) and (o[-1] > c[-2]) and (c[-1] < o[-2])
                bear_har = (o[-2] > c[-2]) and (o[-1] < c[-1]) and (o[-1] < c[-2]) and (c[-1] > o[-2])
                if bull_har: p_score = 0.3
                elif bear_har: p_score = -0.3
                
    except Exception as e:
         print(f"[ANALYZE_ERROR] {symbol}: {e}")
         return {"action": None, "score": 0.0, "details": f"Error: {e}"}

    current_volume_ratio = features.get("volume_ratio", 1.0)
    final_score = (t_score + p_score) * max(1.0, current_volume_ratio * 0.5)

    action = None
    if final_score > TRADING_THRESHOLD: action = "buy"
    elif final_score < -TRADING_THRESHOLD: action = "sell"

    return {"action": action, "score": final_score, "details": f"T:{t_score:.1f} P:{p_score:.1f} V:{current_volume_ratio:.1f}"}

def decide_trade(features: dict, agent: RLAgent, strategy: str) -> dict:
    
    # --- NUR ANALYSE (EXPLOITATION) ---
    analysis = _analyze_features(features, strategy)
    action = analysis["action"]
    score = abs(analysis["score"])

    if not action: # Keine Aktion laut Analyse
        return None

    # MTF-Filter 
    mtf_trend = features.get("mtf_trend", 0.0) 
    if abs(features.get("trend", 0.0)) > 0.05 and features.get("trend", 0.0) * mtf_trend < 0:
        return None

    # TP/SL und Hebel basierend auf Strategie und Agenten-Performance
    atr_pct = float(features.get("atr_pct", 0.01))
    vol = float(features.get("vol", 0.0))
    opt_leverage = agent.get_dynamic_leverage(features, base_leverage=BASE_LEVERAGE if strategy=='conservative' else 3.0)

    if strategy == "scalper":
        sl_pct = 1.0
        tp_pct = max(1.5, MIN_PROFIT_THRESHOLD_PCT)
        if vol > EXTREME_VOLATILITY_THRESHOLD: opt_leverage = 10.0
    else: 
        sl_pct = 1.5
        tp_pct = 2.5

    conf = agent.get_confidence()
    risk_adjusted_margin = agent.get_dynamic_margin(strategy, current_total_cap=150.0)
    
    # Pattern-Stacking
    if score >= 0.8 and conf > 70: 
         risk_adjusted_margin *= 1.5 
         opt_leverage = min(10.0, opt_leverage * 1.2) 
         print(f"[STACKING] Signal {score:.1f} & Konfidenz {conf:.0f} -> Boost!")

    return {
        "symbol": features["symbol"], "action": action, "leverage": round(opt_leverage, 2),
        "tp_pct": tp_pct, "sl_pct": sl_pct, "confidence": round(conf, 3),
        "strategy": strategy, "risk_adjusted_margin": round(risk_adjusted_margin, 2)
    }

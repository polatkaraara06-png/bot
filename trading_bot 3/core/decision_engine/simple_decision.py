def decide_trade(features, agent):
    """
    features: dict with keys:
      market, symbol, trend, vol, atr_pct, price
    returns decision dict or None
    """
    trend = float(features.get("trend", 0.0))
    vol = float(features.get("vol", 0.0))
    atr_pct = float(features.get("atr_pct", 0.01))
    symbol = features["symbol"]

    # require real signal
    if abs(trend) < 0.2:    # weak momentum -> skip
        return None

    # risk based on vol
    if vol < 0.3:
        lev = 3.0; tp = max(0.008, 1.5*atr_pct); sl = max(0.004, 1.0*atr_pct)
    elif vol < 0.7:
        lev = 2.0; tp = max(0.010, 2.0*atr_pct); sl = max(0.005, 1.3*atr_pct)
    else:
        lev = 1.2; tp = max(0.012, 2.5*atr_pct); sl = max(0.007, 1.6*atr_pct)

    action = "buy" if trend > 0 else "sell"
    conf = min(1.0, abs(trend))  # 0..1
    return {
        "symbol": symbol,
        "action": action,
        "leverage": round(lev,2),
        "tp_pct": tp,
        "sl_pct": sl,
        "confidence": round(conf,3),
    }

import time, itertools
from core.shared_state import shared_state
from core.ai import online_rl

_id_counter = itertools.count(1)
MAX_LATENCY_MS = 500
TRAILING_STOP_OFFSET_PCT = 0.5 # TP folgt 0.5% unter dem höchsten Kurs

def _new_id():
    return f"T{next(_id_counter):08d}"

def open_position(symbol:str, side:str, market:str, entry_price:float, margin:float, leverage:float, tp_pct:float, sl_pct:float, features:dict, strategy:str="conservative"):
    
    if shared_state.latency_ms > MAX_LATENCY_MS:
        print(f"[PAPER] Trade abgelehnt: Latenz ({shared_state.latency_ms} ms) ist zu hoch.")
        return None

    if shared_state.available < margin:
        print(f"[PAPER] Daycap erschöpft ({shared_state.daycap_used:.2f}/{shared_state.daycap_total:.2f})")
        return None
    
    qty = (margin * leverage) / max(1e-9, entry_price)
    
    t = {
        "id": _new_id(),
        "market": market,
        "symbol": symbol,
        "side": side,
        "entry_price": float(entry_price),
        "qty": float(qty),
        "leverage": float(leverage),
        "tp": float(tp_pct),
        "sl": float(sl_pct),
        "timestamp": time.time(),
        "margin_used": float(margin),
        "features": features or {},
        "strategy": strategy,
        "max_price": entry_price, # [NEU] Verfolgt den höchsten Preis für Trailing
    }
    shared_state.open_trade(t)
    print(f"[PAPER-OPEN] ({strategy.upper()}) {market.upper()} {side.upper()} {symbol} | margin={margin:.2f} lev={leverage:.2f} tp={tp_pct:.2f}% sl={sl_pct:.2f}% id={t['id']}")
    return t["id"]

def _pnl_pct_for(side:str, entry:float, price:float) -> float:
    if side == "buy":
        return (price - entry) / entry * 100.0
    else:
        return (entry - price) / entry * 100.0

def check_and_close_all():
    open_list = list(shared_state.open_trades.values())
    now = time.time()
    for t in open_list:
        sym = t["symbol"]; market = t["market"]; side = t["side"]
        
        lookup_key = (market.lower(), sym.upper())
        tick = shared_state.ticks.get(lookup_key)
        
        if not tick: 
            continue
            
        price = float(tick.get("price", 0))
        if price <= 0:
            continue

        # [NEU] 1. Aktualisiere den Höchstpreis für Trailing Stop
        current_max_price = t["max_price"]
        if (side == "buy" and price > current_max_price) or (side == "sell" and price < current_max_price):
            t["max_price"] = price
            
        # [NEU] 2. Berechne Trailing Stop Level
        is_trailing = t.get("tp") > 2.0 # Trailing nur, wenn TP hoch genug gesetzt ist (Definiert in simple_decision.py)
        
        if is_trailing:
            offset = TRAILING_STOP_OFFSET_PCT / 100.0 
            if side == "buy":
                trailing_level = t["max_price"] * (1 - offset)
                hit_trailing = price <= trailing_level
            else:
                trailing_level = t["max_price"] * (1 + offset)
                hit_trailing = price >= trailing_level
        else:
            hit_trailing = False
            
        
        gain_pct = _pnl_pct_for(side, float(t["entry_price"]), price)
        hit_tp = gain_pct >= float(t["tp"])
        hit_sl = (-gain_pct) >= float(t["sl"])
        
        max_hold_sec = 300 
        is_scalper = t.get('strategy') == 'scalper'
        
        timeout = False
        if is_scalper:
            timeout = (now - t.get("timestamp", now)) > max_hold_sec
        
        if hit_tp or hit_sl or timeout or hit_trailing:
            pnl = (gain_pct/100.0) * float(t["entry_price"]) * float(t["qty"])
            shared_state.close_trade(t["id"], exit_price=price, pnl=pnl, ts=now)
            
            try:
                online_rl.add_experience(sym, market, side, reward=gain_pct, features=t.get("features", {}))
            except Exception as e:
                print("[PAPER] RL add_experience error:", e)
                
            reason = "TP" if hit_tp else ("SL" if hit_sl else "TIMEOUT")
            if hit_trailing: reason = "TRAIL"
            print(f"[PAPER-CLOSE] ({t.get('strategy','?').upper()}) {market.upper()} {side.upper()} {sym} ({reason}) | exit={price:.6f} pnl={pnl:+.2f} ({gain_pct:+.2f}%) id={t['id']}")

import time, itertools
from core.shared_state import shared_state
from core.ai import online_rl

_id_counter = itertools.count(1)

def _new_id():
    return f"T{next(_id_counter):08d}"

def open_position(symbol:str, side:str, market:str, entry_price:float, margin:float, leverage:float, tp_pct:float, sl_pct:float, features:dict):
    if shared_state.available < margin:
        print(f"[PAPER] Daycap erschöpft ({shared_state.daycap_used:.2f}/{shared_state.daycap_total:.2f})")
        return None
    qty = (margin * leverage) / max(1e-9, entry_price)
    t = {
        "id": _new_id(),
        "market": market,         # "spot" | "futures"
        "symbol": symbol,
        "side": side,             # "buy" | "sell"
        "entry_price": float(entry_price),
        "qty": float(qty),
        "leverage": float(leverage),
        "tp": float(tp_pct),
        "sl": float(sl_pct),
        "timestamp": time.time(),
        "margin_used": float(margin),
        "features": features or {}
    }
    shared_state.open_trade(t)
    print(f"[PAPER-OPEN] {market.upper()} {side.upper()} {symbol} | margin={margin:.2f} lev={leverage:.2f} tp={tp_pct:.2f}% sl={sl_pct:.2f}% id={t['id']}")
    return t["id"]

def _pnl_pct_for(side:str, entry:float, price:float) -> float:
    if side == "buy":
        return (price - entry) / entry * 100.0
    else:
        return (entry - price) / entry * 100.0

def check_and_close_all():
    # iterate on a copy to allow removal while iterating
    open_list = list(shared_state.open_trades.values())
    now = time.time()
    for t in open_list:
        sym = t["symbol"]; market = t["market"]; side = t["side"]
        tick = shared_state.ticks.get((market, sym))
        if not tick: 
            continue
        price = float(tick.get("price", 0))
        if price <= 0:
            continue
        gain_pct = _pnl_pct_for(side, float(t["entry_price"]), price)
        hit_tp = gain_pct >= float(t["tp"])
        hit_sl = (-gain_pct) >= float(t["sl"])
        # Option: simple time-based exit safety after 5 minutes
        max_hold = 300
        timeout = (now - t["timestamp"]) > max_hold
        if hit_tp or hit_sl or timeout:
            pnl = (gain_pct/100.0) * float(t["entry_price"]) * float(t["qty"])
            shared_state.close_trade(t["id"], exit_price=price, pnl=pnl, ts=now)
            try:
                online_rl.add_experience(sym, market, side, reward=gain_pct, features=t.get("features", {}))
            except Exception as e:
                print("[PAPER] RL add_experience error:", e)
            print(f"[PAPER-CLOSE] {market.upper()} {side.upper()} {sym} | exit={price:.6f} pnl={pnl:+.2f} ({gain_pct:+.2f}%) id={t['id']}")

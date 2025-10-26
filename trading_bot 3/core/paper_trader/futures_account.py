import time
FEE=0.0006
def execute(state, market, symbol, side, qty, price):
    with state.lock:
        state.open_trades.append({"market":market,"symbol":symbol,"side":side,"qty":qty,
                                  "entry":price,"ts_open":time.time(),"status":"OPEN"})
def mtm(state):
    with state.lock:
        for t in state.open_trades:
            tick = state.ticks.get((t["market"], t["symbol"]))
            if not tick: continue
            px = tick["price"]
            pnl = (px - t["entry"]) * t["qty"] if t["side"]=="BUY" else (t["entry"]-px)*t["qty"]
            t["unrealized_pnl"] = pnl - abs(t["entry"]*t["qty"])*FEE

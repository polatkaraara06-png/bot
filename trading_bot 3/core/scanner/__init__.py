import threading, time, math, random
from core.shared_state import shared_state
from core.paper_trader import open_position, check_and_close_all

# Grunduniversum (Spot + Futures Ticker-Namen wie bei Bybit/Binance üblich)
BASE_UNIVERSE = [
    "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","TRXUSDT","MATICUSDT","DOTUSDT",
    "LTCUSDT","BCHUSDT","ATOMUSDT","LINKUSDT","XLMUSDT","XMRUSDT","APTUSDT","ARBUSDT","OPUSDT","NEARUSDT",
    "ICPUSDT","FTMUSDT","INJUSDT","SUIUSDT","HBARUSDT","ALGOUSDT","GALAUSDT","SANDUSDT","AXSUSDT","APEUSDT",
    "RNDRUSDT","PEPEUSDT","SHIBUSDT","TONUSDT","FLOWUSDT","EGLDUSDT","CRVUSDT","AAVEUSDT","DYDXUSDT","FILUSDT",
    "BLURUSDT","STXUSDT","ONEUSDT","RUNEUSDT","COAIUSDT","BTTUSDT","ETCUSDT","KASUSDT","SEIUSDT","TIAUSDT"
]

def _features_from_ticks(symbol: str):
    # einfache Echtzeit-Features aus den letzten Ticks (ohne Candle-API):
    spot = shared_state.ticks.get(("spot", symbol))
    fut  = shared_state.ticks.get(("futures", symbol))
    # Preis (wenn beides da ist, nimm futures als "leitend")
    tick = fut or spot
    if not tick: 
        return None
    price = float(tick.get("price", 0.0))
    prev = tick.get("prev")
    if prev is None:
        # speichere prev beim ersten Mal
        tick["prev"] = price
        return {"price": price, "trend": 0.0, "vol": 0.0, "atr_pct": 0.0}
    # Trend = Prozentänderung zum letzten Tick
    trend = (price - float(prev)) / max(1e-9, float(prev)) * 100.0
    # Volatilität: gleitend aus absoluter Tick-Änderung
    vol = abs(trend)
    # ATR_approx: hier nur gleitende Prozentspanne (vereinfachte Näherung)
    atr_pct = min(5.0, vol * 1.5)
    tick["prev"] = price
    return {"price": price, "trend": trend, "vol": vol, "atr_pct": atr_pct}

def _score(feat: dict) -> float:
    # Score: Momentum * Liquiditätsschätzer (hier vol)
    return abs(feat["trend"]) * (1.0 + 0.2 * feat["vol"])

def _decide_side(trend: float) -> str:
    return "buy" if trend >= 0 else "sell"

def _leverage_for(vol: float) -> float:
    # konservativ: hohe Volatilität -> niedrigere Leverage
    base = 3.0
    lev = max(1.0, min(5.0, base - 0.02*vol))
    return round(lev, 2)

def start_scanner_thread(scan_interval=10, max_open_per_scan=5, margin_per_trade=15.0):
    def run():
        print("[SCAN] Scanner Thread läuft ✅")
        while True:
            try:
                # 1) Features sammeln
                feats = []
                for sym in BASE_UNIVERSE:
                    f = _features_from_ticks(sym)
                    if f:
                        feats.append((sym, f))
                # 2) Ranking
                feats.sort(key=lambda x: _score(x[1]), reverse=True)
                hot = [sym for sym,_ in feats[:10]]
                with shared_state.lock:
                    shared_state.hot_coins = hot
                    shared_state.next_scan_at = time.time() + scan_interval
                if hot:
                    print("[SCAN] Hot-Coins:", hot[:10])
                # 3) bis zu max_open_per_scan neue Positionen öffnen (Spot+Futures je Kandidat)
                opened = 0
                for sym, f in feats[:max_open_per_scan]:
                    if opened >= max_open_per_scan:
                        break
                    side = _decide_side(f["trend"])
                    lev  = _leverage_for(f["vol"])
                    tp   = 1.5 + min(2.0, 0.5 * max(0.0, abs(f["trend"])))   # 1.5% .. ~3.5%
                    sl   = 1.0
                    price = float(f["price"])
                    # SPOT
                    open_position(sym, side, "spot", entry_price=price, margin=margin_per_trade, leverage=lev, tp_pct=tp, sl_pct=sl, features=f)
                    # FUTURES
                    open_position(sym, side, "futures", entry_price=price, margin=margin_per_trade, leverage=lev, tp_pct=tp, sl_pct=sl, features=f)
                    opened += 1
                # 4) offene Positionen überwachen und ggf. schließen
                check_and_close_all()
                time.sleep(scan_interval)
            except Exception as e:
                print("[SCANNER] Fehler:", e)
                time.sleep(3)
    threading.Thread(target=run, daemon=True, name="Scanner").start()

def start_auto_trade():
    print("[BOOT] AutoTrade (Scalper+Trader) gestartet ✅")

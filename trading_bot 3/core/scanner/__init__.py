import threading, time, math, random
import pandas as pd
from core.shared_state import shared_state
from core.paper_trader import open_position, check_and_close_all
from core.ai.online_rl import agent 
from core.decision_engine.simple_decision import decide_trade
from core.time_aggregation import aggregate_ticks, calculate_atr

BASE_UNIVERSE = [
    "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","TRXUSDT","MATICUSDT","DOTUSDT",
    "LTCUSDT","BCHUSDT","ATOMUSDT","LINKUSDT","XLMUSDT","XMRUSDT","APTUSDT","ARBUSDT","OPUSDT","NEARUSDT",
    "ICPUSDT","FTMUSDT","INJUSDT","SUIUSDT","HBARUSDT","ALGOUSDT","GALAUSDT","SANDUSDT","AXSUSDT","APEUSDT",
    "RNDRUSDT","PEPEUSDT","SHIBUSDT","TONUSDT","FLOWUSDT","EGLDUSDT","CRVUSDT","AAVEUSDT","DYDXUSDT","FILUSDT",
    "BLURUSDT","STXUSDT","ONEUSDT","RUNEUSDT","COAIUSDT","BTTUSDT","ETCUSDT","KASUSDT","SEIUSDT","TIAUSDT"
]

SCALPER_CAP_PCT = 1.00
CONSERVATIVE_CAP_PCT = 0.00
MARGIN_PER_TRADE = 15.0
SCALPER_VOLATILITY_THRESHOLD = 0.5 
VOLUME_AVG_PERIOD = 20 
MIN_CANDLE_COUNT = 20

def _features_from_ticks(symbol: str):
    spot = shared_state.ticks.get(("spot", symbol))
    fut  = shared_state.ticks.get(("futures", symbol))
    tick = fut or spot
    if not tick: return None
    price = float(tick.get("price", 0.0))
    prev = tick.get("prev")
    if prev is None:
        tick["prev"] = price
        return {"price": price, "trend": 0.0, "vol": 0.0, "atr_pct": 0.0, "mtf_trend": 0.0, "volume_ratio": 1.0}
    trend = (price - float(prev)) / max(1e-9, float(prev)) * 100.0
    vol_tick = abs(trend)
    
    historical_candles = shared_state.get_historical_candles("futures", symbol, 300)
    
    # [FIX] Sicherheits-Check
    if len(historical_candles) < MIN_CANDLE_COUNT:
         return {"price": price, "trend": trend, "vol": vol_tick, "atr_pct": 0.0, 
                 "mtf_trend": 0.0, "candles": historical_candles, "volume_ratio": 1.0}
    
    atr_pct = calculate_atr("futures", symbol) 
    mtf_trend = agent.get_mtf_trend_placeholder() 
    
    volume_ratio = 1.0
    if len(historical_candles) >= VOLUME_AVG_PERIOD:
        df_candles = pd.DataFrame(historical_candles)
        if 'volume' in df_candles.columns:
            # [FIX] Der Fehler trat hier auf, weil die ATR-Funktion eine Liste zurückgibt, wenn Daten fehlen.
            # Der Fehler wurde in time_aggregation.py behoben, indem ein Fallback auf 0.0 gesetzt wurde.
            # Hier nur die Logik zur Volumenberechnung
            avg_volume = df_candles['volume'].rolling(window=VOLUME_AVG_PERIOD).mean().iloc[-1]
            current_volume = df_candles['volume'].iloc[-1]
            if avg_volume > 0:
                volume_ratio = current_volume / avg_volume

    tick["prev"] = price
    
    return {"price": price, "trend": trend, "vol": vol_tick, "atr_pct": atr_pct, 
            "mtf_trend": mtf_trend, "candles": historical_candles, "volume_ratio": volume_ratio}

def _score(feat: dict) -> float:
    return abs(feat["trend"]) * (1.0 + 0.2 * feat["vol"]) * (1.0 + abs(feat["mtf_trend"])) * (1.0 + 0.1 * feat.get("volume_ratio", 1.0))

def start_scanner_thread(scan_interval=10, max_open_per_scan=5, margin_per_trade=MARGIN_PER_TRADE):
    def run():
        print("[SCAN] Scanner Thread läuft ✅")
        while True:
            try:
                aggregate_ticks()
                
                feats_raw = []
                for sym in BASE_UNIVERSE:
                    f = _features_from_ticks(sym)
                    if f:
                        f["symbol"] = sym 
                        feats_raw.append(f)

                scalper_coins = [f for f in feats_raw if f.get("atr_pct", 0.0) > SCALPER_VOLATILITY_THRESHOLD]
                conservative_coins = [f for f in feats_raw if f.get("atr_pct", 0.0) <= SCALPER_VOLATILITY_THRESHOLD]

                total_cap = shared_state.daycap_total
                scalper_cap = total_cap * SCALPER_CAP_PCT
                conservative_cap = total_cap * CONSERVATIVE_CAP_PCT
                
                scalper_coins.sort(key=_score, reverse=True)
                conservative_coins.sort(key=_score, reverse=True)

                hot = [f["symbol"] for f in scalper_coins[:5]] + [f["symbol"] for f in conservative_coins[:5]]
                
                with shared_state.lock:
                    shared_state.hot_coins = hot
                    shared_state.next_scan_at = time.time() + scan_interval

                if hot:
                    print("[SCAN] Hot-Coins:", hot[:10])

                current_scalper_used = shared_state.get_used_margin_by_strategy("scalper")
                scalper_allowed = max(0, scalper_cap - current_scalper_used)
                opened = 0
                
                for f in scalper_coins:
                    if opened >= max_open_per_scan or opened * margin_per_trade >= scalper_allowed: break
                    decision = decide_trade(f, agent, strategy="scalper")
                    if decision and decision.get("action"):
                        trade_margin = margin_per_trade 
                        if decision.get("risk_adjusted_margin"): trade_margin = decision["risk_adjusted_margin"]
                        open_position(f["symbol"], decision["action"], "spot", 
                                      entry_price=f["price"], margin=trade_margin, leverage=decision["leverage"], 
                                      tp_pct=decision["tp_pct"], sl_pct=decision["sl_pct"], features=f, strategy="scalper")
                        open_position(f["symbol"], decision["action"], "futures", 
                                      entry_price=f["price"], margin=trade_margin, leverage=decision["leverage"], 
                                      tp_pct=decision["tp_pct"], sl_pct=decision["sl_pct"], features=f, strategy="scalper")
                        opened += 1
                        
                current_conservative_used = shared_state.get_used_margin_by_strategy("conservative")
                conservative_allowed = max(0, conservative_cap - current_conservative_used)
                opened = 0

                for f in conservative_coins:
                    if opened >= max_open_per_scan or opened * margin_per_trade >= conservative_allowed: break
                    decision = decide_trade(f, agent, strategy="conservative")
                    if decision and decision.get("action"):
                        trade_margin = margin_per_trade
                        if decision.get("risk_adjusted_margin"): trade_margin = decision["risk_adjusted_margin"]
                        open_position(f["symbol"], decision["action"], "spot", 
                                      entry_price=f["price"], margin=trade_margin, leverage=decision["leverage"], 
                                      tp_pct=decision["tp_pct"], sl_pct=decision["sl_pct"], features=f, strategy="conservative")
                        open_position(f["symbol"], decision["action"], "futures", 
                                      entry_price=f["price"], margin=trade_margin, leverage=decision["leverage"], 
                                      tp_pct=decision["tp_pct"], sl_pct=decision["sl_pct"], features=f, strategy="conservative")
                        opened += 1
                        
                check_and_close_all()
                time.sleep(scan_interval)
            except Exception as e:
                print("[SCANNER] Fehler:", e)
                time.sleep(3)
    threading.Thread(target=run, daemon=True, name="Scanner").start()

def start_auto_trade():
    print("[BOOT] AutoTrade (Scalper+Trader) gestartet ✅")

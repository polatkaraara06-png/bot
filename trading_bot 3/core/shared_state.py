import threading, time, json
from collections import deque, defaultdict

class SharedState:
    def __init__(self):
        self.lock = threading.RLock()
        self.start_ts = time.time()
        self.ws_status = {"spot": "disconnected", "futures": "disconnected"}
        self.latency_ms = 0
        self.ticks = {}
        self.current_candles = defaultdict(lambda: {"start_ts": 0, "open": 0, "high": 0, "low": 0, "close": 0}) 
        self.candles_history = defaultdict(lambda: deque(maxlen=200)) 
        self.daycap_total = 150.0
        self.daycap_used = 0.0
        self.open_trades = {}
        self.closed_trades = deque(maxlen=50)
        self.hot_coins = []
        self.next_scan_at = 0
        self.total_profit = 0.0
        self.total_loss = 0.0

    @property
    def available(self):
        return max(0.0, self.daycap_total - self.daycap_used)

    def reset_daycap(self, total=150.0):
        with self.lock:
            self.daycap_total = float(total)
            self.daycap_used = 0.0
            print(f"[STATE] Daycap zurückgesetzt (total={self.daycap_total:.2f}, used=0.0)")

    def apply_profit(self, profit: float):
        self.total_profit += float(profit)

    def apply_loss(self, loss: float):
        self.total_loss += float(loss)

    def open_trade(self, t: dict):
        with self.lock:
            tid = t["id"]
            if tid in self.open_trades:
                return
            self.open_trades[tid] = t
            self.daycap_used += float(t.get("margin_used", 0.0))

    def close_trade(self, tid: str, exit_price: float, pnl: float, ts: float):
        with self.lock:
            t = self.open_trades.pop(tid, None)
            if not t:
                return
            
            t["exit_price"] = float(exit_price)
            t["pnl"] = float(pnl)
            t["close_ts"] = ts
            self.closed_trades.append(t)
            
            margin_to_release = float(t.get("margin_used", 0.0))
            self.daycap_used -= margin_to_release
            if self.daycap_used < 0:
                self.daycap_used = 0.0

            if pnl >= 0:
                self.apply_profit(pnl)
            else:
                self.apply_loss(pnl)

    def upsert_tick(self, market: str, symbol: str, price: float, ts: float):
        with self.lock:
            self.ticks[(market.lower(), symbol.upper())] = {"price": float(price), "ts": ts}
            self.latency_ms = max(0, int((time.time() - ts) * 1000))
            
    def get_current_candle_state(self, key):
        with self.lock:
            return self.current_candles[key]

    def update_candle_state(self, key, state):
        with self.lock:
            self.current_candles[key] = state

    def add_candle(self, market: str, symbol: str, interval: int, cndl: dict):
        key = (market, symbol, interval)
        with self.lock:
            self.candles_history[key].append(cndl)

    def get_historical_candles(self, market: str, symbol: str, interval: int):
        key = (market, symbol, interval)
        with self.lock:
            return list(self.candles_history[key])

    def get_latest_candle_count(self, market: str ="futures", symbol: str = "BTCUSDT", interval: int = 300) -> int:
        key = (market, symbol, interval)
        with self.lock:
            return len(self.candles_history[key])

    def get_used_margin_by_strategy(self, strategy: str) -> float:
        with self.lock:
            used = 0.0
            for t in self.open_trades.values():
                if t.get("strategy") == strategy:
                    used += float(t.get("margin_used", 0.0))
            return used

    def snapshot(self):
        with self.lock:
            ws_stat = self.ws_status
            if not isinstance(ws_stat, dict):
                ws_stat = {"spot": str(ws_stat), "futures": "?"}
            
            current_pnl = 0.0
            open_trades_list = []
            for t in self.open_trades.values():
                open_trades_list.append(dict(t))
            
            candle_count = self.get_latest_candle_count()

            return {
                "ws_status": dict(ws_stat),
                "latency_ms": self.latency_ms,
                "ticks": {f"{m.lower()}:{s.upper()}": d for (m, s), d in self.ticks.items()},
                "accounts": {
                    "daycap": {"total": self.daycap_total, "used": self.daycap_used},
                    "total_pnl": self.total_profit + self.total_loss + current_pnl
                },
                "open_trades": list(self._last_n(open_trades_list, 5)),
                "closed_trades": list(self._last_n(self.closed_trades, 5)),
                "hot_coins": list(self.hot_coins[:10]),
                "next_scan_at": self.next_scan_at,
                "candle_count": candle_count
            }

    def _last_n(self, iterable, n):
        arr = list(iterable)
        return arr[-n:] if len(arr) > n else arr

    def summary(self):
        total_pnl = self.total_profit + self.total_loss
        return {
            "Daycap": round(self.daycap_total, 2),
            "Verfügbar": round(self.available, 2),
            "Gesamt Gewinn": round(self.total_profit, 2),
            "Gesamt Verlust": round(self.total_loss, 2),
            "Gewinn/Verlust (gesamt)": round(total_pnl, 2),
        }

shared_state = SharedState()

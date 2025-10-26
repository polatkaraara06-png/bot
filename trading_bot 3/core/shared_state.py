import threading, time, json
from collections import deque, defaultdict

class SharedState:
    def __init__(self):
        self.lock = threading.RLock()
        self.start_ts = time.time()
        self.ws_status = {"spot": "disconnected", "futures": "disconnected"}
        self.latency_ms = 0
        self.ticks = {}
        self.candles = defaultdict(lambda: deque(maxlen=500))
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
            self.daycap_used -= float(t.get("margin_used", 0.0))
            if pnl >= 0:
                self.apply_profit(pnl)
            else:
                self.apply_loss(pnl)

    def upsert_tick(self, market: str, symbol: str, price: float, ts: float):
        with self.lock:
            self.ticks[(market.lower(), symbol.upper())] = {"price": float(price), "ts": ts}

    def add_candle(self, market: str, symbol: str, cndl: dict):
        with self.lock:
            self.candles[(market.lower(), symbol.upper())].append(cndl)

    def snapshot(self):
        with self.lock:
            ws_stat = self.ws_status
            # ensure dict type (avoid "error:str" issues)
            if not isinstance(ws_stat, dict):
                ws_stat = {"spot": str(ws_stat), "futures": "?"}
            return {
                "ws_status": dict(ws_stat),
                "latency_ms": self.latency_ms,
                "ticks": {f"{m.lower()}:{s.upper()}": d for (m, s), d in self.ticks.items()},
                "accounts": {
                    "daycap": {"total": self.daycap_total, "used": self.daycap_used},
                    "total_pnl": self.total_profit + self.total_loss
                },
                "open_trades": list(self._last_n(self.open_trades.values(), 5)),
                "closed_trades": list(self._last_n(self.closed_trades, 5)),
                "hot_coins": list(self.hot_coins[:10]),
                "next_scan_at": self.next_scan_at
            }

    def _last_n(self, iterable, n):
        if isinstance(iterable, dict):
            iterable = iterable.values()
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

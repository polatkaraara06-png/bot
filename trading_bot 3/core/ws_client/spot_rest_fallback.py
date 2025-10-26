
import threading, time, requests
from core.shared_state import shared_state

SPOT_SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT"]

def _poll_loop():
    print("[REST-SPOT] Fallback aktiviert – zieht Preise alle 2s über HTTPS.")
    while True:
        try:
            for s in SPOT_SYMBOLS:
                r = requests.get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={s}", timeout=3)
                data = r.json()
                if data.get("result") and data["result"].get("list"):
                    last = float(data["result"]["list"][0]["lastPrice"])
                    shared_state.upsert_tick("spot", s, last, time.time())
            shared_state.ws_status["spot"] = "rest-active"
        except Exception as e:
            shared_state.ws_status["spot"] = f"rest-error:{e}"
        time.sleep(2)

def start_rest_spot():
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()

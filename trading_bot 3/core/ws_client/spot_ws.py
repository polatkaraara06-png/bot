import os, json, time, socket, threading
from websocket import WebSocketApp
from dotenv import load_dotenv
from ..shared_state import shared_state

_orig_getaddrinfo = socket.getaddrinfo
def _only_ipv4(*a, **k):
    return [r for r in _orig_getaddrinfo(*a, **k) if r[0] == socket.AF_INET]
socket.getaddrinfo = _only_ipv4

load_dotenv()
WSS_URL = os.getenv("WSS_URL_SPOT", "wss://stream.bybit.com/v5/public/spot")

BASE_UNIVERSE = [
    "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","ADAUSDT","DOGEUSDT",
    "TRXUSDT","MATICUSDT","DOTUSDT","LTCUSDT","BCHUSDT","ATOMUSDT","LINKUSDT",
    "XLMUSDT","XMRUSDT","APTUSDT","ARBUSDT","OPUSDT","NEARUSDT","ICPUSDT",
    "FTMUSDT","INJUSDT","SUIUSDT","HBARUSDT","ALGOUSDT","GALAUSDT","SANDUSDT",
    "AXSUSDT","APEUSDT"
]

def _process_ticker_data(data):
    topic = data.get("topic","")
    if not topic.startswith("tickers."):
        return

    arr = data.get("data")
    if isinstance(arr, dict):
        arr = [arr]
    
    now = time.time()
    
    for it in arr or []:
        sym = (it.get("symbol") or "").upper()
        last = it.get("lastPrice") or it.get("markPrice") 
        
        if sym and last:
            try:
                shared_state.upsert_tick("spot", sym, float(last), now)
            except Exception as e:
                print(f"[WSS-SPOT] ❌ Upsert-Fehler ({sym}): {e}")
    
    shared_state.ws_status["spot"] = "active"

def _on_message(ws, msg):
    try:
        data = json.loads(msg)
    except Exception as e:
        print("[WSS-SPOT] ⚠ JSON decode error:", e)
        return

    _process_ticker_data(data)
    
    if "success" in data:
        print(f"[WSS-SPOT] Ack: {data.get('ret_msg')}")

def _on_open(ws):
    subs = [f"tickers.{s}" for s in BASE_UNIVERSE]
    ws.send(json.dumps({"op": "subscribe", "args": subs}))
    shared_state.ws_status["spot"] = "subscribed" 
    print(f"[WSS-SPOT] Subscribed to {len(subs)} symbols (tickers.*)")

def _on_error(ws, e):
    shared_state.ws_status["spot"] = f"error:{e}"
    print("[WSS-SPOT] ❌", e)

def _on_close(ws, *a):
    shared_state.ws_status["spot"] = "disconnected"
    print("[WSS-SPOT] 🔌 closed")

def run():
    def loop():
        while True:
            try:
                print(f"[WSS-SPOT] Connecting to {WSS_URL}")
                ws = WebSocketApp(WSS_URL,
                    on_open=_on_open,
                    on_message=_on_message,
                    on_error=_on_error,
                    on_close=_on_close)
                ws.run_forever(ping_interval=15, ping_timeout=10)
            except Exception as e:
                print("[WSS-SPOT] crash:", e)
            time.sleep(3)
    threading.Thread(target=loop, daemon=True).start()

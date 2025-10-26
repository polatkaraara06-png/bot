import os, json, time, socket, threading
from websocket import WebSocketApp
from dotenv import load_dotenv
from ..shared_state import shared_state

# IPv4 erzwingen
orig_getaddrinfo = socket.getaddrinfo
def only_ipv4(*a, **k): 
    return [i for i in orig_getaddrinfo(*a, **k) if i[0] == socket.AF_INET]
socket.getaddrinfo = only_ipv4

load_dotenv()

# Nur ein stabiler Futures-Endpunkt, kein Loop, kein Fallback
WSS_URL = "wss://stream.bybit.com/v5/public/linear"

FUT_UNIVERSE = [s.strip() for s in os.getenv("SYMBOLS_FUT",
    "BTCUSDT,ETHUSDT,SOLUSDT,ADAUSDT,XRPUSDT,DOGEUSDT,BNBUSDT,MATICUSDT,ATOMUSDT,OPUSDT,ARBUSDT,APTUSDT,SANDUSDT,TONUSDT,LINKUSDT,HBARUSDT,LTCUSDT,TRXUSDT,SHIBUSDT,NEARUSDT,ALGOUSDT,AVAXUSDT,ETCUSDT,FTMUSDT,INJUSDT,FILUSDT,EGLDUSDT,BCHUSDT,XLMUSDT,ICPUSDT,APEUSDT,CRVUSDT,DYDXUSDT,SUIUSDT,RUNEUSDT,BLURUSDT,GALAUSDT,ONEUSDT,DOTUSDT").split(",") if s.strip()]

def _on_message(ws, msg):
    try:
        data = json.loads(msg)
        topic = data.get("topic", "")
        now = time.time()
        if "tickers" in topic:
            arr = data.get("data")
            if isinstance(arr, dict):
                arr = [arr]
            for it in arr or []:
                sym = it.get("symbol")
                last = it.get("lastPrice") or it.get("price")
                if sym and last:
                    shared_state.upsert_tick("futures", sym, float(last), now)
                    shared_state.ws_status["futures"] = "connected"
        elif "kline." in topic:
            arr = data.get("data")
            if isinstance(arr, dict):
                arr = [arr]
            for it in arr or []:
                sym = it.get("symbol") or it.get("s")
                if not sym:
                    continue
                cndl = {
                    "ts": float(it.get("start", it.get("t", now))),
                    "o": float(it.get("open", it.get("o", 0))),
                    "h": float(it.get("high", it.get("h", 0))),
                    "l": float(it.get("low", it.get("l", 0))),
                    "c": float(it.get("close", it.get("c", 0))),
                    "v": float(it.get("volume", it.get("v", 0))),
                }
                shared_state.add_candle("futures", sym, cndl)
    except Exception as e:
        shared_state.ws_status["futures"] = f"error:{e}"
        print("[WSS-FUTURES] ⚠️ Fehler im Message-Handler:", e)

def _on_open(ws):
    subs = [f"tickers.{s}" for s in FUT_UNIVERSE]
    ws.send(json.dumps({"op": "subscribe", "args": subs}))
    ksubs = [f"kline.1.{s}" for s in FUT_UNIVERSE[:50]]
    ws.send(json.dumps({"op": "subscribe", "args": ksubs}))
    shared_state.ws_status["futures"] = "subscribed"
    print(f"[WSS-FUTURES] Subscribed to {len(FUT_UNIVERSE)} symbols.")

def _on_close(ws, *a):
    shared_state.ws_status["futures"] = "disconnected"
    print("[WSS-FUTURES] Closed ❌ Kein Reconnect, reiner WSS-Modus.")

def run():
    def _runner():
        print(f"[WSS-FUTURES] Verbinde mit {WSS_URL}")
        ws = WebSocketApp(WSS_URL, on_open=_on_open, on_message=_on_message, on_close=_on_close)
        ws.run_forever(ping_interval=20, ping_timeout=10)
    threading.Thread(target=_runner, daemon=True, name="FuturesWS").start()

import os, json, time, socket, threading
from websocket import WebSocketApp
from dotenv import load_dotenv
from ..shared_state import shared_state

_orig_getaddrinfo = socket.getaddrinfo
def _only_ipv4(*a, **k):
    return [r for r in _orig_getaddrinfo(*a, **k) if r[0] == socket.AF_INET]
socket.getaddrinfo = _only_ipv4

load_dotenv()
WSS_URL = os.getenv("WSS_URL_FUTURES", "wss://stream.bybit.com/v5/public/linear")

CANDLE_UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "TRXUSDT", "MATICUSDT", "DOTUSDT"]

def _process_message(data):
    topic = data.get("topic","")
    
    # 1. Ticker-Daten (für den Preis-Scan)
    if topic.startswith("tickers."):
        arr = data.get("data")
        if isinstance(arr, dict): arr = [arr]
        now = time.time()
        for it in arr or []:
            sym = (it.get("symbol") or "").upper()
            last = it.get("lastPrice") or it.get("markPrice") 
            if sym and last:
                shared_state.upsert_tick("futures", sym, float(last), now)
        shared_state.ws_status["futures"] = "active"

    # 2. Kerzen-Daten (für Chart-Analyse / MTF)
    elif topic.startswith("kline.5."): 
        # [FIX] Liest die Kerzen-Daten direkt aus dem 'data'-Feld
        arr = data.get("data") 
        if isinstance(arr, dict): arr = [arr]
        for it in arr or []:
            # 'confirm' ist jetzt ein String, der entweder True oder False als booleschen Wert darstellt
            is_confirmed = str(it.get('confirm')).lower() == 'true' 
            symbol = it.get('symbol')
            
            # WICHTIG: Wir speichern die Kerze NUR, wenn sie abgeschlossen ist (confirm=True)
            if is_confirmed and symbol:
                c = {
                    'open': float(it['open']),
                    'high': float(it['high']),
                    'low': float(it['low']),
                    'close': float(it['close']),
                    'volume': float(it['volume']),
                    'end_ts': int(it['end']),
                }
                shared_state.add_candle("futures", symbol, c)
                print(f"[WSS-FUTURES] Kerze gespeichert: {symbol} @ {c['close']:.2f}")


def _on_message(ws, msg):
    try:
        data = json.loads(msg)
    except Exception as e:
        print("[WSS-FUTURES] ⚠ JSON decode error:", e)
        return

    _process_message(data)
    
    if "success" in data:
        print(f"[WSS-FUTURES] Ack: {data.get('ret_msg')}")

def _on_open(ws):
    ticker_subs = [f"tickers.{s}" for s in CANDLE_UNIVERSE]
    candle_subs = [f"kline.5.{s}" for s in CANDLE_UNIVERSE]

    ws.send(json.dumps({"op": "subscribe", "args": ticker_subs + candle_subs}))
    shared_state.ws_status["futures"] = "subscribed"
    print(f"[WSS-FUTURES] Subscribed to {len(CANDLE_UNIVERSE)} symbols and {len(CANDLE_UNIVERSE)} candles.")

def _on_error(ws, e):
    shared_state.ws_status["futures"] = f"error:{e}"
    print("[WSS-FUTURES] ❌", e)

def _on_close(ws, *a):
    shared_state.ws_status["futures"] = "disconnected"
    print("[WSS-FUTURES] 🔌 closed")

def run():
    def loop():
        while True:
            try:
                print(f"[WSS-FUTURES] Verbinde mit {WSS_URL}")
                ws = WebSocketApp(WSS_URL,
                    on_open=_on_open,
                    on_message=_on_message,
                    on_error=_on_error,
                    on_close=_on_close)
                ws.run_forever(ping_interval=15, ping_timeout=10)
            except Exception as e:
                print("[WSS-FUTURES] crash:", e)
            time.sleep(3)
    threading.Thread(target=loop, daemon=True).start()

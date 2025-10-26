import requests
import time
from core.shared_state import shared_state

BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline"
LIMIT = 200 # Anzahl der zu ladenden Kerzen
INTERVAL_MINUTES = 5

def load_historical_candles(symbol: str, market: str = "futures"):
    print(f"[API] Lade historische {INTERVAL_MINUTES}m Kerzen für {symbol} ({market})...")
    
    # Bybit erwartet 'linear' für Futures USDT Perpetual
    category = "linear" if market == "futures" else "spot"
    
    params = {
        "category": category,
        "symbol": symbol,
        "interval": str(INTERVAL_MINUTES),
        "limit": LIMIT
    }
    
    try:
        response = requests.get(BYBIT_KLINE_URL, params=params, timeout=10)
        response.raise_for_status() # Löst einen Fehler aus, wenn die API nicht 200 OK zurückgibt
        data = response.json()
        
        if data.get("retCode") == 0 and data.get("result", {}).get("list"):
            candle_list = data["result"]["list"]
            
            # Wichtig: Bybit liefert die neuesten Kerzen zuerst, wir brauchen sie aber von alt nach neu
            candle_list.reverse() 
            
            count = 0
            for item in candle_list:
                # Format: [timestamp_ms, open, high, low, close, volume, turnover]
                if len(item) >= 6:
                    ts_seconds = int(item[0]) // 1000
                    candle_data = {
                        "start_ts": ts_seconds,
                        "open": float(item[1]),
                        "high": float(item[2]),
                        "low": float(item[3]),
                        "close": float(item[4]),
                        # Volumen ist optional, wird hier nicht benötigt
                    }
                    shared_state.add_candle(market, symbol, INTERVAL_MINUTES * 60, candle_data)
                    count += 1
            print(f"[API] {count} Kerzen für {symbol} geladen.")
            return True
        else:
            print(f"[API] Fehler beim Laden für {symbol}: {data.get('retMsg', 'Unbekannter Fehler')}")
            
    except requests.exceptions.RequestException as e:
        print(f"[API] Netzwerkfehler beim Laden für {symbol}: {e}")
    except Exception as e:
        print(f"[API] Unbekannter Fehler beim Verarbeiten für {symbol}: {e}")
        
    return False

def load_all_histories(universe: list):
    """Lädt historische Daten für alle Symbole im Universum."""
    loaded_count = 0
    total_count = len(universe)
    
    for symbol in universe:
        # Lade Futures-Daten (primär für Analyse)
        if load_historical_candles(symbol, "futures"):
            loaded_count += 1
        
        # Füge kleine Pause hinzu, um API-Rate-Limits zu vermeiden
        time.sleep(0.1) 
        
    print(f"[API] Historische Kerzen für {loaded_count}/{total_count} Symbole geladen.")


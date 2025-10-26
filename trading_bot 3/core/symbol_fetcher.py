import os

def get_dynamic_symbols(limit=50):
    """
    Liefert IMMER ein Tuple (spot_symbols, futures_symbols).
    Falls nur eine Liste verfügbar ist, wird sie für beide Märkte verwendet.
    COAIUSDT wird NICHT erzwungen (das macht start.py), damit diese Funktion generisch bleibt.
    """
    # Beispiel: lies aus ENV oder statischer Fallback
    env_list = os.getenv("DYNAMIC_SYMBOLS", "")
    if env_list.strip():
        syms = [s.strip().upper() for s in env_list.split(",") if s.strip()]
    else:
        # Minimaler Fallback: bekannte USDT-Paare
        syms = ["BTCUSDT","ETHUSDT","SOLUSDT","PEPEUSDT","FLOKIUSDT","DOGEUSDT","SHIBUSDT","XRPUSDT","BTTUSDT","GALAUSDT"]

    syms = list(dict.fromkeys(syms))[:limit]  # uniq + limit
    return (syms, syms)

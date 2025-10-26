import datetime

# Tageslimit-Startwert
DAY_CAP_DEFAULT = 175.0

def _today_key():
    return datetime.date.today().isoformat()

def _ensure_bucket(shared_state, market: str):
    """
    Stellt sicher, dass es für den gegebenen Markt (z. B. "spot")
    einen Tages-Bucket gibt, mit Feldern:
      - date: yyyy-mm-dd
      - used: heute bereits verwendeter Betrag
      - cap : aktuelles Tageslimit
    """
    with shared_state.lock:
        limits = shared_state.accounts.setdefault("limits", {})
        bucket = limits.setdefault(market, {})
        # Tageswechsel → reset used und setze Basis-Cap, falls nicht vorhanden
        if bucket.get("date") != _today_key():
            bucket["date"] = _today_key()
            bucket["used"] = 0.0
            # falls cap schon mal erhöht wurde, behalten; sonst Default
            bucket["cap"] = float(bucket.get("cap", DAY_CAP_DEFAULT))
        # Migration: falls cap fehlt (Altzustand), nachrüsten
        if "cap" not in bucket:
            bucket["cap"] = DAY_CAP_DEFAULT
        return bucket

def can_spend_today(shared_state, market: str, _cap_param: float, amount: float) -> bool:
    """
    Prüft, ob 'amount' noch innerhalb des heutigen DayCaps liegt.
    _cap_param wird aus Legacy-Gründen ignoriert und durch den aktuellen bucket['cap'] ersetzt.
    """
    bucket = _ensure_bucket(shared_state, market)
    return (float(bucket["used"]) + float(amount)) <= float(bucket["cap"])

def register_spend_today(shared_state, market: str, amount: float):
    """
    Erhöht 'used' um amount (z. B. eingesetztes Kapital des Trades).
    """
    bucket = _ensure_bucket(shared_state, market)
    with shared_state.lock:
        bucket["used"] = float(bucket["used"]) + float(amount)

def remaining_today(shared_state, market: str, _cap_param: float) -> float:
    """
    Gibt die verbleibende Kapazität für heute zurück (cap - used).
    _cap_param ist legacy und wird ignoriert.
    """
    bucket = _ensure_bucket(shared_state, market)
    return max(0.0, float(bucket["cap"]) - float(bucket["used"]))

def adjust_day_cap(shared_state, market: str, _base_cap: float, profit: float):
    """
    Erhöht das DayCap um 50% des Profits, wenn profit > 0.
    Zusätzlich wird 'used' leicht entlastet (optional), damit kurzfristig Luft entsteht.
    """
    bucket = _ensure_bucket(shared_state, market)
    if float(profit) > 0.0:
        bonus = 0.5 * float(profit)  # +50% des Gewinns auf das Limit
        with shared_state.lock:
            bucket["cap"] = float(bucket["cap"]) + bonus
            # optionale Entlastung (kannst du entfernen, wenn du das nicht willst)
            bucket["used"] = max(0.0, float(bucket["used"]) - 0.5 * bonus)

# (Optional) Helper, um Status für Dashboard/Snapshots zu lesen
def get_daycap_status(shared_state, market: str):
    bucket = _ensure_bucket(shared_state, market)
    with shared_state.lock:
        return {
            "date": bucket.get("date"),
            "used": float(bucket.get("used", 0.0)),
            "cap": float(bucket.get("cap", DAY_CAP_DEFAULT)),
        }


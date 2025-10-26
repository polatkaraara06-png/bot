import core.force_ipv4
import os, importlib, threading, time, webbrowser, shutil

print("=== CrazyBot Unified Start ===")

# 🧹 Cache löschen
def _purge_pycache():
    for root, dirs, files in os.walk("."):
        if "__pycache__" in dirs:
            shutil.rmtree(os.path.join(root, "__pycache__"), ignore_errors=True)
_purge_pycache()
print("Cache gelöscht.\n")

# === Core-Module laden ===
from core.shared_state import shared_state

try:
    from core.ws_client.spot_ws import run as run_spot_ws
except Exception:
    def run_spot_ws(): pass
try:
    from core.ws_client.futures_ws import run as run_futures_ws
except Exception:
    def run_futures_ws(): pass

from core.scanner import start_scanner_thread, start_auto_trade
from core.ai.online_rl import start_online_rl_thread, agent

# === Boot-Sequenz ===
def boot_all():
    with shared_state.lock:
        shared_state.daycap_total = 150.0
        shared_state.daycap_used  = 0.0

    print(f"[BOOT] Daycap zurückgesetzt (total={shared_state.daycap_total:.2f}, used=0.0)")

    # Starte Spot & Futures WebSockets
    threading.Thread(target=run_spot_ws, daemon=True, name="SpotWS").start()
    threading.Thread(target=run_futures_ws, daemon=True, name="FuturesWS").start()
    print("[BOOT] Websocket-Feeds gestartet")

    # Starte Scanner & AutoTrader
    start_scanner_thread(scan_interval=10, max_open_per_scan=3, margin_per_trade=15.0)
    start_auto_trade()
    print("[SCAN] Scanner Thread läuft ✅")
    print("[BOOT] AutoTrade (Scalper+Trader) gestartet ✅")

    # Starte Online Reinforcement Learning Agent
    start_online_rl_thread()
    perf = getattr(agent, "performance_ewm", 0.0)
    print(f"[BOOT] RLAgent aktiv (Level={agent.level}, Perf={perf:+.2f})")

# === Dashboard starten (im selben Prozess!) ===
def start_dashboard():
    from dashboard import webapp
    url = "http://127.0.0.1:8050/"
    print(f"[DASHBOARD] Läuft unter {url}")
    # Browser automatisch öffnen (optional)
    try:
        threading.Thread(target=lambda: (time.sleep(3), webbrowser.open(url)), daemon=True).start()
    except Exception as e:
        print(f"[DASHBOARD] Browser-Open fehlgeschlagen: {e}")
    webapp.app.run(host="0.0.0.0", port=8050, debug=False, use_reloader=False)

# === Main ===
if __name__ == "__main__":
    # Module vorladen (zeigt eventuelle Fehler früh)
    for mod in ("core.shared_state","core.paper_trader","core.ai.online_rl","dashboard.webapp"):
        try:
            m = importlib.import_module(mod)
            print(f"Modul geladen: {mod} → {os.path.abspath(m.__file__)}")
        except Exception as e:
            print(f"Fehler beim Laden von {mod}: {e}")

    boot_all()

    # Dashboard in eigenem Thread (gleicher Prozess)
    threading.Thread(target=start_dashboard, daemon=True, name="Dashboard").start()

    # Hauptprozess aktiv halten
    while True:
        time.sleep(5)


import threading, time
from core.ai import online_rl

def monitor_loop():
    while True:
        try:
            a = online_rl.agent
            info = {
                "level": getattr(a, "level", 0),
                "knowledge": getattr(a, "knowledge", 0.0),
                "performance": getattr(a, "performance_ewm", 0.0),
            }
            print(f"[MONITOR] Knowledge={info['knowledge']:.2f} | Level={info['level']} | Perf={info['performance']:+.3f}")
        except Exception as e:
            print("[MONITOR] Fehler:", e)
        time.sleep(30)

def start_monitor():
    threading.Thread(target=monitor_loop, daemon=True).start()
    print("[MONITOR] Knowledge-Monitor aktiv ✅")

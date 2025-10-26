import os, json, time, threading
from core.ai.learning_module import RLAgent

EXPERIENCE_PATH = "data/experience.jsonl"
agent = RLAgent.load()
_buffer = []
_last_save = 0.0

def add_experience(symbol, market, action, reward, features):
    global _last_save
    exp = {
        "ts": time.time(),
        "symbol": symbol,
        "market": market,
        "action": action,
        "reward": float(reward),
        "features": {k: (features or {}).get(k) for k in ("trend","vol","atr_pct")}
    }
    _buffer.append(exp)
    if len(_buffer) > 500:
        _buffer.pop(0)

    agent.consider_xp(reward=float(reward), features={"symbol":symbol,"market":market, **exp["features"]})

    now = time.time()
    if now - _last_save > 10:
        agent.save()
        _last_save = now

    os.makedirs("data", exist_ok=True)
    with open(EXPERIENCE_PATH, "a") as f:
        json.dump(exp, f); f.write("\n")

    print(f"[ONLINE_RL] learn reward={reward:+.3f} xp={agent.xp:.1f}/{agent.xp_to_next:.0f} lvl={agent.level}")

def _loop():
    while True:
        time.sleep(15)
        try:
            agent.save()
            print(f"[ONLINE_RL] snapshot lvl={agent.level} xp={agent.xp:.1f}/{agent.xp_to_next:.0f} perf={agent.performance_ewm:+.3f}")
        except Exception as e:
            print("[ONLINE_RL] save-error:", e)

def start_online_rl_thread():
    t = threading.Thread(target=_loop, daemon=True, name="RLTrainer")
    t.start()
    print("[ONLINE_RL] Live-Training gestartet ✅")
    return t

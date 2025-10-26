import os, pickle, json, hashlib, time

MODEL_PATH = "models/rl_model.pkl"
STATE_PATH = "data/curriculum_state.json"

class RLAgent:
    def __init__(self):
        self.level = 0
        self.xp = 0.0
        self.xp_to_next = 100.0
        self.knowledge = 0.0
        self.performance_ewm = 0.0
        self.alpha = 0.05
        self.last_learn_ts = 0.0
        self._recent_fps = []

    def _fingerprint(self, features: dict) -> str:
        s = json.dumps(features or {}, sort_keys=True, separators=(",",":"))
        return hashlib.sha1(s.encode()).hexdigest()[:12]

    def consider_xp(self, reward: float, features: dict):
        r = max(-2.0, min(2.0, float(reward)))
        sig = abs(r) / 2.0
        if sig < 0.05:
            return
        fp = self._fingerprint({k: (features or {}).get(k) for k in ("symbol","market","trend","vol","atr_pct")})
        novelty = 1.0
        if fp in self._recent_fps:
            novelty = 0.25
        self._recent_fps.append(fp)
        if len(self._recent_fps) > 200:
            self._recent_fps.pop(0)
        xp_gain = 50.0 * sig * (0.5 + 0.5*novelty)
        if r < 0:
            xp_gain *= 0.7
        self.xp += xp_gain
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.level += 1
            self.xp_to_next = min(1000.0, self.xp_to_next * 1.25)
        self.performance_ewm = (1-self.alpha)*self.performance_ewm + self.alpha * r
        self.knowledge = min(100.0, self.knowledge + xp_gain*0.05)
        self.last_learn_ts = time.time()

    def save(self):
        os.makedirs("models", exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self, f)
        os.makedirs("data", exist_ok=True)
        with open(STATE_PATH, "w") as f:
            json.dump({
                "level": self.level,
                "xp": round(self.xp,2),
                "xp_to_next": round(self.xp_to_next,2),
                "knowledge": round(self.knowledge,2),
                "performance_ewm": round(self.performance_ewm,4),
                "last_learn_ts": self.last_learn_ts
            }, f)

    @staticmethod
    def _upgrade(obj):
        changed = False
        defaults = RLAgent().__dict__.keys()
        for k in defaults:
            if not hasattr(obj, k):
                setattr(obj, k, getattr(RLAgent(), k))
                changed = True
        return obj, changed

    @staticmethod
    def load():
        if os.path.exists(MODEL_PATH):
            try:
                with open(MODEL_PATH, "rb") as f:
                    obj = pickle.load(f)
                if isinstance(obj, RLAgent):
                    obj, changed = RLAgent._upgrade(obj)
                    if changed:
                        obj.save()
                    return obj
            except Exception:
                pass
        a = RLAgent()
        a.save()
        return a

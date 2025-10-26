import os, pickle, json, hashlib, time, random
import numpy as np
import talib 
import pandas as pd

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
        self.min_knowledge_to_trade = 0.0
        self.min_trend_to_trade = 0.3
        self.exploration_chance = 0.05
        self.EXPLORATION_LEVERAGE = 3.0

    def get_mtf_trend_placeholder(self):
        return random.uniform(-0.1, 0.3)

    def get_candlestick_signal(self, candles: list):
        if len(candles) < 2:
            return 0
        
        df_candles = pd.DataFrame(candles)
        
        opens = np.array(df_candles['open'].tolist())
        highs = np.array(df_candles['high'].tolist())
        lows = np.array(df_candles['low'].tolist())
        closes = np.array(df_candles['close'].tolist())

        engulfing = talib.CDLENGULFING(opens, highs, lows, closes)
        harami = talib.CDLHARAMI(opens, highs, lows, closes)
        
        if engulfing[-1] > 0:
            return 2 
        if harami[-1] > 0:
            return 1 
        if engulfing[-1] < 0:
            return -2
            
        return 0

    def get_action_and_leverage(self, features: dict):
        trend = float(features.get("trend", 0.0))
        vol = float(features.get("vol", 0.0))
        
        candle_signal = self.get_candlestick_signal(features.get("candles", []))

        # 1. EXPLORATION (Zufall)
        if self.knowledge < 50.0 and random.random() < self.exploration_chance:
             action = random.choice(["buy", "sell"])
             leverage = self.EXPLORATION_LEVERAGE
             return action, leverage
             
        # 2. HAUPT-LOGIK: Muster + Trend
        
        if candle_signal > 1:
            action = "buy"
        elif candle_signal < -1:
            action = "sell"
        elif abs(trend) > self.min_trend_to_trade:
             action = "buy" if trend > 0 else "sell"
        else:
            return None, None

        # 3. RISIKOBEWERTUNG (Leverage)
        base_leverage = 2.0
        performance_boost = max(0.0, self.performance_ewm * 5.0)
        volatility_penalty = 0.03 * vol
        
        opt_leverage = max(1.0, min(10.0, base_leverage + performance_boost - volatility_penalty))
        
        return action, round(opt_leverage, 2)
    
    def get_dynamic_margin(self, strategy: str, current_total_cap: float) -> float:
        """
        [NEU] Berechnet die Margin basierend auf Vertrauen und Strategie.
        Das gesamte Daycap ist 150 USDT.
        """
        # Basis-Vertrauen: 1 (Minimum) bis 100 (Maximum)
        confidence = self.get_confidence() 
        
        if strategy == "scalper":
            # Scalper: Niedrige Basis, starker Boost bei hoher Performance
            base_margin = 15.0
            margin_boost = max(0, confidence - 50) * 0.5 
            max_margin = 35.0 # Max 35 USD für Scalper
            return min(max_margin, base_margin + margin_boost)
        
        else: # Conservative
            # Konservativ: Höhere Basis, starker Boost bei hoher Performance
            base_margin = 50.0
            margin_boost = max(0, confidence - 60) * 1.5 
            max_margin = 90.0 # Max 90 USD für Konservativ
            return min(max_margin, base_margin + margin_boost)

    def get_confidence(self):
        return min(100.0, self.knowledge)

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
        
        # [FIX] Intelligentes Lernen: Keine XP-Reduktion bei Verlusten!
        # Der Trade war informativ (novelty > 0), deshalb kein Abzug.
        # if r < 0: xp_gain *= 0.7  <--- Entfernt!
        
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

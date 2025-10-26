import numpy as np
from .base_layer import FeatureLayer

class RegimeLayer(FeatureLayer):
    name = "regime"
    def compute(self, market, symbol, tf, shared_state):
        with shared_state.lock:
            bars = shared_state.bars[tf].get((market,symbol))
        if not bars or len(bars)<20: return {}
        close = np.array([b["c"] for b in list(bars)[-20:]], dtype=float)
        x = np.arange(len(close))
        slope = float(np.polyfit(x, close, 1)[0])
        regime_flag = 1.0 if abs(slope)>0 else 0.0
        return {"trend": slope, "regime_flag": regime_flag}

import numpy as np
from .base_layer import FeatureLayer

class VolatilityLayer(FeatureLayer):
    name = "volatility"
    def compute(self, market, symbol, tf, shared_state):
        with shared_state.lock:
            bars = shared_state.bars[tf].get((market,symbol))
        if not bars or len(bars)<12: return {}
        close = np.array([b["c"] for b in list(bars)[-60:]], dtype=float)
        vol = float(np.std(np.diff(close)[-10:])) if len(close)>12 else 0.0
        return {"vol": vol}

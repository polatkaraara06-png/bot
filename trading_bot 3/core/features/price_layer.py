import numpy as np
from .base_layer import FeatureLayer

def _series(bars, field="c", n=60):
    vals = [b[field] for b in list(bars)[-n:]]
    return np.array(vals, dtype=float) if vals else np.array([], dtype=float)

class PriceLayer(FeatureLayer):
    name = "price"
    def compute(self, market, symbol, tf, shared_state):
        with shared_state.lock:
            bars = shared_state.bars[tf].get((market,symbol))
        if not bars or len(bars)<10: return {}
        close = _series(bars,"c",60)
        if len(close)<10: return {}
        ret1 = (close[-1] - close[-2])/(close[-2]+1e-9)
        ret5 = (close[-1] - close[-6])/(close[-6]+1e-9) if len(close)>6 else 0.0
        return {"ret1":float(ret1), "ret5":float(ret5)}

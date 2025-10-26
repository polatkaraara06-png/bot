import numpy as np
def zscore_from_close(bars, n=60):
    if not bars or len(bars)<30: return None
    close = np.array([b["c"] for b in list(bars)[-n:]], dtype=float)
    rets = np.diff(close)
    if len(rets)<10: return None
    mu, sd = rets.mean(), rets.std()+1e-9
    return (rets[-1]-mu)/sd

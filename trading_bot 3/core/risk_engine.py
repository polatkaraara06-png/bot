def position_size(balance: float, confidence: float, risk_frac=0.01):
    return max(0.0, balance * risk_frac * max(0.0, min(confidence,1.0)))

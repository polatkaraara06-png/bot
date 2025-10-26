def multi_objective_adjust(score: float, pnl_penalty: float, vol_spike_risk: float)->float:
    s = score - 0.2*pnl_penalty - 0.1*vol_spike_risk
    return max(0.0, min(1.0, s))

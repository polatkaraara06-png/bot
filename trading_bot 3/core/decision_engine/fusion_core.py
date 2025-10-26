from .objectives import multi_objective_adjust
from .context_switch import context_weights
from .latency_guard import allow
from .meta_decision import permitted
from ..calibration.confidence_calibrator import platt_scale

def decide(latency_ms:int, market_type:str, features:dict,
           ai_confidence:float, rl_score:float,
           tech_signal:float, sentiment_adj:float):
    if not allow(latency_ms): 
        return {"action":"HOLD","confidence":0.0,"reason":"latency_guard"}
    if not permitted():
        return {"action":"HOLD","confidence":0.0,"reason":"meta_block"}

    w = context_weights(market_type, features.get("regime_flag",0.0))
    rl01 = 0.5 + 0.5*max(-1.0, min(1.0, rl_score))  # map -1..1 → 0..1
    raw = (w["w_ai"]*ai_confidence + w["w_rl"]*rl01 + w["w_ta"]*tech_signal
           + w["w_se"]*sentiment_adj + w["w_rg"]*features.get("regime_flag",0.0))

    pnl_pen = max(0.0, min(1.0, abs(features.get("ret5",0.0))*10))
    vol_spike_risk = 1.0 if features.get("vol",0.0)>0.01 else 0.0
    fused = multi_objective_adjust(raw, pnl_pen, vol_spike_risk)
    conf = platt_scale(fused)

    action = "HOLD"
    if conf>0.65 and features.get("ret1",0.0)>=0: action="BUY"
    elif conf>0.65 and features.get("ret1",0.0)<0: action="SELL"
    return {"action":action,"confidence":conf,"reason":"fusion_v1"}

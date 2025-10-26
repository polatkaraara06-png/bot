def context_weights(market_type:str, regime_flag:float):
    if market_type=="futures" and regime_flag>=0.5:
        return dict(w_ai=0.25, w_rl=0.35, w_ta=0.25, w_se=0.05, w_rg=0.10)
    return dict(w_ai=0.35, w_rl=0.25, w_ta=0.25, w_se=0.10, w_rg=0.05)

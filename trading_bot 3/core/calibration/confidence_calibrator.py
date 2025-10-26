def platt_scale(conf: float)->float:
    conf = max(0.0, min(1.0, conf))
    return 0.05 + 0.9*conf

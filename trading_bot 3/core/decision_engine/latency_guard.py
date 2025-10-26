import os
LAT_WARN = int(os.getenv("LATENCY_MS_WARN","250"))
def allow(latency_ms:int)->bool:
    return latency_ms <= LAT_WARN

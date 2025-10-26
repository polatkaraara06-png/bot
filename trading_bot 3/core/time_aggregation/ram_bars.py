import time, math
from collections import deque
from ..shared_state import shared_state

def _bucket(ts, tf): return int(math.floor(ts/tf)*tf)

def on_tick_to_bars(tf_list=(60,180,300)):
    with shared_state.lock:
        for (m,s), tick in list(shared_state.ticks.items()):
            price, ts = tick["price"], tick["ts"]
            for tf in tf_list:
                dq = shared_state.bars[tf][(m,s)]
                if not dq or _bucket(dq[-1]["t"],tf) < _bucket(ts,tf):
                    dq.append({"t":_bucket(ts,tf),"o":price,"h":price,"l":price,"c":price})
                    while len(dq)>500: dq.popleft()
                else:
                    dq[-1]["h"] = max(dq[-1]["h"], price)
                    dq[-1]["l"] = min(dq[-1]["l"], price)
                    dq[-1]["c"] = price

""" 
Reward Engine – Teil 2.1
Berechnet Belohnungen aus abgeschlossenen Trades für das Lernsystem.
"""

import numpy as np

def trade_reward(trade):
    if not trade:
        return 0.0
    pnl = trade.get("realized_pnl", 0.0)
    duration = max(1.0, trade.get("ts_close", 1.0) - trade.get("ts_open", 0.0))
    risk = abs(trade.get("entry", 1.0) - trade.get("exit", trade.get("entry", 1.0))) / trade.get("entry", 1.0)
    reward = np.tanh(pnl / 10.0) - 0.05 * risk - 0.01 * np.log(duration)
    return float(reward)

def portfolio_reward(trades):
    if not trades:
        return 0.0
    rewards = [trade_reward(t) for t in trades]
    return float(np.mean(rewards))

def update_account_reward(shared_state):
    with shared_state.lock:
        closed = shared_state.closed_trades
        reward = portfolio_reward(closed)
        shared_state.accounts["spot"]["reward_score"] = reward
    return reward

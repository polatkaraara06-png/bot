"""
Reinforcement Agent – Teil 2.3
Einfacher Q-Learning-Agent mit Replay-Memory (optimierte Hyperparameter).
"""

import numpy as np
import random
from collections import deque

class ReinforcementAgent:
    def __init__(self, state_size=5, action_size=3, gamma=0.97, lr=0.01,   # --- gamma erhöht ---
                 epsilon=1.0, epsilon_min=0.05, epsilon_decay=0.995):       # --- langsameres Decay ---
        self.state_size = state_size
        self.action_size = action_size
        self.gamma = gamma
        self.lr = lr
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.memory = deque(maxlen=10000)
        self.q_table = np.zeros((state_size, action_size))

    def remember(self, state, action, reward, next_state):
        self.memory.append((state, action, reward, next_state))

    def act(self, state_index):
        if np.random.rand() <= self.epsilon:
            return random.randrange(self.action_size)
        q_values = self.q_table[state_index]
        return np.argmax(q_values)

    def replay(self, batch_size=32):
        if len(self.memory) < batch_size:
            return
        minibatch = random.sample(self.memory, batch_size)
        for state, action, reward, next_state in minibatch:
            target = reward + self.gamma * np.max(self.q_table[next_state])
            self.q_table[state][action] += self.lr * (target - self.q_table[state][action])
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def save(self, path="models/q_table.npy"):
        np.save(path, self.q_table)

    def load(self, path="models/q_table.npy"):
        try:
            self.q_table = np.load(path)
        except Exception:
            pass


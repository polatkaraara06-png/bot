"""
Pattern Memory – Teil 2.4
Speichert Markt-Pattern (Feature-Sequenzen) und sucht nach ähnlichen Mustern.
"""

import numpy as np
import os, pickle

class PatternMemory:
    def __init__(self, path="data/pattern_memory.pkl", max_patterns=1000):
        self.path = path
        self.max_patterns = max_patterns
        self.patterns = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "rb") as f:
                    self.patterns = pickle.load(f)
            except Exception:
                self.patterns = []

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "wb") as f:
            pickle.dump(self.patterns[-self.max_patterns:], f)

    def add_pattern(self, features: dict):
        """Speichert ein neues Pattern (Features als NumPy-Vektor)."""
        vec = np.array(list(features.values()), dtype=float)
        self.patterns.append(vec)
        self._save()

    def find_similar(self, features: dict, top_k=3):
        """Findet die ähnlichsten gespeicherten Muster."""
        if not self.patterns:
            return []
        vec = np.array(list(features.values()), dtype=float)
        sims = []
        for i, p in enumerate(self.patterns):
            dist = np.linalg.norm(vec - p)
            sims.append((i, dist))
        sims.sort(key=lambda x: x[1])
        return sims[:top_k]


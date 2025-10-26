"""
AI-Module – Teil 2.3
Kleines neuronales Netz (MLPClassifier) für Marktentscheidungen.
"""

import numpy as np
from sklearn.neural_network import MLPClassifier
import joblib
import os

class AIModule:
    def __init__(self, model_path="models/ai_supervised.pkl"):
        self.model_path = model_path
        self.model = None
        self._init_model()

    def _init_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                return
            except Exception:
                pass
        # neues Netz erstellen
        self.model = MLPClassifier(
            hidden_layer_sizes=(16, 8),
            activation="relu",
            solver="adam",
            learning_rate_init=0.001,
            max_iter=1,
            warm_start=True,
            random_state=42
        )

    def fit(self, X, y):
        """Trainiert das Netz inkrementell (online-Lernen)."""
        self.model.partial_fit(X, y, classes=np.array([0, 1, 2]))
        joblib.dump(self.model, self.model_path)

    def predict(self, X):
        """Gibt Aktionswahrscheinlichkeiten zurück."""
        probs = self.model.predict_proba(X)
        return probs

    def predict_action(self, X):
        """Wählt Aktion mit höchster Wahrscheinlichkeit."""
        probs = self.predict(X)
        action = int(np.argmax(probs, axis=1)[0])
        conf = float(np.max(probs, axis=1)[0])
        return action, conf


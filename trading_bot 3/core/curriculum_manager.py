"""
Curriculum Manager – Teil 2.5
Steuert die Lern-Stufen des Bots (Beginner → Advanced → Expert)
"""

import json, os

class CurriculumManager:
    def __init__(self, path="data/curriculum_state.json"):
        self.path = path
        self.state = {"level": "beginner", "episodes": 0, "avg_reward": 0.0}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    self.state = json.load(f)
            except Exception:
                pass

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.state, f, indent=2)

    def update(self, new_reward):
        """Aktualisiert Fortschritt und wechselt ggf. Level."""
        self.state["episodes"] += 1
        old = self.state["avg_reward"]
        n = self.state["episodes"]
        self.state["avg_reward"] = (old * (n - 1) + new_reward) / n

        avg = self.state["avg_reward"]
        if self.state["level"] == "beginner" and avg > 0.2:
            self.state["level"] = "intermediate"
        elif self.state["level"] == "intermediate" and avg > 0.5:
            self.state["level"] = "expert"

        self._save()
        return self.state

    def reset(self):
        self.state = {"level": "beginner", "episodes": 0, "avg_reward": 0.0}
        self._save()


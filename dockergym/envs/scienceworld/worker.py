#!/usr/bin/env python
"""
Worker script that runs INSIDE the Docker container.

Subclasses BaseWorker so the stdin/stdout JSON-lines protocol is handled
automatically. ScienceWorld is a text-based virtual environment for
elementary science tasks backed by a JVM process via py4j.
"""

from dockergym import BaseWorker
from scienceworld import ScienceWorldEnv


class ScienceWorldWorker(BaseWorker):
    def __init__(self):
        self.env = None

    def init_env(self, env_id: str, params: dict) -> tuple:
        task_name = env_id
        variation_idx = params.get("variation_idx")
        simplification_str = params.get("simplification_str", "")
        env_step_limit = params.get("env_step_limit", 100)
        generate_gold_path = params.get("generate_gold_path", False)

        # Create the env once (JVM startup is expensive), reuse across inits
        if self.env is None:
            self.env = ScienceWorldEnv("", envStepLimit=env_step_limit)

        # Pick a random training variation if not specified
        if variation_idx is None:
            self.env.load(task_name, 0, simplification_str, generate_gold_path)
            variation_idx = self.env.get_random_variation_train()

        self.env.load(task_name, variation_idx, simplification_str, generate_gold_path)
        obs, info = self.env.reset()

        return str(obs), 0.0, False, {
            "valid_actions": info.get("valid", []),
            "score": info.get("score", 0),
            "task_description": info.get("taskDesc", ""),
            "look": info.get("look", ""),
            "inventory": info.get("inv", ""),
            "moves": info.get("moves", 0),
            "task_name": task_name,
            "variation_idx": variation_idx,
        }

    def step_env(self, action: str) -> tuple:
        obs, reward, done, info = self.env.step(action)

        return str(obs), float(reward), bool(done), {
            "valid_actions": info.get("valid", []),
            "score": info.get("score", 0),
            "task_description": info.get("taskDesc", ""),
            "look": info.get("look", ""),
            "inventory": info.get("inv", ""),
            "moves": info.get("moves", 0),
        }

    def close_env(self):
        if self.env is not None:
            try:
                self.env.close()
            except Exception:
                pass
            self.env = None


if __name__ == "__main__":
    ScienceWorldWorker().run()

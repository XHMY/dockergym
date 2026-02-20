#!/usr/bin/env python
"""
Worker script that runs INSIDE the Docker container.

Subclasses BaseWorker so the stdin/stdout JSON-lines protocol is handled
automatically. ALFWorld is a TextWorld-based environment for household tasks.

Protocol (JSON lines):
  <- {"cmd": "init", "env_id": "...", "game_file": "/data/json_2.1.1/train/.../game.tw-pddl"}
  -> {"status": "ok", "observation": "...", "reward": 0.0, "done": false, "admissible_commands": [...], "game_file": "..."}

  <- {"cmd": "step", "action": "take apple 1"}
  -> {"status": "ok", "observation": "...", "reward": 0.0, "done": false, "won": false, "admissible_commands": [...]}
"""

from dockergym import BaseWorker

import textworld
import textworld.gym

from alfworld.agents.environment.alfred_tw_env import AlfredDemangler, AlfredInfos


class ALFWorldWorker(BaseWorker):
    def __init__(self):
        self.env = None
        self.env_done = False

    def init_env(self, env_id: str, params: dict) -> tuple:
        if self.env is not None:
            self.close_env()

        game_file = params.get("game_file", env_id)

        request_infos = textworld.EnvInfos(
            won=True,
            admissible_commands=True,
            extras=["gamefile"],
        )

        alfred_demangler = AlfredDemangler(shuffle=False)
        wrappers = [alfred_demangler, AlfredInfos]

        tw_env_id = textworld.gym.register_games(
            [game_file],
            request_infos,
            batch_size=1,
            asynchronous=False,
            max_episode_steps=200,
            wrappers=wrappers,
        )
        self.env = textworld.gym.make(tw_env_id)
        obs, info = self.env.reset()
        self.env_done = False

        admissible = list(info.get("admissible_commands", [[]])[0])

        return obs[0], 0.0, False, {
            "admissible_commands": admissible,
            "game_file": game_file,
        }

    def step_env(self, action: str) -> tuple:
        if self.env_done:
            raise RuntimeError("Episode is already done")

        obs, scores, dones, infos = self.env.step([action])

        observation = obs[0]
        score = float(scores[0])
        done = bool(dones[0])
        won = bool(infos.get("won", [False])[0])
        admissible = list(infos.get("admissible_commands", [[]])[0])

        if done:
            self.env_done = True

        return observation, score, done, {
            "won": won,
            "admissible_commands": admissible,
        }

    def close_env(self):
        if self.env is not None:
            try:
                self.env.close()
            except Exception:
                pass
            self.env = None
        self.env_done = False


if __name__ == "__main__":
    ALFWorldWorker().run()

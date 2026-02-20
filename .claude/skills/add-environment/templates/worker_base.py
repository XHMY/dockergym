#!/usr/bin/env python
"""
Worker script that runs INSIDE the Docker container.

Subclasses BaseWorker so the stdin/stdout JSON-lines protocol is handled
automatically. Only init_env() and step_env() need implementing.

Replace <EnvName> and <env_name> with the actual environment name.
"""

from dockergym import BaseWorker

# -- Import the target environment's libraries here --
# import <target_env_package>


class <EnvName>Worker(BaseWorker):
    def __init__(self):
        self.env = None

    def init_env(self, env_id: str, params: dict) -> tuple:
        """Initialize the environment for a new episode.

        Args:
            env_id: Environment instance identifier (e.g. level name, game file path).
            params: Extra parameters from the session creation request.

        Returns:
            (observation, reward, done, info)
            - observation (str): initial observation text
            - reward (float): initial reward (usually 0.0)
            - done (bool): whether the episode is immediately done (usually False)
            - info (dict): extra keys to include in the response
        """
        # Close previous environment if any
        if self.env is not None:
            self.close_env()

        # --- Create and initialize the environment ---
        # self.env = <target_env_package>.make(env_id, **params)
        # obs = self.env.reset()
        #
        # return str(obs), 0.0, False, {"env_id": env_id}

        raise NotImplementedError("Implement init_env for your environment")

    def step_env(self, action: str) -> tuple:
        """Execute one step in the environment.

        Args:
            action: The action string to execute.

        Returns:
            (observation, reward, done, info)
        """
        # --- Execute the action ---
        # obs, reward, done, info = self.env.step(action)
        #
        # return str(obs), float(reward), bool(done), {
        #     "extra_field": info.get("extra_field"),
        # }

        raise NotImplementedError("Implement step_env for your environment")

    def close_env(self):
        """Clean up the environment."""
        if self.env is not None:
            try:
                self.env.close()
            except Exception:
                pass
            self.env = None


if __name__ == "__main__":
    <EnvName>Worker().run()

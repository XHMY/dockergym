"""Base worker class for DockerGym environments.

Workers run INSIDE Docker containers and communicate with the host via
JSON lines on stdin/stdout. This module provides a base class with the
main loop already implemented — subclasses only need to implement
init_env() and step_env().

Protocol (JSON lines on stdin/stdout):
  <- {"cmd": "init", "env_id": "...", ...extra_params}
  -> {"status": "ok", "observation": "...", "reward": 0.0, "done": false, ...extras}

  <- {"cmd": "step", "action": "..."}
  -> {"status": "ok", "observation": "...", "reward": <float>, "done": <bool>, ...extras}

  -> {"status": "error", "message": "..."}

Rules:
  - Worker redirects stdout to stderr before processing (prevent log pollution)
  - Worker flushes stdout after each response
  - "observation" (str), "reward" (float), "done" (bool) are required in "ok" responses
  - Extra keys in the info dict are spread into the JSON response (flat)
  - Server accepts "score" as alias for "reward" (backward compat)
"""

import json
import sys
from abc import ABC, abstractmethod


class BaseWorker(ABC):
    """Abstract base class for DockerGym workers.

    Subclasses implement init_env() and step_env() to define environment
    behavior. The run() method handles the stdin/stdout JSON-lines protocol.
    """

    @abstractmethod
    def init_env(self, env_id: str, params: dict) -> tuple:
        """Initialize the environment.

        Args:
            env_id: Environment identifier (e.g. path to a game file).
            params: Extra parameters from the create session request.

        Returns:
            (observation, reward, done, info) where info is a dict of
            extra keys to include in the response.
        """
        ...

    @abstractmethod
    def step_env(self, action: str) -> tuple:
        """Execute one step in the environment.

        Args:
            action: The action string to execute.

        Returns:
            (observation, reward, done, info) where info is a dict of
            extra keys to include in the response.
        """
        ...

    def close_env(self):
        """Optional cleanup when the environment is closed."""
        pass

    def _send(self, obj: dict):
        """Write a JSON line to the real stdout and flush."""
        self._real_stdout.write(json.dumps(obj) + "\n")
        self._real_stdout.flush()

    def _send_error(self, message: str):
        self._send({"status": "error", "message": message})

    def run(self):
        """Main loop: read JSON commands from stdin, dispatch to handlers."""
        # Redirect stdout to stderr so library logs don't pollute the protocol
        self._real_stdout = sys.stdout
        sys.stdout = sys.stderr

        initialized = False

        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                try:
                    cmd = json.loads(line)
                except json.JSONDecodeError as e:
                    self._send_error(f"Invalid JSON: {e}")
                    continue

                command = cmd.get("cmd")

                if command == "init":
                    env_id = cmd.get("env_id", "")
                    # Everything except "cmd" and "env_id" goes into params
                    params = {k: v for k, v in cmd.items() if k not in ("cmd", "env_id")}

                    try:
                        obs, reward, done, info = self.init_env(env_id, params)
                        initialized = True
                        response = {
                            "status": "ok",
                            "observation": obs,
                            "reward": float(reward),
                            "done": bool(done),
                        }
                        response.update(info)
                        self._send(response)
                    except Exception as e:
                        self._send_error(f"Init failed: {e}")

                elif command == "step":
                    if not initialized:
                        self._send_error("Environment not initialized")
                        continue

                    action = cmd.get("action", "")

                    try:
                        obs, reward, done, info = self.step_env(action)
                        response = {
                            "status": "ok",
                            "observation": obs,
                            "reward": float(reward),
                            "done": bool(done),
                        }
                        response.update(info)
                        self._send(response)
                    except Exception as e:
                        self._send_error(f"Step failed: {e}")

                else:
                    self._send_error(f"Unknown command: {command}")

        finally:
            # Stdin closed — clean up
            try:
                self.close_env()
            except Exception:
                pass

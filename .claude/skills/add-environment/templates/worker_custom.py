#!/usr/bin/env python
"""
Worker script that runs INSIDE the Docker container.

Uses the raw JSON-lines protocol over stdin/stdout. Use this template when
BaseWorker doesn't fit (e.g. the environment library hijacks stdout).

Replace <EnvName> and <env_name> with the actual environment name.

Protocol (JSON lines):
  <- {"cmd": "init", "env_id": "...", ...extra_params}
  -> {"status": "ok", "observation": "...", ...extras}

  <- {"cmd": "step", "action": "..."}
  -> {"status": "ok", "observation": "...", "reward": 0.0, "done": false, ...extras}
"""

import json
import sys

# -- Import the target environment's libraries here --
# import <target_env_package>


def send(obj):
    """Write a JSON line to stdout and flush."""
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def send_error(message):
    send({"status": "error", "message": message})


def main():
    real_stdout = sys.stdout
    sys.stdout = sys.stderr

    env = None
    env_done = False

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            cmd = json.loads(line)
        except json.JSONDecodeError as e:
            sys.stdout = real_stdout
            send_error(f"Invalid JSON: {e}")
            sys.stdout = sys.stderr
            continue

        command = cmd.get("cmd")

        if command == "init":
            env_id = cmd.get("env_id", "")

            try:
                # Close previous env if any
                if env is not None:
                    try:
                        env.close()
                    except Exception:
                        pass

                # --- Initialize the environment ---
                # env = <target_env_package>.make(env_id)
                # obs = env.reset()
                env_done = False

                sys.stdout = real_stdout
                send({
                    "status": "ok",
                    "observation": "TODO: initial observation",
                    # Add any extra fields the consumer needs
                })
                sys.stdout = sys.stderr

            except Exception as e:
                sys.stdout = real_stdout
                send_error(f"Init failed: {e}")
                sys.stdout = sys.stderr

        elif command == "step":
            if env is None:
                sys.stdout = real_stdout
                send_error("Environment not initialized")
                sys.stdout = sys.stderr
                continue

            if env_done:
                sys.stdout = real_stdout
                send_error("Episode is already done")
                sys.stdout = sys.stderr
                continue

            action = cmd.get("action", "")

            try:
                # --- Execute the action ---
                # obs, reward, done, info = env.step(action)

                reward = 0.0
                done = False

                if done:
                    env_done = True

                sys.stdout = real_stdout
                send({
                    "status": "ok",
                    "observation": "TODO: step observation",
                    "reward": reward,
                    "done": done,
                    # Add any extra fields the consumer needs
                })
                sys.stdout = sys.stderr

            except Exception as e:
                sys.stdout = real_stdout
                send_error(f"Step failed: {e}")
                sys.stdout = sys.stderr

        else:
            sys.stdout = real_stdout
            send_error(f"Unknown command: {command}")
            sys.stdout = sys.stderr

    # Stdin closed — clean up
    if env is not None:
        try:
            env.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

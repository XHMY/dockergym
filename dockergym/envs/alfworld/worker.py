#!/usr/bin/env python
"""
Worker script that runs INSIDE the Docker container.

Reads JSON commands from stdin, writes JSON responses to stdout.
All other output (TextWorld init logs, etc.) is redirected to stderr.

Protocol (JSON lines):
  <- {"cmd": "init", "game_file": "/data/json_2.1.1/train/.../game.tw-pddl"}
  -> {"status": "ok", "observation": "...", "admissible_commands": [...], "game_file": "..."}

  <- {"cmd": "step", "action": "take apple 1"}
  -> {"status": "ok", "observation": "...", "score": 0.0, "done": false, "won": false, "admissible_commands": [...]}
"""

import contextlib
import io
import json
import os
import sys

import textworld
import textworld.gym

from alfworld.agents.environment.alfred_tw_env import AlfredDemangler, AlfredInfos


def send(obj):
    """Write a JSON line to stdout and flush."""
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def send_error(message):
    send({"status": "error", "message": message})


def main():
    # Redirect stdout to stderr so TextWorld init logs don't pollute the protocol.
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
            game_file = cmd.get("game_file")
            if not game_file:
                sys.stdout = real_stdout
                send_error("Missing game_file")
                sys.stdout = sys.stderr
                continue

            try:
                # Close previous env if any
                if env is not None:
                    try:
                        env.close()
                    except Exception:
                        pass

                request_infos = textworld.EnvInfos(
                    won=True,
                    admissible_commands=True,
                    extras=["gamefile"],
                )

                alfred_demangler = AlfredDemangler(shuffle=False)
                wrappers = [alfred_demangler, AlfredInfos]

                env_id = textworld.gym.register_games(
                    [game_file],
                    request_infos,
                    batch_size=1,
                    asynchronous=False,
                    max_episode_steps=200,
                    wrappers=wrappers,
                )
                env = textworld.gym.make(env_id)
                obs, info = env.reset()
                env_done = False

                admissible = list(info.get("admissible_commands", [[]])[0])

                sys.stdout = real_stdout
                send({
                    "status": "ok",
                    "observation": obs[0],
                    "admissible_commands": admissible,
                    "game_file": game_file,
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

            action = cmd.get("action", "look")

            try:
                obs, scores, dones, infos = env.step([action])

                observation = obs[0]
                score = float(scores[0])
                done = bool(dones[0])
                won = bool(infos.get("won", [False])[0])
                admissible = list(infos.get("admissible_commands", [[]])[0])

                if done:
                    env_done = True

                sys.stdout = real_stdout
                send({
                    "status": "ok",
                    "observation": observation,
                    "score": score,
                    "done": done,
                    "won": won,
                    "admissible_commands": admissible,
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

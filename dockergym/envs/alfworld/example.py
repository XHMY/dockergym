#!/usr/bin/env python
"""
API example: Interact with ALFWorld via the DockerGym Web API

Demonstrates single-session gameplay and concurrent multi-session usage.
Sessions are wrapped in context managers so containers are always cleaned up,
even if the script crashes mid-run.

Prerequisites:
    1. Start the API server:
       python -m dockergym.envs.alfworld --config base_config.yaml
    2. Run this example:
       python -m dockergym.envs.alfworld.example [--base-url http://localhost:8000]
"""

import argparse
from collections import Counter
import random
import sys
import time
from tqdm import tqdm
import requests
from joblib import Parallel, delayed


class Session:
    """Sync context manager that creates a session on enter and deletes it on exit."""

    def __init__(self, base_url: str, **create_kwargs):
        self.base_url = base_url
        self.create_kwargs = create_kwargs
        self.data = None
        self.session_id = None

    def __enter__(self):
        r = requests.post(f"{self.base_url}/sessions", json=self.create_kwargs)
        r.raise_for_status()
        self.data = r.json()
        self.session_id = self.data["session_id"]
        return self.data

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session_id:
            try:
                requests.delete(f"{self.base_url}/sessions/{self.session_id}")
            except Exception:
                pass
        return False


def _response_error_detail(response: requests.Response) -> str:
    """Best-effort parse of API error payloads."""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            detail = payload.get("detail") or payload.get("error_code")
            if detail:
                return str(detail)
    except ValueError:
        pass

    text = response.text.strip()
    if text:
        return text[:160]
    return f"HTTP {response.status_code}"


def _run_one_session_job(base_url: str, max_steps: int) -> dict:
    """Run one full session lifecycle: create -> step loop -> delete."""
    started_at = time.time()
    sid = None
    steps = 0
    done = False
    won = False
    score = 0.0
    task = ""

    try:
        create_response = requests.post(f"{base_url}/sessions", json={})
        if create_response.status_code >= 400:
            return {
                "success": False,
                "session_id": None,
                "steps": 0,
                "done": False,
                "won": False,
                "score": 0.0,
                "status": "create_error",
                "task": "",
                "error_code": f"HTTP_{create_response.status_code}",
                "error": _response_error_detail(create_response),
                "duration_s": time.time() - started_at,
            }

        session_data = create_response.json()
        sid = session_data["session_id"]
        observation = session_data.get("observation", "")
        task = observation.split("Your task is to: ")[-1]
        admissible = session_data.get("info", {}).get("admissible_commands", [])

        status = "max_steps"
        for step in range(1, max_steps + 1):
            action = random.choice(admissible) if admissible else "look"
            step_response = requests.post(
                f"{base_url}/sessions/{sid}/step",
                json={"action": action},
            )
            if step_response.status_code >= 400:
                return {
                    "success": False,
                    "session_id": sid,
                    "steps": steps,
                    "done": done,
                    "won": won,
                    "score": score,
                    "status": "step_error",
                    "task": task,
                    "error_code": f"HTTP_{step_response.status_code}",
                    "error": _response_error_detail(step_response),
                    "duration_s": time.time() - started_at,
                }

            result = step_response.json()
            steps = step
            done = result.get("done", False)
            won = result.get("info", {}).get("won", False)
            score = result.get("reward", score)

            if done:
                status = "done"
                break

            admissible = result.get("info", {}).get("admissible_commands", [])

        return {
            "success": True,
            "session_id": sid,
            "steps": steps,
            "done": done,
            "won": won,
            "score": score,
            "status": status,
            "task": task,
            "error_code": None,
            "error": None,
            "duration_s": time.time() - started_at,
        }
    except requests.RequestException as exc:
        return {
            "success": False,
            "session_id": sid,
            "steps": steps,
            "done": done,
            "won": won,
            "score": score,
            "status": "request_error",
            "task": task,
            "error_code": "REQUEST_EXCEPTION",
            "error": str(exc),
            "duration_s": time.time() - started_at,
        }
    except Exception as exc:
        return {
            "success": False,
            "session_id": sid,
            "steps": steps,
            "done": done,
            "won": won,
            "score": score,
            "status": "unexpected_error",
            "task": task,
            "error_code": type(exc).__name__,
            "error": str(exc),
            "duration_s": time.time() - started_at,
        }
    finally:
        if sid:
            try:
                requests.delete(f"{base_url}/sessions/{sid}")
            except Exception:
                pass


def single_session_demo(base_url: str):
    """Run one session with a random agent, using synchronous requests."""
    print("=== Single Session Demo ===\n")

    r = requests.get(f"{base_url}/environments")
    r.raise_for_status()
    env_data = r.json()
    game_files = env_data["environments"]
    print(f"Available game files: {env_data['total']}")

    chosen = random.choice(game_files)
    print(f"Chosen:  {chosen.split('/')[-2]}\n")

    with Session(base_url, env_id=chosen) as session:
        sid = session["session_id"]
        game_file = session.get("info", {}).get("game_file", "unknown")
        print(f"Session: {sid[:8]}...")
        print(f"Game:    {game_file.split('/')[-2]}")
        print(f"Task:    {session['observation'].split('Your task is to: ')[-1]}")
        print()

        admissible = session.get("info", {}).get("admissible_commands", [])
        max_steps = 30

        for step in range(1, max_steps + 1):
            action = random.choice(admissible) if admissible else "look"
            r = requests.post(
                f"{base_url}/sessions/{sid}/step", json={"action": action}
            )
            r.raise_for_status()
            result = r.json()

            obs_short = result["observation"][:100]
            print(f"  Step {step:2d}: {action}")
            print(f"           -> {obs_short}")

            if result["done"]:
                won = result.get("info", {}).get("won", False)
                outcome = "WON" if won else "LOST"
                print(f"\n  Game over: {outcome} (reward={result['reward']}) in {step} steps")
                break

            admissible = result.get("info", {}).get("admissible_commands", [])
        else:
            print(f"\n  Stopped after {max_steps} steps")

    print()


def concurrent_sessions_demo(base_url: str, n: int = 3, total_jobs: int = 100):
    """Run many sessions in parallel; each job owns one full lifecycle."""
    print(f"=== Concurrent Sessions Demo ({n} sessions) ===\n")
    max_steps = 10
    t0 = time.time()
    results = Parallel(n_jobs=n, backend="threading")(
        delayed(_run_one_session_job)(base_url, max_steps=max_steps)
        for _ in tqdm(range(total_jobs), desc="Running jobs", total=total_jobs)
    )
    elapsed = time.time() - t0

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    finished = [r for r in successes if r["done"]]
    unfinished = [r for r in successes if not r["done"]]
    wins = [r for r in finished if r["won"]]
    losses = [r for r in finished if not r["won"]]

    print(f"Processed {len(results)} jobs in {elapsed:.2f}s")
    print(
        f"  Success: {len(successes)} | Failed: {len(failures)} | "
        f"Finished: {len(finished)} | Reached max steps: {len(unfinished)}"
    )

    if successes:
        avg_steps = sum(r["steps"] for r in successes) / len(successes)
        avg_duration = sum(r["duration_s"] for r in successes) / len(successes)
        avg_score = sum(r["score"] for r in successes) / len(successes)
        print(
            f"  Won: {len(wins)} | Lost: {len(losses)} | "
            f"avg_steps={avg_steps:.2f} | avg_score={avg_score:.2f} | "
            f"avg_duration={avg_duration:.2f}s"
        )

        print("\nSample successful jobs:")
        for item in successes[: min(5, len(successes))]:
            sid = item["session_id"][:8]
            outcome = "WON" if item["won"] else ("LOST" if item["done"] else "INCOMPLETE")
            print(
                f"  {sid}... {outcome:10s} "
                f"steps={item['steps']:2d} score={item['score']:.2f} "
                f"task={item['task'][:55]}"
            )

    if failures:
        by_error = Counter(r["error_code"] or "UNKNOWN" for r in failures)
        print("\nFailure reasons:")
        for error_code, count in by_error.items():
            print(f"  {error_code}: {count}")

        print("\nSample failures:")
        for item in failures[: min(5, len(failures))]:
            sid = item["session_id"][:8] if item["session_id"] else "--------"
            print(f"  {sid}... {item['status']}: {item['error']}")
    print()

    # Final health check
    r = requests.get(f"{base_url}/health")
    r.raise_for_status()
    health = r.json()
    print(f"Health: active_sessions={health['active_sessions']}")


def main():
    parser = argparse.ArgumentParser(description="ALFWorld DockerGym API example")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=24,
        help="Number of concurrent jobs (default: 24)",
    )
    parser.add_argument(
        "--total_jobs",
        type=int,
        default=100,
        help="Total number of jobs to run (default: 100)",
    )
    args = parser.parse_args()

    # Verify server is running
    try:
        r = requests.get(f"{args.base_url}/health")
        r.raise_for_status()
        health = r.json()
        print(f"Server OK: active {health['active_sessions']} sessions, "
              f"max {health['max_sessions']} sessions\n")
    except requests.ConnectionError:
        print(f"Cannot connect to {args.base_url}. Is the server running?")
        print("Start it with: python -m dockergym.envs.alfworld")
        sys.exit(1)

    single_session_demo(args.base_url)
    concurrent_sessions_demo(args.base_url, n=args.concurrent, total_jobs=args.total_jobs)


if __name__ == "__main__":
    main()

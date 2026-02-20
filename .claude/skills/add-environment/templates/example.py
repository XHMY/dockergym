#!/usr/bin/env python
"""
API example: Interact with <EnvName> via the DockerGym Web API

Demonstrates single-session gameplay and concurrent multi-session usage.

Prerequisites:
    1. Build the Docker image (see README.md)
    2. Start the API server:
       python -m dockergym.envs.<env_name>
    3. Run this example:
       python -m dockergym.envs.<env_name>.example [--base-url http://localhost:8000]

Replace <EnvName> and <env_name> with the actual environment name.
"""

import argparse
from collections import Counter
import random
import sys
import time

import requests
from joblib import Parallel, delayed
from tqdm import tqdm


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


def single_session_demo(base_url: str, max_steps: int = 20):
    """Run one session, printing observations at each step."""
    print("=== Single Session Demo ===\n")

    with Session(base_url) as session:
        sid = session["session_id"]
        print(f"Session: {sid[:8]}...")
        print(f"Env:     {session['env_id']}")
        print(f"Obs:     {session['observation'][:200]}")
        print()

        for step in range(1, max_steps + 1):
            # --- Choose an action ---
            # Replace with environment-appropriate action selection
            action = "look"

            r = requests.post(
                f"{base_url}/sessions/{sid}/step",
                json={"action": action},
            )
            r.raise_for_status()
            result = r.json()

            obs_short = result["observation"][:100]
            print(f"  Step {step:2d}: {action}")
            print(f"           -> {obs_short}")

            if result["done"]:
                print(f"\n  Done! reward={result['reward']}")
                break
        else:
            print(f"\n  Stopped after {max_steps} steps")

    print()


def _run_one_job(base_url: str, max_steps: int) -> dict:
    """Run one full session lifecycle: create -> step loop -> delete."""
    started_at = time.time()
    sid = None
    steps = 0
    done = False
    score = 0.0

    try:
        r = requests.post(f"{base_url}/sessions", json={})
        if r.status_code >= 400:
            return {
                "success": False, "session_id": None, "steps": 0,
                "done": False, "score": 0.0, "status": "create_error",
                "error": r.text[:160], "duration_s": time.time() - started_at,
            }

        session = r.json()
        sid = session["session_id"]

        for step in range(1, max_steps + 1):
            action = "look"  # Replace with appropriate action
            r = requests.post(
                f"{base_url}/sessions/{sid}/step",
                json={"action": action},
            )
            if r.status_code >= 400:
                return {
                    "success": False, "session_id": sid, "steps": steps,
                    "done": done, "score": score, "status": "step_error",
                    "error": r.text[:160], "duration_s": time.time() - started_at,
                }

            result = r.json()
            steps = step
            done = result.get("done", False)
            score = result.get("reward", score)

            if done:
                break

        return {
            "success": True, "session_id": sid, "steps": steps,
            "done": done, "score": score,
            "status": "done" if done else "max_steps",
            "error": None, "duration_s": time.time() - started_at,
        }
    except Exception as exc:
        return {
            "success": False, "session_id": sid, "steps": steps,
            "done": done, "score": score, "status": "error",
            "error": str(exc), "duration_s": time.time() - started_at,
        }
    finally:
        if sid:
            try:
                requests.delete(f"{base_url}/sessions/{sid}")
            except Exception:
                pass


def concurrent_sessions_demo(base_url: str, n: int = 8, total_jobs: int = 20):
    """Run many sessions in parallel."""
    print(f"=== Concurrent Sessions Demo ({n} workers, {total_jobs} jobs) ===\n")
    max_steps = 10
    t0 = time.time()
    results = Parallel(n_jobs=n, backend="threading")(
        delayed(_run_one_job)(base_url, max_steps)
        for _ in tqdm(range(total_jobs), desc="Running jobs")
    )
    elapsed = time.time() - t0

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    print(f"Processed {len(results)} jobs in {elapsed:.2f}s")
    print(f"  Success: {len(successes)} | Failed: {len(failures)}")

    if successes:
        avg_steps = sum(r["steps"] for r in successes) / len(successes)
        avg_score = sum(r["score"] for r in successes) / len(successes)
        print(f"  avg_steps={avg_steps:.2f} | avg_score={avg_score:.2f}")

    if failures:
        for item in failures[:5]:
            sid = item["session_id"][:8] if item["session_id"] else "--------"
            print(f"  FAIL {sid}... {item['status']}: {item['error']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="<EnvName> DockerGym API example")
    parser.add_argument(
        "--base-url", default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--concurrent", type=int, default=8,
        help="Number of concurrent workers (default: 8)",
    )
    parser.add_argument(
        "--total-jobs", type=int, default=20,
        help="Total number of jobs (default: 20)",
    )
    args = parser.parse_args()

    try:
        r = requests.get(f"{args.base_url}/health")
        r.raise_for_status()
        health = r.json()
        print(f"Server OK: {health['active_sessions']} active, "
              f"max {health['max_sessions']} sessions\n")
    except requests.ConnectionError:
        print(f"Cannot connect to {args.base_url}. Is the server running?")
        print("Start it with: python -m dockergym.envs.<env_name>")
        sys.exit(1)

    single_session_demo(args.base_url)
    concurrent_sessions_demo(args.base_url, n=args.concurrent, total_jobs=args.total_jobs)


if __name__ == "__main__":
    main()

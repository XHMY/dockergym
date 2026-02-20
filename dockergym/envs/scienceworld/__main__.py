"""CLI entry point: python -m dockergym.envs.scienceworld"""

import argparse
import logging
import os

import uvicorn

from dockergym.config import ServerConfig
from dockergym.envs.scienceworld.app import create_scienceworld_app


def main():
    env_package_dir = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(description="ScienceWorld Web API (via DockerGym)")
    parser.add_argument(
        "--docker-image",
        default="scienceworld:latest",
        help="Docker image for worker containers (default: scienceworld:latest)",
    )
    parser.add_argument(
        "--max-sessions", type=int, default=64,
        help="Maximum concurrent sessions (default: 64)",
    )
    parser.add_argument(
        "--batch-window-ms", type=int, default=50,
        help="Batch window in milliseconds (default: 50)",
    )
    parser.add_argument(
        "--idle-timeout", type=int, default=120,
        help="Idle session timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port to listen on (default: 8000)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Mount the package directory so the worker script is accessible inside the container
    volumes = [
        f"{env_package_dir}:/app/scienceworld_env:ro",
    ]

    server_config = ServerConfig(
        docker_image=args.docker_image,
        worker_command=["python", "-u", "/app/scienceworld_env/worker.py"],
        volumes=volumes,
        container_label="scienceworld-session",
        max_sessions=args.max_sessions,
        batch_window_ms=args.batch_window_ms,
        idle_timeout_s=args.idle_timeout,
        host=args.host,
        port=args.port,
        title="ScienceWorld API",
    )

    app = create_scienceworld_app(server_config)

    uvicorn.run(app, host=server_config.host, port=server_config.port)


if __name__ == "__main__":
    main()

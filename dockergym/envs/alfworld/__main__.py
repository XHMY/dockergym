"""CLI entry point: python -m dockergym.envs.alfworld"""

import argparse
import logging
import os
from pathlib import Path

import uvicorn

from dockergym.config import ServerConfig

from dockergym.envs.alfworld.app import create_alfworld_app


def main():
    # Package directory containing worker.py, Dockerfile, base_config.yaml, etc.
    env_package_dir = os.path.dirname(os.path.abspath(__file__))

    default_config = os.path.join(env_package_dir, "base_config.yaml")

    parser = argparse.ArgumentParser(description="ALFWorld TextWorld Web API (via DockerGym)")
    parser.add_argument(
        "--config",
        default=default_config,
        help=f"Path to ALFWorld base_config.yaml (default: {default_config})",
    )
    parser.add_argument(
        "--docker-image",
        default="alfworld-text:latest",
        help="Docker image for worker containers (default: alfworld-text:latest)",
    )
    parser.add_argument(
        "--data-volume",
        default="~/.cache/alfworld:/data:ro",
        help="Volume mount for game data (default: ~/.cache/alfworld:/data:ro)",
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=64,
        help="Maximum concurrent sessions (default: 64)",
    )
    parser.add_argument(
        "--batch-window-ms",
        type=int,
        default=50,
        help="Batch window in milliseconds (default: 50)",
    )
    parser.add_argument(
        "--idle-timeout",
        type=int,
        default=120,
        help="Idle session timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Expand the data volume path
    data_volume = args.data_volume
    parts = data_volume.split(":")
    parts[0] = str(Path(parts[0]).expanduser())
    data_volume = ":".join(parts)

    # Ensure ALFWORLD_DATA points to the host data path so that
    # discover_game_files() can resolve $ALFWORLD_DATA in base_config.yaml.
    # Inside the container this is set by the Dockerfile (ENV ALFWORLD_DATA=/data),
    # but on the host we derive it from the --data-volume argument.
    os.environ.setdefault("ALFWORLD_DATA", parts[0])

    # Build volumes list: data volume + package directory for worker.py
    volumes = [data_volume]
    volumes.append(f"{env_package_dir}:/app/alfworld_env:ro")

    server_config = ServerConfig(
        docker_image=args.docker_image,
        worker_command=["python", "-u", "/app/alfworld_env/worker.py"],
        volumes=volumes,
        container_label="alfworld-session",
        max_sessions=args.max_sessions,
        batch_window_ms=args.batch_window_ms,
        idle_timeout_s=args.idle_timeout,
        host=args.host,
        port=args.port,
        title="ALFWorld TextWorld API",
    )

    app = create_alfworld_app(server_config, alfworld_config_path=args.config)

    uvicorn.run(app, host=server_config.host, port=server_config.port)


if __name__ == "__main__":
    main()

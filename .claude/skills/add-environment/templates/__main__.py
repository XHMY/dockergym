"""CLI entry point: python -m dockergym.envs.<env_name>

Replace <EnvName> and <env_name> with the actual environment name.
"""

import argparse
import logging
import os
from pathlib import Path

import uvicorn

from dockergym.config import ServerConfig
from dockergym.envs.<env_name>.app import create_<env_name>_app


def main():
    env_package_dir = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(description="<EnvName> Web API (via DockerGym)")
    parser.add_argument(
        "--docker-image",
        default="<env_name>:latest",
        help="Docker image for worker containers (default: <env_name>:latest)",
    )
    # --- Add env-specific arguments ---
    # parser.add_argument(
    #     "--data-volume",
    #     default="~/.cache/<env_name>:/data:ro",
    #     help="Volume mount for data (default: ~/.cache/<env_name>:/data:ro)",
    # )
    # parser.add_argument(
    #     "--config",
    #     default=os.path.join(env_package_dir, "config.yaml"),
    #     help="Path to environment config file",
    # )
    parser.add_argument(
        "--max-sessions", type=int, default=1024,
        help="Maximum concurrent sessions (default: 1024)",
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

    # --- Build volumes list ---
    volumes = []

    # Mount the package directory so the worker script is accessible inside the container
    volumes.append(f"{env_package_dir}:/app/<env_name>_env:ro")

    # Mount data volumes (expand ~ in paths)
    # data_volume = args.data_volume
    # parts = data_volume.split(":")
    # parts[0] = str(Path(parts[0]).expanduser())
    # data_volume = ":".join(parts)
    # volumes.append(data_volume)

    server_config = ServerConfig(
        docker_image=args.docker_image,
        worker_command=["python", "-u", "/app/<env_name>_env/worker.py"],
        volumes=volumes,
        container_label="<env_name>-session",
        max_sessions=args.max_sessions,
        batch_window_ms=args.batch_window_ms,
        idle_timeout_s=args.idle_timeout,
        host=args.host,
        port=args.port,
        title="<EnvName> API",
    )

    app = create_<env_name>_app(server_config)  # Pass env-specific kwargs here

    uvicorn.run(app, host=server_config.host, port=server_config.port)


if __name__ == "__main__":
    main()

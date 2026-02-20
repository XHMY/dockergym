"""CLI entry point: python -m dockergym"""

import argparse
import logging

import uvicorn

from dockergym.app import create_app
from dockergym.config import ServerConfig


def main():
    parser = argparse.ArgumentParser(description="DockerGym — REST API for Docker-containerized environments")
    parser.add_argument(
        "--docker-image",
        required=True,
        help="Docker image for worker containers",
    )
    parser.add_argument(
        "--worker-command",
        required=True,
        nargs="+",
        help='Command to run inside the container (e.g. "python -u /app/worker.py")',
    )
    parser.add_argument(
        "--volume",
        action="append",
        default=[],
        dest="volumes",
        help="Volume mount in host:container[:mode] format (repeatable)",
    )
    parser.add_argument(
        "--env-file-list",
        default=None,
        help="Path to a text file listing environment IDs (one per line)",
    )
    parser.add_argument(
        "--container-label",
        default="dockergym-session",
        help="Docker label for tracking containers (default: dockergym-session)",
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=1024,
        help="Maximum concurrent sessions (default: 1024)",
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
        "--command-timeout",
        type=float,
        default=60.0,
        help="Timeout for worker commands in seconds (default: 60.0)",
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

    # Load env files from text file if provided
    env_files = []
    if args.env_file_list:
        with open(args.env_file_list) as f:
            env_files = [line.strip() for line in f if line.strip()]

    config = ServerConfig(
        docker_image=args.docker_image,
        worker_command=args.worker_command,
        volumes=args.volumes,
        env_files=env_files,
        container_label=args.container_label,
        max_sessions=args.max_sessions,
        batch_window_ms=args.batch_window_ms,
        idle_timeout_s=args.idle_timeout,
        command_timeout_s=args.command_timeout,
        host=args.host,
        port=args.port,
    )

    app = create_app(config)

    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()

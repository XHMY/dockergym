"""Generic server configuration for DockerGym."""

from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, field_validator


class ServerConfig(BaseModel):
    docker_image: str
    worker_command: List[str]
    volumes: List[str] = []  # "host:container[:mode]" strings
    env_files: List[str] = []  # Available environment IDs
    container_label: str = "dockergym-session"
    container_env: Dict[str, str] = {}
    max_sessions: int = 64
    container_stop_timeout_s: int = 2
    batch_window_ms: int = 50
    idle_timeout_s: int = 120
    command_timeout_s: float = 60.0
    host: str = "0.0.0.0"
    port: int = 8000
    title: str = "DockerGym API"
    version: str = "0.1.0"

    @field_validator("volumes")
    @classmethod
    def expand_volumes(cls, v: List[str]) -> List[str]:
        result = []
        for vol in v:
            parts = vol.split(":")
            parts[0] = str(Path(parts[0]).expanduser())
            result.append(":".join(parts))
        return result

    def parsed_volumes(self) -> Dict[str, Dict[str, str]]:
        """Parse volume strings into docker-py format."""
        vols = {}
        for vol in self.volumes:
            parts = vol.split(":")
            host_path = parts[0]
            container_path = parts[1] if len(parts) > 1 else host_path
            mode = parts[2] if len(parts) > 2 else "rw"
            vols[host_path] = {"bind": container_path, "mode": mode}
        return vols

    def translate_path(self, host_path: str) -> str:
        """Translate a host path to the corresponding container path using volume mounts."""
        for vol in self.volumes:
            parts = vol.split(":")
            host_prefix = parts[0]
            container_prefix = parts[1] if len(parts) > 1 else host_prefix
            if host_path.startswith(host_prefix):
                return container_prefix + host_path[len(host_prefix):]
        return host_path

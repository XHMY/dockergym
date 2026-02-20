"""<EnvName> API — thin wrapper around DockerGym with environment-specific hooks.

Replace <EnvName> and <env_name> with the actual environment name.
"""

import logging
import random

from fastapi import FastAPI

from dockergym.app import Hooks, create_app
from dockergym.config import ServerConfig

logger = logging.getLogger("dockergym.envs.<env_name>")


def discover_environments(config_or_path) -> list:
    """Discover available environment instances.

    This function scans data directories, reads config files, or otherwise
    enumerates the set of environment IDs that users can create sessions for.

    Returns a list of environment ID strings.
    """
    # --- Implement environment discovery ---
    # Examples:
    #   - Walk a data directory for level files
    #   - Read a YAML/JSON config listing available scenarios
    #   - Return a hardcoded list of environment IDs
    #   - Query an index file
    return []


class <EnvName>Hooks(Hooks):
    def __init__(self, server_config: ServerConfig, **env_specific_kwargs):
        self.server_config = server_config
        # Store any env-specific config
        # self.config_path = env_specific_kwargs.get("config_path")

    async def on_startup(self, app: FastAPI) -> None:
        """Discover environments and populate config.env_files."""
        logger.info("Discovering environments...")
        env_files = discover_environments(None)  # Pass your config here
        logger.info("Found %d environments", len(env_files))

        self.server_config.env_files = env_files

    async def on_create_session(self, env_id: str | None, params: dict) -> dict:
        """Build the init payload for the worker container.

        Must return a dict with at least "env_id". All keys are forwarded
        to the worker's init command.
        """
        config = self.server_config

        if env_id is None:
            candidates = config.env_files
            # --- Optional: filter candidates by params ---
            # difficulty = params.pop("difficulty", None)
            # if difficulty:
            #     candidates = [e for e in candidates if difficulty in e]
            env_id = random.choice(candidates) if candidates else ""

        # Translate host path to container path if needed
        # container_path = config.translate_path(env_id)

        return {
            "env_id": env_id,
            # Add any extra keys the worker needs
            # "game_file": container_path,
            # "seed": params.get("seed"),
        }


def create_<env_name>_app(server_config: ServerConfig, **kwargs) -> FastAPI:
    """Create a FastAPI app for <EnvName> using DockerGym."""
    hooks = <EnvName>Hooks(server_config, **kwargs)
    return create_app(server_config, hooks=hooks)

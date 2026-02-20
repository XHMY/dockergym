"""ScienceWorld API — thin wrapper around DockerGym with environment-specific hooks."""

import logging
import random

from fastapi import FastAPI

from dockergym.app import Hooks, create_app
from dockergym.config import ServerConfig

logger = logging.getLogger("dockergym.envs.scienceworld")

# Hardcoded task list — avoids requiring Java on the host.
# Source: ScienceWorld v1.2 (30 tasks across 10 topic areas).
TASK_NAMES = [
    "boil",
    "melt",
    "freeze",
    "change-the-state-of-matter-of",
    "use-thermometer",
    "measure-melting-point-known-substance",
    "measure-melting-point-unknown-substance",
    "power-component",
    "power-component-renewable-vs-nonrenewable-energy",
    "test-conductivity",
    "test-conductivity-of-unknown-substances",
    "find-living-thing",
    "find-non-living-thing",
    "find-plant",
    "find-animal",
    "grow-plant",
    "grow-fruit",
    "chemistry-mix",
    "chemistry-mix-paint-secondary-color",
    "chemistry-mix-paint-tertiary-color",
    "lifespan-longest-lived",
    "lifespan-shortest-lived",
    "lifespan-longest-lived-then-shortest-lived",
    "identify-life-stages-1",
    "identify-life-stages-2",
    "inclined-plane-determine-angle",
    "inclined-plane-friction-named-surfaces",
    "inclined-plane-friction-unnamed-surfaces",
    "mendelian-genetics-known-plant",
    "mendelian-genetics-unknown-plant",
]


class ScienceWorldHooks(Hooks):
    def __init__(self, server_config: ServerConfig):
        self.server_config = server_config

    async def on_startup(self, app: FastAPI) -> None:
        logger.info("Registering %d ScienceWorld tasks", len(TASK_NAMES))
        self.server_config.env_files = list(TASK_NAMES)

    async def on_create_session(self, env_id: str | None, params: dict) -> dict:
        if env_id is None:
            env_id = random.choice(TASK_NAMES)

        # Forward all params to the worker (variation_idx, simplification_str, etc.)
        return {"env_id": env_id, **params}


def create_scienceworld_app(server_config: ServerConfig) -> FastAPI:
    """Create a FastAPI app for ScienceWorld using DockerGym."""
    hooks = ScienceWorldHooks(server_config)
    return create_app(server_config, hooks=hooks)

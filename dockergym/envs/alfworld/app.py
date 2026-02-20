"""ALFWorld API — thin wrapper around DockerGym with ALFWorld-specific hooks."""

import json
import logging
import os
import random

import yaml
from fastapi import FastAPI

from dockergym.app import Hooks, create_app
from dockergym.config import ServerConfig

logger = logging.getLogger("dockergym.envs.alfworld")

# Duplicated from alfworld.agents.environment.alfred_tw_env so the host
# doesn't need alfworld installed (it runs inside Docker containers only).
TASK_TYPES = {
    1: "pick_and_place_simple",
    2: "look_at_obj_in_light",
    3: "pick_clean_then_place_in_recep",
    4: "pick_heat_then_place_in_recep",
    5: "pick_cool_then_place_in_recep",
    6: "pick_two_obj_and_place",
}


def discover_game_files(alfworld_config_path: str) -> list:
    """Walk the data directory to find solvable game files.

    Re-implements the logic from AlfredTWEnv.collect_game_files without
    importing alfworld (which is only installed inside the Docker image).
    """
    with open(alfworld_config_path, "r") as f:
        config = yaml.safe_load(f)

    task_types = [TASK_TYPES[t] for t in config["env"]["task_types"] if t in TASK_TYPES]

    data_paths = []
    for key in ("data_path", "eval_id_data_path", "eval_ood_data_path"):
        path = config["dataset"].get(key)
        if path:
            data_paths.append(os.path.expandvars(path))

    game_files = []
    for data_path in data_paths:
        if not os.path.isdir(data_path):
            logger.warning("Data path does not exist: %s", data_path)
            continue

        for root, dirs, files in os.walk(data_path, topdown=False):
            if "traj_data.json" not in files:
                continue

            game_file_path = os.path.join(root, "game.tw-pddl")
            if not os.path.exists(game_file_path):
                continue

            if "movable" in root or "Sliced" in root:
                continue

            # Check task type
            traj_path = os.path.join(root, "traj_data.json")
            try:
                with open(traj_path, "r") as f:
                    traj_data = json.load(f)
                if traj_data.get("task_type") not in task_types:
                    continue
            except Exception:
                continue

            # Check solvability
            try:
                with open(game_file_path, "r") as f:
                    gamedata = json.load(f)
                if not gamedata.get("solvable", False):
                    continue
            except Exception:
                continue

            game_files.append(game_file_path)

    return game_files


class ALFWorldHooks(Hooks):
    def __init__(self, alfworld_config_path: str, server_config: ServerConfig):
        self.alfworld_config_path = alfworld_config_path
        self.server_config = server_config

    async def on_startup(self, app: FastAPI) -> None:
        logger.info("Discovering game files from %s", self.alfworld_config_path)
        game_files = discover_game_files(self.alfworld_config_path)
        logger.info("Found %d game files", len(game_files))

        # Update config with discovered env_files
        self.server_config.env_files = game_files

        # Store on app state for backward-compatible access
        app.state.game_files = game_files

    async def on_create_session(self, env_id: str | None, params: dict) -> dict:
        config = self.server_config
        game_files = config.env_files

        # Handle task_type filtering (backward compat)
        task_type = params.pop("task_type", None)

        if env_id is None:
            candidates = game_files
            if task_type is not None and task_type in TASK_TYPES:
                task_name = TASK_TYPES[task_type]
                candidates = [g for g in game_files if task_name in g]
                if not candidates:
                    candidates = game_files
            env_id = random.choice(candidates) if candidates else ""

        # Translate host path to container path
        container_path = config.translate_path(env_id)

        return {"env_id": env_id, "game_file": container_path}


def create_alfworld_app(server_config: ServerConfig, alfworld_config_path: str) -> FastAPI:
    """Create a FastAPI app for ALFWorld using DockerGym."""
    hooks = ALFWorldHooks(alfworld_config_path, server_config)
    return create_app(server_config, hooks=hooks)

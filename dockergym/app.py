"""FastAPI application factory with hooks support."""

import logging
from contextlib import asynccontextmanager

import docker
from fastapi import FastAPI

from dockergym.batcher import BatchCoordinator
from dockergym.config import ServerConfig
from dockergym.errors import register_error_handlers
from dockergym.routes import router
from dockergym.session_manager import SessionManager

logger = logging.getLogger("dockergym")


class Hooks:
    """Override these methods to customize DockerGym behavior."""

    async def on_startup(self, app: FastAPI) -> None:
        """Called after core infrastructure is ready, before the server accepts requests."""
        pass

    async def on_shutdown(self, app: FastAPI) -> None:
        """Called before core infrastructure is torn down."""
        pass

    async def on_create_session(self, env_id: str | None, params: dict) -> dict:
        """Customize session creation.

        Called when a new session is requested. Return a dict that will be
        sent as the init payload to the worker container. Must contain at
        least "env_id".

        The default implementation passes env_id and params through unchanged.
        """
        return {"env_id": env_id or "", **params}


def create_app(config: ServerConfig, hooks: Hooks | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting DockerGym API server...")

        # Create Docker client
        docker_client = docker.from_env()
        app.state.docker_client = docker_client

        # Create session manager
        sm = SessionManager(
            docker_client=docker_client,
            config=config,
        )
        app.state.session_manager = sm

        # Kill any orphaned containers from a previous server run
        await sm.cleanup_orphans()

        # Create batch coordinator
        batcher = BatchCoordinator(
            session_manager=sm,
            batch_window_ms=config.batch_window_ms,
        )
        app.state.batcher = batcher

        # Store hooks on app state for routes to access
        app.state.hooks = hooks

        # Start cleanup loop
        await sm.start_cleanup_loop()

        # Call hooks
        if hooks is not None:
            await hooks.on_startup(app)

        logger.info(
            "DockerGym API ready: %d environments, max %d sessions",
            len(config.env_files),
            config.max_sessions,
        )

        yield

        # Shutdown
        logger.info("Shutting down DockerGym API server...")
        if hooks is not None:
            await hooks.on_shutdown(app)
        await sm.shutdown()
        docker_client.close()

    app = FastAPI(
        title=config.title,
        description="REST API for Docker-containerized gym environments",
        version=config.version,
        lifespan=lifespan,
    )

    register_error_handlers(app)
    app.include_router(router)

    return app

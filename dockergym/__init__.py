"""DockerGym — wrap any Docker-containerized gym-like environment into a REST API."""

from dockergym.app import Hooks, create_app
from dockergym.config import ServerConfig
from dockergym.errors import (
    ContainerError,
    NoSlotsAvailable,
    SessionAlreadyDone,
    SessionNotFound,
)
from dockergym.models import (
    CreateSessionRequest,
    EnvironmentListResponse,
    ErrorResponse,
    HealthResponse,
    SessionResponse,
    StepRequest,
    StepResponse,
)
from dockergym.session_manager import Session, SessionManager
from dockergym.batcher import BatchCoordinator
from dockergym.worker import BaseWorker

__all__ = [
    # App factory
    "create_app",
    "Hooks",
    "ServerConfig",
    # Session management
    "SessionManager",
    "Session",
    "BatchCoordinator",
    # Errors
    "ContainerError",
    "NoSlotsAvailable",
    "SessionAlreadyDone",
    "SessionNotFound",
    # Models
    "CreateSessionRequest",
    "StepRequest",
    "SessionResponse",
    "StepResponse",
    "EnvironmentListResponse",
    "HealthResponse",
    "ErrorResponse",
    # Worker
    "BaseWorker",
]

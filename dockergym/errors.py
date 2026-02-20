"""Custom exceptions and FastAPI error handlers for DockerGym."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("dockergym")


class SessionNotFound(Exception):
    """Raised when a session ID does not exist."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class NoSlotsAvailable(Exception):
    """Raised when the maximum number of sessions is reached."""

    def __init__(self, max_sessions: int):
        self.max_sessions = max_sessions
        super().__init__(f"No slots available (max {max_sessions} sessions)")


class SessionAlreadyDone(Exception):
    """Raised when trying to step a session that has already finished."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session already done: {session_id}")


class ContainerError(Exception):
    """Raised when a Docker container error occurs."""

    pass


def register_error_handlers(app):
    @app.exception_handler(SessionNotFound)
    async def session_not_found_handler(request: Request, exc: SessionNotFound):
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc), "error_code": "SESSION_NOT_FOUND"},
        )

    @app.exception_handler(NoSlotsAvailable)
    async def no_slots_handler(request: Request, exc: NoSlotsAvailable):
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc), "error_code": "NO_SLOTS_AVAILABLE"},
        )

    @app.exception_handler(SessionAlreadyDone)
    async def session_done_handler(request: Request, exc: SessionAlreadyDone):
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc), "error_code": "SESSION_ALREADY_DONE"},
        )

    @app.exception_handler(ContainerError)
    async def container_error_handler(request: Request, exc: ContainerError):
        logger.error("ContainerError: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "error_code": "CONTAINER_ERROR"},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"},
        )

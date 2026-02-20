"""Generic REST API endpoints for DockerGym."""

import random
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from dockergym.errors import ContainerError, SessionAlreadyDone
from dockergym.models import (
    CreateSessionRequest,
    EnvironmentListResponse,
    HealthResponse,
    SessionResponse,
    StepRequest,
    StepResponse,
)
from dockergym.session_manager import _extract_info

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: Request, body: CreateSessionRequest = None):
    if body is None:
        body = CreateSessionRequest()

    sm = request.app.state.session_manager
    config = sm.config
    hooks = getattr(request.app.state, "hooks", None)

    env_id = body.env_id
    params = body.params

    # Let hooks customize env selection and params
    if hooks is not None:
        init_payload = await hooks.on_create_session(env_id, params)
    else:
        # Default: pick random env_id from config.env_files if not specified
        if env_id is None and config.env_files:
            env_id = random.choice(config.env_files)
        init_payload = {"env_id": env_id or "", **params}

    session = await sm.create_session(init_payload)

    return SessionResponse(
        session_id=session.session_id,
        env_id=session.env_id,
        observation=session.observation,
        info=session.info,
        status=session.status,
        created_at=session.created_at,
        last_active_at=session.last_active_at,
    )


@router.delete("/sessions")
async def delete_all_sessions(request: Request):
    sm = request.app.state.session_manager
    deleted = await sm.delete_all_sessions()
    return {"status": "ok", "deleted": deleted, "count": len(deleted)}


@router.post("/sessions/{session_id}/step", response_model=StepResponse)
async def step_session(request: Request, session_id: str, body: StepRequest):
    sm = request.app.state.session_manager
    batcher = request.app.state.batcher

    session = sm.get_session(session_id)
    if session.status == "done":
        raise SessionAlreadyDone(session_id)

    result = await batcher.submit_step(session, body.action)

    if result.get("status") != "ok":
        raise ContainerError(result.get("message", "Step failed"))

    done = result.get("done", False)
    if done:
        session.status = "done"

    # Accept both "reward" and "score" (backward compat)
    reward = result.get("reward", result.get("score", 0.0))
    info = _extract_info(result)

    return StepResponse(
        session_id=session_id,
        observation=result.get("observation", ""),
        reward=float(reward),
        done=done,
        info=info,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(request: Request, session_id: str):
    sm = request.app.state.session_manager
    await sm.delete_session(session_id)
    return {"status": "ok", "session_id": session_id}


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(request: Request, session_id: str):
    sm = request.app.state.session_manager
    session = sm.get_session(session_id)

    return SessionResponse(
        session_id=session.session_id,
        env_id=session.env_id,
        observation=session.observation,
        info=session.info,
        status=session.status,
        created_at=session.created_at,
        last_active_at=session.last_active_at,
    )


@router.get("/environments", response_model=EnvironmentListResponse)
async def list_environments(request: Request):
    config = request.app.state.session_manager.config
    return EnvironmentListResponse(
        environments=config.env_files,
        total=len(config.env_files),
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    sm = request.app.state.session_manager
    return HealthResponse(
        status="ok",
        active_sessions=sm.active_session_count,
        max_sessions=sm.config.max_sessions,
        available_environments=len(sm.config.env_files),
    )

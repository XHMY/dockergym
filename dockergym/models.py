"""Pydantic request/response schemas for DockerGym."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# -- Requests --

class CreateSessionRequest(BaseModel):
    env_id: Optional[str] = None  # If None, server picks from env_files
    params: Dict[str, Any] = {}


class StepRequest(BaseModel):
    action: str


# -- Responses --

class SessionResponse(BaseModel):
    session_id: str
    env_id: str
    observation: str
    info: Dict[str, Any] = {}
    status: str
    created_at: datetime
    last_active_at: datetime


class StepResponse(BaseModel):
    session_id: str
    observation: str
    reward: float
    done: bool
    info: Dict[str, Any] = {}


class EnvironmentListResponse(BaseModel):
    environments: List[str]
    total: int


class HealthResponse(BaseModel):
    status: str
    active_sessions: int
    max_sessions: int
    available_environments: int


class ErrorResponse(BaseModel):
    detail: str
    error_code: str

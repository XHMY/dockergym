"""Session lifecycle and Docker container management."""

import asyncio
import json
import logging
import random
import select
import time as _time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from typing import Any, Dict, List, Optional

import docker

from dockergym.config import ServerConfig
from dockergym.errors import (
    ContainerError,
    NoSlotsAvailable,
    SessionAlreadyDone,
    SessionNotFound,
)

logger = logging.getLogger("dockergym")


@dataclass
class Session:
    session_id: str
    container: object  # docker Container
    socket: object  # attached stream
    env_id: str
    observation: str
    info: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"  # "active" | "done"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _read_buffer: str = ""
    _raw_buffer: bytes = b""


class SessionManager:
    def __init__(
        self,
        docker_client: docker.DockerClient,
        config: ServerConfig,
    ):
        self.docker_client = docker_client
        self.config = config
        self._sessions: Dict[str, Session] = {}
        self._semaphore = asyncio.Semaphore(config.max_sessions)
        self._cleanup_task: Optional[asyncio.Task] = None

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)

    def get_session(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFound(session_id)
        return session

    async def create_session(self, init_payload: dict) -> Session:
        """Create a new session with a Docker container.

        Args:
            init_payload: Dict sent as the init command to the worker.
                Must contain at least "env_id". Any extra keys are passed
                through to the worker.
        """
        if self._semaphore.locked():
            raise NoSlotsAvailable(self.config.max_sessions)
        await self._semaphore.acquire()

        try:
            env_id = init_payload.get("env_id", "")
            session_id = str(uuid.uuid4())

            # Start container
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                partial(self._start_container, session_id),
            )

            # Attach to stdin/stdout
            socket = await loop.run_in_executor(
                None,
                partial(self._attach_container, container),
            )

            session = Session(
                session_id=session_id,
                container=container,
                socket=socket,
                env_id=env_id,
                observation="",
            )
            self._sessions[session_id] = session

            # Send init command
            init_cmd = {"cmd": "init"}
            init_cmd.update(init_payload)
            response = await self.send_command(session, init_cmd)

            if response.get("status") != "ok":
                await self._kill_container(container)
                self._sessions.pop(session_id, None)
                self._semaphore.release()
                raise ContainerError(
                    f"Init failed: {response.get('message', 'unknown error')}"
                )

            session.observation = response.get("observation", "")
            # Partition standard keys from extras → info
            session.info = _extract_info(response)

            return session

        except (NoSlotsAvailable, ContainerError):
            raise
        except Exception as e:
            self._semaphore.release()
            logger.exception("Failed to create session")
            raise ContainerError(f"Failed to create session: {e}") from e

    def _start_container(self, session_id: str):
        volumes = self.config.parsed_volumes()

        container = self.docker_client.containers.run(
            self.config.docker_image,
            self.config.worker_command,
            volumes=volumes,
            environment=self.config.container_env or None,
            stdin_open=True,
            detach=True,
            auto_remove=True,
            labels={self.config.container_label: session_id},
        )
        return container

    def _attach_container(self, container):
        socket = container.attach_socket(
            params={"stdin": True, "stdout": True, "stderr": False, "stream": True}
        )
        return socket

    async def send_command(self, session: Session, command: dict) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(self._send_command_sync, session, command),
        )

    def _send_command_sync(self, session: Session, command: dict) -> dict:
        payload = json.dumps(command) + "\n"
        try:
            self._write_to_stdin(session, payload)
            response_line = self._read_from_stdout(session)
            return json.loads(response_line)
        except Exception as e:
            return {"status": "error", "message": f"Communication error: {e}"}

    def _write_to_stdin(self, session: Session, payload: str):
        """Write to container stdin via the attached socket."""
        sock = session.socket._sock if hasattr(session.socket, '_sock') else session.socket
        sock.sendall(payload.encode("utf-8"))

    def _read_from_stdout(self, session: Session, timeout: float = None) -> str:
        """Read a JSON line from container stdout via the attached socket."""
        if timeout is None:
            timeout = self.config.command_timeout_s

        sock = session.socket._sock if hasattr(session.socket, '_sock') else session.socket
        sock.setblocking(False)

        buf = session._read_buffer
        deadline = _time.time() + timeout

        while True:
            remaining = deadline - _time.time()
            if remaining <= 0:
                raise TimeoutError("Timeout reading from container")

            # Check for complete line in buffer (skip empty lines)
            while "\n" in buf:
                line, rest = buf.split("\n", 1)
                buf = rest
                line = line.strip()
                if line:
                    session._read_buffer = buf
                    return self._extract_json_line(line)

            ready, _, _ = select.select([sock], [], [], min(remaining, 1.0))
            if ready:
                data = sock.recv(4096)
                if not data:
                    raise ConnectionError("Container closed connection")
                # Accumulate raw bytes, decode only complete Docker frames
                session._raw_buffer += data
                decoded, consumed = self._decode_docker_stream(session._raw_buffer)
                session._raw_buffer = session._raw_buffer[consumed:]
                buf += decoded

    def _decode_docker_stream(self, data: bytes) -> tuple:
        """Decode Docker multiplexed stream data.

        Docker attach streams use an 8-byte header per frame:
        [stream_type(1), 0, 0, 0, size(4)] followed by the payload.

        Returns:
            (decoded_text, bytes_consumed) — stops at incomplete frames so
            the caller can buffer the remainder for the next recv().
        """
        result = []
        pos = 0

        while pos < len(data):
            # Need at least 8 bytes for a frame header
            if pos + 8 > len(data):
                break

            stream_type = data[pos]
            if stream_type not in (0, 1, 2):
                # Not a Docker frame — treat rest as raw text
                result.append(data[pos:].decode("utf-8", errors="replace"))
                pos = len(data)
                break

            size = int.from_bytes(data[pos + 4 : pos + 8], "big")

            # Need the full payload before we can decode this frame
            if pos + 8 + size > len(data):
                break

            if size > 0 and stream_type in (0, 1):  # stdout
                payload = data[pos + 8 : pos + 8 + size]
                result.append(payload.decode("utf-8", errors="replace"))
            pos += 8 + size

        return "".join(result), pos

    def _extract_json_line(self, line: str) -> str:
        """Extract valid JSON from a line that may have docker framing artifacts."""
        line = line.strip()
        try:
            json.loads(line)
            return line
        except json.JSONDecodeError:
            pass

        start = line.find("{")
        if start >= 0:
            candidate = line[start:]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        return line

    async def delete_all_sessions(self) -> list:
        """Kill all active sessions. Returns list of deleted session IDs."""
        session_ids = list(self._sessions.keys())
        deleted = []
        for sid in session_ids:
            try:
                await self.delete_session(sid)
                deleted.append(sid)
            except Exception:
                pass
        return deleted

    async def delete_session(self, session_id: str):
        session = self._sessions.pop(session_id, None)
        if session is None:
            raise SessionNotFound(session_id)

        await self._kill_container(session.container)
        self._semaphore.release()

    async def _kill_container(self, container):
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                partial(container.stop, timeout=self.config.container_stop_timeout_s),
            )
        except Exception:
            pass

    async def start_cleanup_loop(self):
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(60)
            now = datetime.now(timezone.utc)
            to_remove = []
            for sid, session in self._sessions.items():
                idle = (now - session.last_active_at).total_seconds()
                if idle > self.config.idle_timeout_s:
                    to_remove.append(sid)

            for sid in to_remove:
                logger.info("Cleaning up idle session: %s", sid)
                try:
                    await self.delete_session(sid)
                except Exception:
                    pass

    async def _kill_all_labeled_containers(self):
        """Find and kill ALL containers with the session label."""
        loop = asyncio.get_event_loop()
        try:
            containers = await loop.run_in_executor(
                None,
                partial(self.docker_client.containers.list,
                        filters={"label": self.config.container_label}),
            )
            for c in containers:
                try:
                    await loop.run_in_executor(None, c.kill)
                    logger.info("Killed orphaned container: %s", c.short_id)
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Error cleaning up labeled containers: %s", e)

    async def cleanup_orphans(self):
        """Kill any leftover containers from a previous server run."""
        await self._kill_all_labeled_containers()

    async def shutdown(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        self._sessions.clear()
        await self._kill_all_labeled_containers()


def _extract_info(response: dict) -> dict:
    """Extract extra keys from a worker response into an info dict."""
    standard_keys = {"status", "observation", "reward", "score", "done", "cmd", "env_id"}
    return {k: v for k, v in response.items() if k not in standard_keys}

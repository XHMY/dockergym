"""Auto-batching coordinator for concurrent container I/O."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from dockergym.session_manager import Session, SessionManager

logger = logging.getLogger("dockergym")


@dataclass
class PendingRequest:
    session: Session
    action: str
    future: asyncio.Future


class BatchCoordinator:
    def __init__(self, session_manager: SessionManager, batch_window_ms: int = 50):
        self.session_manager = session_manager
        self.batch_window_ms = batch_window_ms
        self._pending: List[PendingRequest] = []
        self._drain_scheduled = False
        self._lock = asyncio.Lock()

    async def submit_step(self, session: Session, action: str) -> dict:
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        async with self._lock:
            self._pending.append(PendingRequest(
                session=session,
                action=action,
                future=future,
            ))

            if not self._drain_scheduled:
                self._drain_scheduled = True
                asyncio.get_event_loop().call_later(
                    self.batch_window_ms / 1000.0,
                    lambda: asyncio.ensure_future(self._drain()),
                )

        return await future

    async def _drain(self):
        async with self._lock:
            requests = self._pending[:]
            self._pending.clear()
            self._drain_scheduled = False

        if not requests:
            return

        async def process_one(req: PendingRequest):
            try:
                async with req.session.lock:
                    command = {"cmd": "step", "action": req.action}
                    result = await self.session_manager.send_command(
                        req.session, command
                    )
                    req.session.last_active_at = datetime.now(timezone.utc)
                    if not req.future.done():
                        req.future.set_result(result)
            except Exception as e:
                if not req.future.done():
                    req.future.set_exception(e)

        await asyncio.gather(*(process_one(req) for req in requests))

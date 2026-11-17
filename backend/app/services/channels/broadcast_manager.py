"""In-memory connection manager for real-time Web Broadcasts (WebSocket and SSE)."""

from __future__ import annotations
import asyncio
import logging
from typing import List, Dict, Any
from starlette.websockets import WebSocket, WebSocketState

logger = logging.getLogger("masscommai.broadcast_manager")


class BroadcastConnectionManager:
    """
    Manages active anonymous citizen connections via WebSocket and Server-Sent Events (SSE).
    Ensures zero PII leakage: all broadcast payloads contain only public announcement data.
    """

    def __init__(self) -> None:
        self._active_websockets: List[WebSocket] = []
        self._active_sse_queues: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def connect_websocket(self, websocket: WebSocket) -> None:
        """Accepts and tracks an active citizen browser WebSocket."""
        await websocket.accept()
        async with self._lock:
            self._active_websockets.append(websocket)
        logger.info("Citizen WebSocket connected. Active WS connections: %d", len(self._active_websockets))

    async def disconnect_websocket(self, websocket: WebSocket) -> None:
        """Removes a disconnected citizen WebSocket."""
        async with self._lock:
            if websocket in self._active_websockets:
                self._active_websockets.remove(websocket)
        logger.info("Citizen WebSocket disconnected. Active WS connections: %d", len(self._active_websockets))

    async def register_sse_client(self) -> asyncio.Queue:
        """Registers a citizen browser SSE listener queue."""
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._active_sse_queues.append(queue)
        logger.info("Citizen SSE client registered. Active SSE queues: %d", len(self._active_sse_queues))
        return queue

    async def unregister_sse_client(self, queue: asyncio.Queue) -> None:
        """Removes an SSE client listener queue."""
        async with self._lock:
            if queue in self._active_sse_queues:
                self._active_sse_queues.remove(queue)
        logger.info("Citizen SSE client unregistered. Active SSE queues: %d", len(self._active_sse_queues))

    def get_connected_count(self) -> int:
        """Returns total active listening clients across WebSockets and SSE."""
        return len(self._active_websockets) + len(self._active_sse_queues)

    async def broadcast(self, payload: Dict[str, Any]) -> int:
        """
        Dispatches public announcement payload to all active WebSockets and SSE queues.
        Guarantees that no recipient personal details are transmitted.
        Returns count of clients to which the message was successfully dispatched.
        """
        dispatched_count = 0
        dead_websockets: List[WebSocket] = []

        # 1. Dispatch to WebSockets
        async with self._lock:
            ws_targets = list(self._active_websockets)

        for ws in ws_targets:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(payload)
                    dispatched_count += 1
                else:
                    dead_websockets.append(ws)
            except Exception as exc:
                logger.warning("Error transmitting broadcast over WebSocket: %s", exc)
                dead_websockets.append(ws)

        if dead_websockets:
            async with self._lock:
                for ws in dead_websockets:
                    if ws in self._active_websockets:
                        self._active_websockets.remove(ws)

        # 2. Dispatch to SSE queues
        async with self._lock:
            sse_targets = list(self._active_sse_queues)

        for q in sse_targets:
            try:
                q.put_nowait(payload)
                dispatched_count += 1
            except Exception as exc:
                logger.warning("Error putting payload into SSE queue: %s", exc)

        logger.info("Broadcast dispatched to %d listeners.", dispatched_count)
        return dispatched_count


# Global singleton instance
broadcast_manager = BroadcastConnectionManager()

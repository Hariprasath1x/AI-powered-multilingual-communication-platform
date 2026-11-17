"""Router for citizen device registration, public announcements, and real-time broadcasts."""

from __future__ import annotations
import json
import asyncio
import logging
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from starlette.websockets import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.device_token import DeviceToken
from app.models.web_broadcast import WebBroadcast
from app.models.user import User
from app.schemas.channel_config import (
    DeviceTokenCreateRequest,
    DeviceTokenResponse,
    WebBroadcastResponse,
)
from app.core.dependencies import get_current_user_optional, require_role
from app.services.channels.broadcast_manager import broadcast_manager

logger = logging.getLogger("masscommai.notifications")

router = APIRouter(
    tags=["Citizen Notifications & Broadcasts"],
)


@router.post(
    "/notifications/devices/register",
    response_model=DeviceTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register or update a citizen device push notification token",
)
def register_device_token(
    payload: DeviceTokenCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> DeviceTokenResponse:
    """
    Registers a browser Web Push subscription, FCM registration token, or APNs device token.
    Idempotently reactivates or creates the token record.
    """
    token_str = payload.token.strip()
    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device registration token cannot be empty.",
        )

    stmt = select(DeviceToken).where(DeviceToken.token == token_str)
    existing = db.execute(stmt).scalar_one_or_none()

    if existing:
        existing.is_active = True
        existing.device_type = payload.device_type
        if payload.platform_metadata:
            existing.platform_metadata = payload.platform_metadata
        if payload.audience_member_id:
            existing.audience_member_id = payload.audience_member_id
        if current_user:
            existing.user_id = current_user.id
        db.commit()
        db.refresh(existing)
        return existing

    device = DeviceToken(
        token=token_str,
        device_type=payload.device_type,
        audience_member_id=payload.audience_member_id,
        user_id=current_user.id if current_user else None,
        platform_metadata=payload.platform_metadata or {},
        is_active=True,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get(
    "/notifications/devices",
    response_model=List[DeviceTokenResponse],
    summary="List all registered citizen device tokens",
)
def list_registered_devices(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> List[DeviceTokenResponse]:
    """Administrative retrieval of active and historical citizen device tokens."""
    stmt = (
        select(DeviceToken)
        .order_by(DeviceToken.id.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


@router.get(
    "/announcements",
    response_model=List[WebBroadcastResponse],
    summary="List recent public announcements and broadcasts",
)
def get_public_announcements(
    language: Optional[str] = Query(None, description="Optional language filter (e.g. en, hi, ta)"),
    emergency_only: bool = Query(False, description="Filter for high-priority emergency alerts only"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[WebBroadcastResponse]:
    """
    Public citizen endpoint returning official public announcements.
    Privacy Guarantee: Never exposes citizen identities, emails, or phone numbers.
    """
    stmt = select(WebBroadcast).order_by(WebBroadcast.broadcast_at.desc())

    if language:
        stmt = stmt.where(WebBroadcast.language == language.strip().lower())
    if emergency_only:
        stmt = stmt.where(WebBroadcast.is_emergency.is_(True))

    stmt = stmt.limit(limit)
    broadcasts = list(db.execute(stmt).scalars().all())

    return [
        WebBroadcastResponse(
            id=b.id,
            campaign_id=b.campaign_id,
            title=b.title,
            body=b.body,
            language=b.language,
            is_emergency=b.is_emergency,
            priority=b.priority,
            connected_clients_count=b.connected_clients_count,
            broadcast_at=b.broadcast_at,
        )
        for b in broadcasts
    ]


@router.get(
    "/broadcast/sse",
    summary="Real-time Server-Sent Events stream for public announcements",
)
async def broadcast_sse_stream():
    """
    Server-Sent Events endpoint streaming live citizen emergency alerts and public updates.
    Citizens connect anonymously with zero personal data leakage.
    """
    client_queue = await broadcast_manager.register_sse_client()

    async def event_generator():
        try:
            # Initial connection greeting
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            while True:
                # Wait for next broadcast message or heartbeat
                try:
                    payload = await asyncio.wait_for(client_queue.get(), timeout=25.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat ping
                    yield f": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await broadcast_manager.unregister_sse_client(client_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.websocket("/ws/broadcast")
async def websocket_broadcast_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for bidirectional real-time citizen portal announcements.
    Broadcasts public notifications immediately when an approved campaign dispatches.
    """
    await broadcast_manager.connect_websocket(websocket)
    try:
        # Send initial confirmation
        await websocket.send_json({
            "type": "welcome",
            "message": "Connected to MassCommAI Public Broadcast Service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        while True:
            # Keep socket open and accept incoming client pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await broadcast_manager.disconnect_websocket(websocket)
    except Exception as exc:
        logger.warning("WebSocket broadcast connection terminated: %s", exc)
        await broadcast_manager.disconnect_websocket(websocket)

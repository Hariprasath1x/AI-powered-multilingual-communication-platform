"""Admin router for managing Channel Configurations, Provider Credentials, and Health Tests."""

from __future__ import annotations
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.channel_config import ChannelConfiguration
from app.schemas.channel_config import (
    ChannelConfigResponse,
    ChannelConfigUpdateRequest,
    ChannelTestRequest,
    ChannelTestResponse,
    mask_secret,
)
from app.core.dependencies import require_role
from app.services.channels import get_configured_channel, BaseChannel

logger = logging.getLogger("masscommai.admin_channels")

router = APIRouter(
    prefix="/admin/channels",
    tags=["Channel Administration"],
)


def _to_response_dto(config: ChannelConfiguration) -> ChannelConfigResponse:
    creds = config.credentials if isinstance(config.credentials, dict) else {}
    masked: Dict[str, str] = {}
    for k, v in creds.items():
        if isinstance(v, str):
            masked[k] = mask_secret(v)
        else:
            masked[k] = "********"

    return ChannelConfigResponse(
        id=config.id,
        channel=config.channel,
        is_enabled=config.is_enabled,
        provider_type=config.provider_type,
        sender_address=config.sender_address,
        sender_name=config.sender_name,
        has_credentials=bool(creds),
        masked_credentials=masked,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get(
    "",
    response_model=List[ChannelConfigResponse],
    summary="List all channel configurations and provider settings",
)
def list_channel_configurations(
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> List[ChannelConfigResponse]:
    """Retrieves all channel configurations with masked credentials."""
    stmt = select(ChannelConfiguration).order_by(ChannelConfiguration.channel.asc())
    configs = list(db.execute(stmt).scalars().all())

    # Ensure Email, SMS, WhatsApp, Push, and Web default records exist in DB if not present
    existing_channels = {c.channel for c in configs}
    modified = False

    defaults = [
        ("Email", "mock", "notifications@masscomm.gov.in", "MassCommAI Citizen Communications", {}),
        ("SMS", "mock", "GOVMSG", "Govt Citizen Alert", {}),
        ("WhatsApp", "mock", "+1555010099", "MassCommAI WhatsApp Official", {"phone_number_id": "1000000001", "waba_id": "2000000002"}),
        ("Push", "mock", "masscommai-fcm-project", "MassCommAI Citizen Push", {"project_id": "masscommai-mock-fcm"}),
        ("Web", "mock", "masscomm-broadcast-hub", "MassCommAI Web Broadcast", {}),
    ]

    for ch_name, prov, s_addr, s_name, def_creds in defaults:
        if ch_name not in existing_channels:
            cfg = ChannelConfiguration(
                channel=ch_name,
                is_enabled=True,
                provider_type=prov,
                sender_address=s_addr,
                sender_name=s_name,
                credentials=def_creds,
            )
            db.add(cfg)
            configs.append(cfg)
            modified = True

    if modified:
        db.commit()

    return [_to_response_dto(c) for c in configs]


@router.get(
    "/{channel}",
    response_model=ChannelConfigResponse,
    summary="Get configuration details for a specific channel",
)
def get_channel_configuration(
    channel: str = Path(..., description="Channel name: Email, SMS, WhatsApp, Voice"),
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> ChannelConfigResponse:
    """Retrieves details of a single channel with masked credentials."""
    stmt = select(ChannelConfiguration).where(ChannelConfiguration.channel == channel)
    config = db.execute(stmt).scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel '{channel}' configuration not found.",
        )
    return _to_response_dto(config)


@router.put(
    "/{channel}",
    response_model=ChannelConfigResponse,
    summary="Update channel provider type, enabled status, or credentials",
)
def update_channel_configuration(
    channel: str = Path(..., description="Channel name: Email, SMS"),
    payload: ChannelConfigUpdateRequest = ...,
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> ChannelConfigResponse:
    """Updates provider adapter, enable/disable toggle, or provider credentials."""
    stmt = select(ChannelConfiguration).where(ChannelConfiguration.channel == channel)
    config = db.execute(stmt).scalar_one_or_none()

    if not config:
        # Create new configuration record
        config = ChannelConfiguration(
            channel=channel,
            is_enabled=True if payload.is_enabled is None else payload.is_enabled,
            provider_type=payload.provider_type or "mock",
            sender_address=payload.sender_address,
            sender_name=payload.sender_name,
            credentials=payload.credentials or {},
        )
        db.add(config)
    else:
        if payload.is_enabled is not None:
            config.is_enabled = payload.is_enabled
        if payload.provider_type is not None:
            config.provider_type = payload.provider_type.lower().strip()
        if payload.sender_address is not None:
            config.sender_address = payload.sender_address.strip()
        if payload.sender_name is not None:
            config.sender_name = payload.sender_name.strip()
        if payload.credentials is not None:
            # Merge with existing credentials to avoid wiping out unmodified keys
            existing_creds = dict(config.credentials or {})
            for k, v in payload.credentials.items():
                if v and "****" not in str(v):  # Don't overwrite with masked string
                    existing_creds[k] = v
            config.credentials = existing_creds

    db.commit()
    db.refresh(config)
    return _to_response_dto(config)


@router.post(
    "/{channel}/test",
    response_model=ChannelTestResponse,
    summary="Send an isolated test message to verify credentials and connectivity",
)
async def test_channel_connectivity(
    channel: str = Path(..., description="Target channel: Email, SMS"),
    payload: ChannelTestRequest = ...,
    current_user: User = Depends(require_role("Admin")),
    db: Session = Depends(get_db),
) -> ChannelTestResponse:
    """Executes an isolated test transmission to destination address."""
    adapter: BaseChannel = get_configured_channel(db, channel)
    result = await adapter.send_test(
        destination=payload.destination,
        body=payload.message or "MassCommAI automated connectivity test.",
        subject=payload.subject,
    )
    return ChannelTestResponse(
        success=result.success,
        status=result.status,
        provider_name=result.provider_name,
        provider_message_id=result.provider_message_id,
        error_code=result.error_code,
        error_message=result.error_message,
        metadata=result.metadata,
    )

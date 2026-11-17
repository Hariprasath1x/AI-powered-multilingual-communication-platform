"""ChannelRegistry managing dynamic provider resolution and extensible channel registration."""

from __future__ import annotations
import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.services.channels.base import BaseChannel, ChannelSendResult
from app.services.channels.email_channel import EmailChannel
from app.services.channels.sms_channel import SMSChannel
from app.services.channels.whatsapp_channel import WhatsAppChannel
from app.services.channels.push_channel import PushChannel
from app.services.channels.web_broadcast_channel import WebBroadcastChannel
from app.models.channel_config import ChannelConfiguration

logger = logging.getLogger("masscommai.channel_registry")

_REGISTRY: Dict[str, BaseChannel] = {
    "Email": EmailChannel(),
    "SMS": SMSChannel(),
    "WhatsApp": WhatsAppChannel(),
    "Push": PushChannel(),
    "Web": WebBroadcastChannel(),
}


def register_channel(channel_name: str, channel: BaseChannel) -> None:
    """Registers an additional communication channel into the runtime registry."""
    key = channel_name.strip()
    _REGISTRY[key] = channel
    logger.info("Registered channel '%s' with implementation %s", key, type(channel).__name__)


def get_channel(channel_name: str) -> BaseChannel:
    """
    Returns registered channel instance for the specified channel name.
    Raises ValueError if the channel is not supported.
    """
    channel = _REGISTRY.get(channel_name.strip())
    if not channel:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(f"Channel '{channel_name}' is not registered. Available channels: {available}")
    return channel


def get_configured_channel(db: Session, channel_name: str) -> BaseChannel:
    """
    Instantiates or retrieves a channel adapter loaded with active database configurations,
    sender details, and provider credentials.
    """
    c_name = channel_name.strip()
    stmt = select(ChannelConfiguration).where(ChannelConfiguration.channel == c_name)
    config = db.execute(stmt).scalar_one_or_none()

    if not config:
        # Fall back to default in-memory registry channel
        return get_channel(c_name)

    provider_type = config.provider_type or "mock"
    sender_addr = config.sender_address or ("notifications@masscomm.gov.in" if c_name == "Email" else "GOVMSG")
    sender_nm = config.sender_name or ("MassCommAI Citizen Communications" if c_name == "Email" else "Govt Citizen Alert")
    creds = config.credentials or {}

    if c_name == "Email":
        return EmailChannel(
            provider_type=provider_type,
            sender_address=sender_addr,
            sender_name=sender_nm,
            credentials=creds,
        )
    elif c_name == "SMS":
        return SMSChannel(
            provider_type=provider_type,
            sender_address=sender_addr,
            sender_name=sender_nm,
            credentials=creds,
        )
    elif c_name == "WhatsApp":
        return WhatsAppChannel(
            provider_type=provider_type,
            sender_address=config.sender_address or "+1555010099",
            sender_name=config.sender_name or "MassCommAI WhatsApp Official",
            credentials=creds,
        )
    elif c_name == "Push":
        return PushChannel(
            provider_type=provider_type,
            sender_address=config.sender_address or "masscommai-fcm-project",
            sender_name=config.sender_name or "MassCommAI Citizen Push",
            credentials=creds,
        )
    elif c_name == "Web":
        return WebBroadcastChannel(
            provider_type=provider_type,
            sender_address=config.sender_address or "masscomm-broadcast-hub",
            sender_name=config.sender_name or "MassCommAI Web Broadcast",
            credentials=creds,
        )
    else:
        return get_channel(c_name)


def list_registered_channels() -> List[str]:
    """Returns a sorted list of all active communication channel names."""
    return sorted(list(_REGISTRY.keys()))


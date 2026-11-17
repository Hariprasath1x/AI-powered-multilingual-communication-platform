"""Channel integration module providing common abstraction layer, Email, SMS, WhatsApp, Push, and Web integrations."""

from app.services.channels.base import BaseChannel, ChannelSendResult
from app.services.channels.email_channel import EmailChannel
from app.services.channels.sms_channel import SMSChannel
from app.services.channels.whatsapp_channel import WhatsAppChannel
from app.services.channels.push_channel import PushChannel
from app.services.channels.web_broadcast_channel import WebBroadcastChannel
from app.services.channels.broadcast_manager import broadcast_manager, BroadcastConnectionManager
from app.services.channels.registry import (
    register_channel,
    get_channel,
    get_configured_channel,
    list_registered_channels,
)

__all__ = [
    "BaseChannel",
    "ChannelSendResult",
    "EmailChannel",
    "SMSChannel",
    "WhatsAppChannel",
    "PushChannel",
    "WebBroadcastChannel",
    "broadcast_manager",
    "BroadcastConnectionManager",
    "register_channel",
    "get_channel",
    "get_configured_channel",
    "list_registered_channels",
]


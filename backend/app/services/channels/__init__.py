"""Channel integration module providing common abstraction layer, Email, and SMS integrations."""

from app.services.channels.base import BaseChannel, ChannelSendResult
from app.services.channels.email_channel import EmailChannel
from app.services.channels.sms_channel import SMSChannel
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
    "register_channel",
    "get_channel",
    "get_configured_channel",
    "list_registered_channels",
]


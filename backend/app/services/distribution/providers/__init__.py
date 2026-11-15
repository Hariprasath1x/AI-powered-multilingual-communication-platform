"""Delivery provider factory and registry."""

from typing import Dict
from app.services.distribution.providers.base_provider import (
    BaseDeliveryProvider,
    DeliveryPayload,
    DeliveryResult,
)
from app.services.distribution.providers.mock_email import MockEmailProvider
from app.services.distribution.providers.mock_sms import MockSMSProvider
from app.services.distribution.providers.mock_whatsapp import MockWhatsAppProvider
from app.services.distribution.providers.mock_voice import MockVoiceProvider
from app.services.distribution.providers.mock_web_notification import MockWebNotificationProvider

_PROVIDERS: Dict[str, BaseDeliveryProvider] = {
    "Email": MockEmailProvider(),
    "SMS": MockSMSProvider(),
    "WhatsApp": MockWhatsAppProvider(),
    "Voice": MockVoiceProvider(),
    "Web": MockWebNotificationProvider(),
}


def get_provider(channel: str) -> BaseDeliveryProvider:
    """
    Returns registered provider adapter for the requested channel.
    Fails closed if the channel has no valid configured provider.
    """
    provider = _PROVIDERS.get(channel)
    if not provider:
        raise ValueError(
            f"No delivery provider configured for channel '{channel}'. "
            f"Available channels: {', '.join(sorted(_PROVIDERS.keys()))}"
        )
    return provider


__all__ = [
    "BaseDeliveryProvider",
    "DeliveryPayload",
    "DeliveryResult",
    "MockEmailProvider",
    "MockSMSProvider",
    "MockWhatsAppProvider",
    "MockVoiceProvider",
    "MockWebNotificationProvider",
    "get_provider",
]


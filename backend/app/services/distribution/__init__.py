"""Multichannel distribution engine services and provider interfaces."""

from app.services.distribution.base import (
    JobStatus,
    DeliveryStatus,
    DeliveryChannel,
    ReadinessCheckResult,
    ResolvedRecipient,
)
from app.services.distribution.consent_validator import (
    validate_recipient_consent,
    revalidate_jit_consent,
)
from app.services.distribution.recipient_resolver import resolve_campaign_recipients
from app.services.distribution.job_service import (
    check_campaign_readiness,
    create_distribution_job,
    get_distribution_job_by_uuid,
    list_distribution_jobs,
    list_job_delivery_records,
    cancel_distribution_job,
)
from app.services.distribution.delivery_service import (
    process_distribution_job,
    retry_failed_deliveries,
    claim_next_queued_job,
    recover_stale_jobs,
    update_worker_heartbeat,
    process_job_batch,
    get_distribution_metrics,
)
from app.services.distribution.providers import (
    BaseDeliveryProvider,
    DeliveryPayload,
    DeliveryResult,
    get_provider,
)

__all__ = [
    "JobStatus",
    "DeliveryStatus",
    "DeliveryChannel",
    "ReadinessCheckResult",
    "ResolvedRecipient",
    "validate_recipient_consent",
    "revalidate_jit_consent",
    "resolve_campaign_recipients",
    "check_campaign_readiness",
    "create_distribution_job",
    "get_distribution_job_by_uuid",
    "list_distribution_jobs",
    "list_job_delivery_records",
    "cancel_distribution_job",
    "process_distribution_job",
    "retry_failed_deliveries",
    "claim_next_queued_job",
    "recover_stale_jobs",
    "update_worker_heartbeat",
    "process_job_batch",
    "get_distribution_metrics",
    "BaseDeliveryProvider",
    "DeliveryPayload",
    "DeliveryResult",
    "get_provider",
]


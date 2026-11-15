"""
MassCommAI - Translation Caching Service.

Provides deterministic, persistent, concurrency-safe translation caching in PostgreSQL
(with full SQLite test fallback) to avoid redundant LLM invocations and token costs.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.translation import TranslationCache

logger = logging.getLogger("masscommai.translation_cache")


def compute_source_content_hash(
    title: Optional[str] = None,
    body: Optional[str] = None,
    call_to_action: Optional[str] = None,
) -> str:
    """Generate SHA-256 hash of canonical source content to link cache entries to source version."""
    clean_title = (title or "").strip()
    clean_body = (body or "").strip()
    clean_cta = (call_to_action or "").strip()
    payload = f"title:{clean_title}|body:{clean_body}|cta:{clean_cta}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_translation_cache_key(
    source_language: str,
    target_language: str,
    channel: str,
    source_content_hash: str,
    context_notes: Optional[str] = None,
    provider_type: Optional[str] = None,
    prompt_version: str = "v1.0",
    model_name: Optional[str] = None,
) -> str:
    """
    Generate deterministic SHA-256 cache key based on source hash, language pair, channel, context,
    provider type, model identifier, and prompt version.
    Ensures that any edit to the source content or provider/model/version switch changes the key,
    preventing stale translation hits or mock/production collision.
    """
    clean_src = source_language.lower().strip()
    clean_tgt = target_language.lower().strip()
    clean_ch = channel.strip().capitalize()
    clean_ctx = (context_notes or "").strip()
    clean_prov = (provider_type or "default").lower().strip()
    clean_model = (model_name or "default").lower().strip()
    clean_ver = (prompt_version or "v1.0").strip()
    payload = f"p:{clean_prov}|m:{clean_model}|ver:{clean_ver}|src:{clean_src}|tgt:{clean_tgt}|ch:{clean_ch}|shash:{source_content_hash}|ctx:{clean_ctx}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cached_translation(
    db: Session,
    cache_key: str,
) -> Optional[TranslationCache]:
    """
    Look up translation cache entry by cache key.
    If found, increments hit_count and updates last_accessed_at timestamp.
    """
    stmt = select(TranslationCache).where(TranslationCache.cache_key == cache_key)
    cached = db.execute(stmt).scalar_one_or_none()

    if cached:
        try:
            cached.hit_count += 1
            cached.last_accessed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(cached)
            logger.info("Translation cache HIT for key=%s (hit_count=%d)", cache_key[:12], cached.hit_count)
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to increment cache hit count: %s", exc)
        return cached

    logger.debug("Translation cache MISS for key=%s", cache_key[:12])
    return None


def save_cached_translation(
    db: Session,
    cache_key: str,
    source_content_hash: str,
    source_language: str,
    target_language: str,
    channel: str,
    translated_title: str,
    translated_body: str,
    translated_call_to_action: Optional[str] = None,
    summary: Optional[str] = None,
    preserved_placeholders: Optional[List[str]] = None,
    provider_metadata: Optional[Dict[str, Any]] = None,
) -> TranslationCache:
    """
    Persist valid translation in cache.
    Handles concurrent insertions gracefully by catching unique constraint collisions and returning existing.
    """
    clean_meta = dict(provider_metadata or {})
    clean_meta["cached"] = True

    new_entry = TranslationCache(
        cache_key=cache_key,
        source_content_hash=source_content_hash,
        source_language=source_language.lower().strip(),
        target_language=target_language.lower().strip(),
        channel=channel.strip().capitalize(),
        translated_title=translated_title.strip(),
        translated_body=translated_body.strip(),
        translated_call_to_action=translated_call_to_action.strip() if translated_call_to_action else None,
        summary=summary,
        preserved_placeholders=preserved_placeholders or [],
        provider_metadata=clean_meta,
        hit_count=0,
    )

    try:
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        logger.info("Translation cached successfully for key=%s", cache_key[:12])
        return new_entry
    except IntegrityError:
        db.rollback()
        # Concurrent worker inserted the exact same cache_key
        existing = db.execute(
            select(TranslationCache).where(TranslationCache.cache_key == cache_key)
        ).scalar_one_or_none()
        if existing:
            return existing
        raise


def invalidate_source_cache(
    db: Session,
    source_content_hash: str,
) -> int:
    """Purge all translation cache entries associated with a specific source content hash."""
    stmt = delete(TranslationCache).where(TranslationCache.source_content_hash == source_content_hash)
    result = db.execute(stmt)
    db.commit()
    deleted_count = result.rowcount or 0
    if deleted_count > 0:
        logger.info("Invalidated %d cache entries for source_hash=%s", deleted_count, source_content_hash[:12])
    return deleted_count


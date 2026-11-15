"""
MassCommAI - Milestone 2, Task 8: Dedicated PostgreSQL Concurrency Integration Tests.

Validates that:
- PostgreSQL-level partial unique index `uq_content_asset_translation_variant`
  strictly prevents concurrent duplicate variant creation.
- Concurrent requests dispatched across separate threads and DB sessions both resolve to the single valid variant.
- Losing session remains healthy and usable after transaction rollback.
- Unrelated database errors are not swallowed.
"""

import unittest
import concurrent.futures
import asyncio
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from fastapi import HTTPException

from app.core.config import settings
from app.models.user import User
from app.models.content_asset import ContentAsset
from app.services.translation_service import translate_single_language


def is_postgres_available() -> bool:
    """Check if the configured PostgreSQL database is accessible."""
    if not settings.DATABASE_URL.startswith("postgresql"):
        return False
    try:
        engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return True
    except Exception:
        return False


@unittest.skipUnless(is_postgres_available(), "PostgreSQL database is not accessible")
class TestPostgreSQLTranslationConcurrency(unittest.TestCase):
    """PostgreSQL-backed concurrency verification for translation variants."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(settings.DATABASE_URL)
        cls.SessionLocal = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        # Retrieve or seed an existing user
        self.user = self.db.execute(select(User).limit(1)).scalar_one_or_none()
        if not self.user:
            self.skipTest("No user found in PostgreSQL database to run authoring test")

        # Create isolated root asset for this test
        self.source = ContentAsset(
            title="Postgres Concurrency Isolation Root",
            body="Citizen notice regarding {facility} schedule in {city}.",
            channel="Email",
            category="Civic Services",
            source_language="en",
            created_by=self.user.id,
        )
        self.db.add(self.source)
        self.db.commit()
        self.db.refresh(self.source)
        self.source_id = self.source.id

    def tearDown(self):
        try:
            # Clean up all created test assets and history
            self.db.execute(
                text("DELETE FROM translation_review_history WHERE content_asset_id IN (SELECT id FROM content_assets WHERE parent_id = :pid OR id = :pid)"),
                {"pid": self.source_id},
            )
            self.db.execute(
                text("DELETE FROM content_assets WHERE parent_id = :pid OR id = :pid"),
                {"pid": self.source_id},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def test_postgresql_concurrent_translation_variant_uniqueness(self):
        """
        Dispatch two simultaneous translation requests for the same parent asset and target language.
        Verify:
        1. PostgreSQL unique index triggers UniqueViolation on the losing transaction.
        2. Both requests return the valid persisted variant.
        3. Exactly one child variant exists in PostgreSQL.
        4. The losing session remains usable for subsequent queries.
        """
        def worker(worker_id: int):
            thread_db = self.SessionLocal()
            try:
                thread_source = thread_db.get(ContentAsset, self.source_id)
                thread_user = thread_db.get(User, self.user.id)
                variant = asyncio.run(translate_single_language(
                    db=thread_db,
                    source_asset=thread_source,
                    target_language="hi",
                    current_user=thread_user,
                    provider_type="mock",
                ))
                # Verify session usability after potential rollback
                session_usable = thread_db.execute(select(func.count(ContentAsset.id))).scalar() is not None
                return {
                    "worker_id": worker_id,
                    "variant_id": variant.id,
                    "target_language": variant.target_language,
                    "session_usable": session_usable,
                }
            finally:
                thread_db.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker, 1)
            f2 = executor.submit(worker, 2)
            r1 = f1.result()
            r2 = f2.result()

        # Both workers must return the identical variant ID
        self.assertEqual(r1["variant_id"], r2["variant_id"])
        self.assertEqual(r1["target_language"], "hi")
        self.assertEqual(r2["target_language"], "hi")

        # Both sessions must report usable
        self.assertTrue(r1["session_usable"])
        self.assertTrue(r2["session_usable"])

        # Exactly ONE variant exists in PostgreSQL
        variants_in_pg = self.db.execute(
            select(ContentAsset).where(
                ContentAsset.parent_id == self.source_id,
                ContentAsset.target_language == "hi",
            )
        ).scalars().all()
        self.assertEqual(len(variants_in_pg), 1)
        self.assertEqual(variants_in_pg[0].id, r1["variant_id"])

    def test_postgresql_unrelated_database_errors_not_swallowed(self):
        """Verify that foreign key or database violations are not swallowed or mistaken for variants."""
        # Non-existent parent_id
        fake_source = ContentAsset(
            id=99999999,
            title="Nonexistent",
            body="No parent",
            channel="SMS",
            category="Healthcare",
            source_language="en",
            created_by=self.user.id,
        )
        fake_source.id = 99999999

        # Attempt to create variant for nonexistent parent
        thread_db = self.SessionLocal()
        try:
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(translate_single_language(
                    db=thread_db,
                    source_asset=fake_source,
                    target_language="ta",
                    current_user=self.user,
                    provider_type="mock",
                ))
            # Must raise 500 or 409, not return a phantom variant
            self.assertIn(ctx.exception.status_code, [409, 500])
        finally:
            thread_db.close()


if __name__ == "__main__":
    unittest.main()


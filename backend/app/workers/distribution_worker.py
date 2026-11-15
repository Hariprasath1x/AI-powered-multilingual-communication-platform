"""Independent database-backed queue worker for multichannel distribution jobs."""

import sys
import time
import signal
import asyncio
import logging
import argparse
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.workers.worker_config import WorkerConfig
from app.services.distribution import (
    claim_next_queued_job,
    recover_stale_jobs,
    process_job_batch,
    get_distribution_metrics,
)

# Configure worker logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("masscommai.worker")


class DistributionWorker:
    """
    Independent queue worker daemon executing batch delivery processing.
    Features:
    - Atomic job claiming with PostgreSQL FOR UPDATE SKIP LOCKED.
    - Automated stale job lease recovery.
    - Bounded batch processing preventing memory exhaustion.
    - Graceful shutdown handling for SIGINT and SIGTERM.
    - Configurable one-shot and continuous polling execution modes.
    """

    def __init__(self, config: Optional[WorkerConfig] = None):
        self.config = config or WorkerConfig()
        self.shutdown_requested = False
        self._register_signal_handlers()

    def _register_signal_handlers(self) -> None:
        """Hooks SIGINT and SIGTERM to trigger graceful shutdown."""
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (ValueError, AttributeError):
            # Signal handling may not be supported in some thread contexts
            pass

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Signal handler requesting worker shutdown after current batch finishes."""
        sig_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        logger.info("Received %s signal. Requesting graceful shutdown...", sig_name)
        self.shutdown_requested = True

    async def run_one_shot(self) -> Dict[str, Any]:
        """
        Executes a single processing pass:
        1. Recovers any expired stale jobs.
        2. Claims and executes queued jobs up to max_jobs_per_run in bounded batches.
        Returns execution statistics summary.
        """
        stats: Dict[str, Any] = {
            "worker_id": self.config.worker_id,
            "stale_jobs_recovered": 0,
            "jobs_claimed": 0,
            "jobs_completed": 0,
            "batches_executed": 0,
            "records_processed": 0,
        }

        db: Session = SessionLocal()
        try:
            # 1. Recover stale jobs
            recovered = recover_stale_jobs(
                db=db,
                lease_seconds=self.config.lease_duration_seconds,
                max_recoveries=self.config.max_recoveries,
            )
            stats["stale_jobs_recovered"] = len(recovered)
            if recovered:
                logger.info("Recovered %s stale distribution jobs.", len(recovered))

            # 2. Claim and process queued jobs
            claimed_count = 0
            while claimed_count < self.config.max_jobs_per_run and not self.shutdown_requested:
                job = claim_next_queued_job(
                    db=db,
                    worker_id=self.config.worker_id,
                    lease_seconds=self.config.lease_duration_seconds,
                )
                if not job:
                    break  # No more queued jobs

                claimed_count += 1
                stats["jobs_claimed"] += 1
                logger.info(
                    "[%s] Claimed Job #%s (UUID: %s, Channel: %s).",
                    self.config.worker_id,
                    job.id,
                    job.job_id,
                    job.channel,
                )

                # Process job in bounded batches until done
                job_uuid = job.job_id
                lease_generation = job.recovery_count
                has_more = True
                while has_more and not self.shutdown_requested:
                    records_in_batch, has_more = await process_job_batch(
                        db=db,
                        job_uuid=job_uuid,
                        batch_size=self.config.batch_size,
                        worker_id=self.config.worker_id,
                        base_backoff_seconds=self.config.retry_backoff_base_seconds,
                        max_backoff_seconds=self.config.max_retry_backoff_seconds,
                        expected_recovery_count=lease_generation,
                    )
                    stats["batches_executed"] += 1
                    stats["records_processed"] += records_in_batch

                if not has_more:
                    stats["jobs_completed"] += 1
                    logger.info("Completed processing for Job UUID: %s.", job_uuid)

        finally:
            db.close()

        logger.info("One-shot run finished: %s", stats)
        return stats

    async def run_continuous(self) -> None:
        """
        Continuously polls the database queue for work until shutdown is requested.
        Executes bounded batches and sleeps for poll_interval between idle checks.
        """
        logger.info(
            "Starting continuous worker daemon '%s' (batch_size=%s, poll_interval=%.1fs, lease=%ss)...",
            self.config.worker_id,
            self.config.batch_size,
            self.config.poll_interval,
            self.config.lease_duration_seconds,
        )

        last_recovery_scan = 0.0
        recovery_interval = min(60.0, float(self.config.lease_duration_seconds / 2))

        while not self.shutdown_requested:
            db: Session = SessionLocal()
            try:
                now_epoch = time.time()
                # Periodically recover stale jobs
                if (now_epoch - last_recovery_scan) >= recovery_interval:
                    recover_stale_jobs(
                        db=db,
                        lease_seconds=self.config.lease_duration_seconds,
                        max_recoveries=self.config.max_recoveries,
                    )
                    last_recovery_scan = now_epoch

                # Claim next queued job
                job = claim_next_queued_job(
                    db=db,
                    worker_id=self.config.worker_id,
                    lease_seconds=self.config.lease_duration_seconds,
                )

                if job:
                    job_uuid = job.job_id
                    has_more = True
                    while has_more and not self.shutdown_requested:
                        records_in_batch, has_more = await process_job_batch(
                            db=db,
                            job_uuid=job_uuid,
                            batch_size=self.config.batch_size,
                            worker_id=self.config.worker_id,
                            base_backoff_seconds=self.config.retry_backoff_base_seconds,
                            max_backoff_seconds=self.config.max_retry_backoff_seconds,
                        )
                        logger.debug("Processed %s records for Job %s.", records_in_batch, job_uuid)
                else:
                    # Queue is empty, sleep for poll interval
                    await asyncio.sleep(self.config.poll_interval)

            except Exception as exc:
                logger.error("Unexpected worker exception during queue loop: %s", exc, exc_info=True)
                await asyncio.sleep(self.config.poll_interval)
            finally:
                db.close()

        logger.info("Worker '%s' cleanly terminated.", self.config.worker_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MassCommAI Distribution Queue Worker")
    parser.add_argument(
        "--one-shot",
        action="store_true",
        help="Execute single pass over eligible queue items and exit (ideal for tests and CI)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Max delivery records processed per bounded batch",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="Polling interval in seconds between idle checks",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="Maximum jobs claimed during one-shot execution",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint for executing the worker process."""
    args = parse_args()
    config = WorkerConfig()

    if args.batch_size is not None:
        config.batch_size = args.batch_size
    if args.poll_interval is not None:
        config.poll_interval = args.poll_interval
    if args.max_jobs is not None:
        config.max_jobs_per_run = args.max_jobs

    worker = DistributionWorker(config=config)

    if args.one_shot:
        asyncio.run(worker.run_one_shot())
    else:
        asyncio.run(worker.run_continuous())


if __name__ == "__main__":
    main()


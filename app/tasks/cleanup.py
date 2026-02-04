"""Cleanup tasks for maintenance operations."""

import logging
from datetime import datetime, timedelta, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.cleanup.cleanup_old_execution_traces")
def cleanup_old_execution_traces(days_to_keep: int = 30) -> dict:
    """
    Delete execution traces older than the specified number of days.

    This task runs daily to prevent unbounded growth of the execution_traces table.

    Args:
        days_to_keep: Number of days of traces to retain (default 30)

    Returns:
        Dict with count of deleted traces
    """
    import asyncio

    async def _cleanup():
        from sqlalchemy import delete
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from app.config import get_settings
        from app.models import ExecutionTrace

        settings = get_settings()
        engine = create_async_engine(settings.async_database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        async with session_factory() as db:
            # Delete old traces
            result = await db.execute(
                delete(ExecutionTrace).where(ExecutionTrace.created_at < cutoff_date)
            )

            deleted_count = result.rowcount
            await db.commit()

            logger.info(
                f"Cleaned up {deleted_count} execution traces older than {days_to_keep} days"
            )

            return {"deleted_count": deleted_count, "cutoff_date": cutoff_date.isoformat()}

        await engine.dispose()

    return asyncio.run(_cleanup())


@celery_app.task(name="app.tasks.cleanup.check_abandoned_sessions")
def check_abandoned_sessions(timeout_minutes: int = 30) -> dict:
    """
    Check for and mark abandoned conversation sessions.

    This task runs periodically to detect sessions that have been inactive
    for longer than the timeout period. It handles:
    - Customer flow sessions (booking, modify, cancel, rating)
    - Staff onboarding sessions
    - Business onboarding sessions

    Args:
        timeout_minutes: Inactivity threshold in minutes (default 30)

    Returns:
        Dict with counts of abandoned sessions by type
    """
    import asyncio

    async def _check_abandoned():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from app.config import get_settings
        from app.models import CustomerFlowSession, OnboardingSession, StaffOnboardingSession
        from app.services.abandoned_state import check_and_mark_abandoned_sessions

        settings = get_settings()
        engine = create_async_engine(settings.async_database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        results = {
            "customer_flows": 0,
            "staff_onboarding": 0,
            "business_onboarding": 0,
            "timeout_minutes": timeout_minutes,
        }

        async with session_factory() as db:
            # Check customer flow sessions
            results["customer_flows"] = await check_and_mark_abandoned_sessions(
                db=db,
                session_model=CustomerFlowSession,
                timeout_minutes=timeout_minutes,
            )

            # Check staff onboarding sessions
            results["staff_onboarding"] = await check_and_mark_abandoned_sessions(
                db=db,
                session_model=StaffOnboardingSession,
                timeout_minutes=timeout_minutes,
            )

            # Check business onboarding sessions
            results["business_onboarding"] = await check_and_mark_abandoned_sessions(
                db=db,
                session_model=OnboardingSession,
                timeout_minutes=timeout_minutes,
            )

            await db.commit()

            total = sum([
                results["customer_flows"],
                results["staff_onboarding"],
                results["business_onboarding"],
            ])

            if total > 0:
                logger.info(f"Marked {total} sessions as abandoned: {results}")

            return results

        await engine.dispose()

    return asyncio.run(_check_abandoned())

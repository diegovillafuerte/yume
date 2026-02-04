"""Celery application configuration."""

from celery import Celery

from app.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "yume",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.health",
        "app.tasks.reminders",
        "app.tasks.cleanup",
    ],
)

# Configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="America/Mexico_City",
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Result settings
    result_expires=3600,  # 1 hour

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,

    # Beat schedule for periodic tasks
    beat_schedule={
        "check-upcoming-reminders": {
            "task": "app.tasks.reminders.check_and_send_reminders",
            "schedule": 300.0,  # Every 5 minutes
        },
        "cleanup-old-execution-traces": {
            "task": "app.tasks.cleanup.cleanup_old_execution_traces",
            "schedule": 86400.0,  # Every 24 hours (daily)
            "args": [30],  # Keep 30 days of traces
        },
        "check-abandoned-sessions": {
            "task": "app.tasks.cleanup.check_abandoned_sessions",
            "schedule": 600.0,  # Every 10 minutes
            "args": [30],  # 30 minute timeout
        },
    },
)

"""Celery application — Upstash Redis broker + result backend (D.6)."""

from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]

from aeogen.settings import get_settings

_settings = get_settings()
_redis_url = str(_settings.redis_url)

celery_app = Celery(
    "aeogen",
    broker=_redis_url,
    backend=_redis_url,
    include=["aeogen.tasks.crawl"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

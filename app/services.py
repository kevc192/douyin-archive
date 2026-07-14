from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from sqlalchemy import select

from .database import SessionLocal
from .downloader import ArchiveDownloader
from .models import Subscription, SyncRun

executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="archive")


def enqueue_archive(url: str, subscription_id: int | None = None) -> int:
    with SessionLocal() as db:
        run = SyncRun(source_url=url, subscription_id=subscription_id)
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
    executor.submit(_run_archive, run_id)
    return run_id


def _run_archive(run_id: int) -> None:
    with SessionLocal() as db:
        run = db.get(SyncRun, run_id)
        if not run:
            return
        run.status = "running"
        db.commit()
        try:
            count = ArchiveDownloader().archive_profile(run.source_url)
            run.status = "completed"
            run.downloaded_count = count
            run.message = f"Archived {count} new work(s)."
            if run.subscription_id:
                sub = db.get(Subscription, run.subscription_id)
                if sub:
                    sub.last_synced_at = datetime.utcnow()
                    sub.last_error = None
        except Exception as exc:
            run.status = "failed"
            run.message = str(exc)[:4000]
            if run.subscription_id:
                sub = db.get(Subscription, run.subscription_id)
                if sub:
                    sub.last_error = run.message
        finally:
            run.completed_at = datetime.utcnow()
            db.commit()


def enqueue_enabled_subscriptions() -> None:
    with SessionLocal() as db:
        subscriptions = db.scalars(select(Subscription).where(Subscription.enabled.is_(True))).all()
        for sub in subscriptions:
            enqueue_archive(sub.profile_url, sub.id)


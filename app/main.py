from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from .browser_provider import browser_status
from .config import DOWNLOAD_ROOT, SYNC_CRON
from .database import Base, SessionLocal, engine
from .models import Subscription, SyncRun
from .schemas import ArchiveRequest, BrowserStatusOut, RunOut, SubscriptionCreate, SubscriptionOut
from .services import enqueue_archive, enqueue_enabled_subscriptions

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


@asynccontextmanager
async def lifespan(_: FastAPI):
    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    minute, hour, day, month, weekday = SYNC_CRON.split()
    scheduler.add_job(enqueue_enabled_subscriptions, "cron", minute=minute, hour=hour, day=day, month=month, day_of_week=weekday, id="subscription-sync")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="抖音作品归档", lifespan=lifespan)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/browser", response_model=BrowserStatusOut)
def browser():
    return browser_status()


@app.get("/api/config")
def config():
    return {"sync_cron": SYNC_CRON}


@app.post("/api/archive", response_model=RunOut, status_code=202)
def archive(request: ArchiveRequest):
    url = request.profile_url
    run_id = enqueue_archive(url)
    with SessionLocal() as db:
        return db.get(SyncRun, run_id)


@app.get("/api/runs", response_model=list[RunOut])
def runs():
    with SessionLocal() as db:
        return db.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(30)).all()


@app.get("/api/subscriptions", response_model=list[SubscriptionOut])
def subscriptions():
    with SessionLocal() as db:
        return db.scalars(select(Subscription).order_by(Subscription.id.desc())).all()


@app.post("/api/subscriptions", response_model=SubscriptionOut, status_code=201)
def create_subscription(payload: SubscriptionCreate):
    url = payload.profile_url
    with SessionLocal() as db:
        existing = db.scalar(select(Subscription).where(Subscription.profile_url == url))
        if existing:
            raise HTTPException(409, "This profile is already subscribed.")
        sub = Subscription(profile_url=url, label=payload.label)
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return sub


@app.post("/api/subscriptions/{subscription_id}/sync", response_model=RunOut, status_code=202)
def sync_subscription(subscription_id: int):
    with SessionLocal() as db:
        sub = db.get(Subscription, subscription_id)
        if not sub:
            raise HTTPException(404, "Subscription not found.")
        run_id = enqueue_archive(sub.profile_url, sub.id)
        return db.get(SyncRun, run_id)


@app.patch("/api/subscriptions/{subscription_id}/toggle", response_model=SubscriptionOut)
def toggle_subscription(subscription_id: int):
    with SessionLocal() as db:
        sub = db.get(Subscription, subscription_id)
        if not sub:
            raise HTTPException(404, "Subscription not found.")
        sub.enabled = not sub.enabled
        db.commit()
        db.refresh(sub)
        return sub

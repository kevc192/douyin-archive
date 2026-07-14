import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/app.db")
DOWNLOAD_ROOT = Path(os.getenv("DOWNLOAD_ROOT", "/app/downloads"))
SYNC_CRON = os.getenv("SYNC_CRON", "15 */6 * * *")
ALLOW_AGE_RESTRICTED = os.getenv("ALLOW_AGE_RESTRICTED", "false").lower() == "true"
BROWSER_CDP_URL = os.getenv("BROWSER_CDP_URL", "http://host.docker.internal:9222")
PROFILE_SCROLL_ROUNDS = int(os.getenv("PROFILE_SCROLL_ROUNDS", "18"))

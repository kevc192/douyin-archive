from datetime import datetime

from pydantic import BaseModel, field_validator


class ArchiveRequest(BaseModel):
    profile_url: str

    @field_validator("profile_url")
    @classmethod
    def normalize_douyin_source(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A Douyin profile URL or sec_uid is required.")
        if value.startswith(("http://", "https://")):
            return value
        # A sec_uid is the stable identifier used in a Douyin profile URL.
        if all(c.isalnum() or c in "_-" for c in value):
            return f"https://www.douyin.com/user/{value}"
        raise ValueError("Enter a valid Douyin profile URL or sec_uid.")


class SubscriptionCreate(ArchiveRequest):
    label: str | None = None


class SubscriptionOut(BaseModel):
    id: int
    profile_url: str
    label: str | None
    enabled: bool
    created_at: datetime
    last_synced_at: datetime | None
    last_error: str | None

    class Config:
        from_attributes = True


class RunOut(BaseModel):
    id: int
    source_url: str
    subscription_id: int | None
    status: str
    downloaded_count: int
    message: str | None
    started_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class BrowserStatusOut(BaseModel):
    connected: bool
    contexts: int | None = None
    pages: int | None = None
    message: str | None = None

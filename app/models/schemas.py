from pydantic import BaseModel, field_validator
import validators
import re
from datetime import datetime, timezone

from app.core.constants import RESERVED_CODES

ALIAS_RE = re.compile(r"[A-Za-z0-9_-]{3,32}")

class ShortenRequest(BaseModel):
    url: str
    alias: str | None = None
    expires_at: datetime | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 2048 or not validators.url(v):
            raise ValueError("Invalid URL.")
        return v

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not ALIAS_RE.fullmatch(v):
            raise ValueError("Alias must be 3-32 characters: letters, digits, '-' or '_'.")
        if v.lower() in RESERVED_CODES:
            raise ValueError("That alias is reserved.")
        return v

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)  # a datetime with no zone is taken as UTC
        v = v.astimezone(timezone.utc)  # store one canonical zone, whatever offset was sent
        if v <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be in the future.")
        return v


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
    created_at: datetime
    expires_at: datetime | None = None
    model_config = {"from_attributes": True}


class URLStats(BaseModel):
    short_code: str
    original_url: str
    click_count: int
    created_at: datetime
    last_clicked_at: datetime | None
    expires_at: datetime | None = None
    model_config = {"from_attributes": True}


class ClickDetail(BaseModel):
    clicked_at: datetime
    referrer: str | None
    user_agent: str | None

    model_config = {"from_attributes": True}


class AnalyticsResponse(BaseModel):
    stats: URLStats
    recent_clicks: list[ClickDetail]

class RegisterRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()  # normalize so Alice@x.com and alice@x.com are one account
        if not validators.email(v):
            raise ValueError("Invalid email address.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if len(v.encode()) > 72:  # bcrypt ignores or rejects anything beyond 72 bytes
            raise ValueError("Password must be at most 72 bytes.")
        return v


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class DayCount(BaseModel):
    date: str
    clicks: int


class ReferrerCount(BaseModel):
    referrer: str
    clicks: int


class BrowserCount(BaseModel):
    browser: str
    clicks: int


class SummaryResponse(BaseModel):
    short_code: str
    days: int
    total_clicks: int
    clicks_per_day: list[DayCount]
    top_referrers: list[ReferrerCount]
    browsers: list[BrowserCount]
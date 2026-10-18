from datetime import datetime
from pydantic import BaseModel, field_validator
import validators


class ShortenRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not validators.url(v):
            raise ValueError("Invalid URL provided.")
        return v


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class URLStats(BaseModel):
    short_code: str
    original_url: str
    click_count: int
    created_at: datetime
    last_clicked_at: datetime | None

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
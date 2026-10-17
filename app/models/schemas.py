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
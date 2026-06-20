from pydantic import BaseModel, Field, field_validator
from typing import Any
from datetime import datetime


class EventIn(BaseModel):
    """Schema validasi untuk event masuk dari publisher."""
    topic: str = Field(..., min_length=1, max_length=255)
    event_id: str = Field(..., min_length=1, max_length=255)
    timestamp: str = Field(..., description="Format ISO 8601")
    source: str = Field(default="", max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Pastikan timestamp bisa di-parse sebagai ISO 8601."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("timestamp harus format ISO 8601, contoh: 2024-01-01T00:00:00Z")
        return v

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        """Pastikan topic tidak mengandung spasi."""
        if " " in v:
            raise ValueError("topic tidak boleh mengandung spasi")
        return v.lower()


class BatchEventIn(BaseModel):
    """Schema untuk batch publish."""
    events: list[EventIn] = Field(..., min_length=1, max_length=1000)


class EventOut(BaseModel):
    """Schema response untuk event."""
    id: int
    topic: str
    event_id: str
    source: str
    timestamp: str
    payload: dict[str, Any]
    received_at: str


class StatsOut(BaseModel):
    received: int
    unique_processed: int
    duplicate_dropped: int
    error_count: int
    topics: list[str]
    uptime_seconds: float
    duplicate_rate_percent: float
    lag_seconds: float


class AuditEntry(BaseModel):
    id: int
    topic: str
    event_id: str
    source: str
    action: str
    logged_at: str


class PublishResult(BaseModel):
    """Schema response setelah publish."""
    status: str
    accepted: int
    duplicates: int
    errors: int
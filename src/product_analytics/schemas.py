"""CP1 synthetic GA4-style event contract. This is not a full GA4 export."""

from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EventName = Literal[
    "experiment_assignment", "experiment_exposure", "session_start", "view_item",
    "add_to_cart", "begin_checkout", "purchase", "error",
]
Variant = Literal["A", "B"]
Device = Literal["mobile", "desktop", "tablet"]
Channel = Literal["organic", "paid_search", "email", "direct", "social"]


class EventRecord(BaseModel):
    """Strict synthetic event. Assignment has no session, other events do."""

    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    session_id: str | None = None
    event_timestamp: datetime
    event_name: EventName
    page: str | None = None
    channel: Channel
    campaign: str | None = None
    device: Device
    experiment_id: str = Field(min_length=1)
    variant: Variant
    conversion: Literal[0, 1] = 0
    revenue: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)

    @field_validator("event_id", "user_id", "experiment_id")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identifier cannot be blank")
        return value

    @field_validator("event_timestamp")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("timestamp must be UTC-aware (+00:00), not naive or local offset")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def event_invariants(self):
        if self.event_name == "experiment_assignment":
            if self.session_id is not None:
                raise ValueError("assignment must have no session_id")
        elif not self.session_id or not self.session_id.strip():
            raise ValueError("non-assignment events require a session_id")
        if self.event_name == "purchase":
            if self.conversion != 1 or self.revenue <= 0:
                raise ValueError("purchase must have conversion=1 and positive revenue")
        elif self.conversion != 0 or self.revenue != 0:
            raise ValueError("non-purchase event cannot carry conversion or revenue")
        return self

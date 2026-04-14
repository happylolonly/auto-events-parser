import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from supabase import Client, create_client

from app.services.extractor import ExtractedEvent


class SupabaseRepoError(Exception):
    pass


@dataclass
class EventRecord:
    id: str
    source_url: str
    title: str
    start_at: datetime | None
    location: str | None
    created_at: datetime | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "EventRecord":
        return cls(
            id=row["id"],
            source_url=row["source_url"],
            title=row["title"],
            start_at=_to_datetime(row.get("start_at")),
            location=row.get("location"),
            created_at=_to_datetime(row.get("created_at")),
        )


def _to_datetime(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(value, datetime):
        return value
    return None


class SupabaseRepo:
    def __init__(self) -> None:
        self._client = self._build_client()

    @staticmethod
    def _build_client() -> Client:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise SupabaseRepoError("SUPABASE_URL and SUPABASE_KEY must be configured.")
        return create_client(url, key)

    def upsert_event(self, source_url: str, extracted: ExtractedEvent) -> EventRecord:
        payload = {
            "source_url": source_url,
            "title": extracted.title,
            "start_at": extracted.start_at.isoformat() if extracted.start_at else None,
            "location": extracted.location,
        }
        try:
            response = (
                self._client.table("events")
                .upsert(payload, on_conflict="source_url")
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            raise SupabaseRepoError(f"Failed to save event in Supabase: {exc}") from exc
        if not response.data:
            raise SupabaseRepoError("Supabase returned empty response after upsert.")
        return EventRecord.from_row(response.data[0])

    def list_events(self) -> list[dict[str, Any]]:
        try:
            response = (
                self._client.table("events")
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            raise SupabaseRepoError(f"Failed to load events from Supabase: {exc}") from exc
        return response.data or []

    @staticmethod
    def to_dict(record: EventRecord) -> dict[str, Any]:
        return asdict(record)

from datetime import datetime
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from dotenv import load_dotenv

from app.services.extractor import EventExtractionError, extract_event_from_url
from app.services.supabase_repo import EventRecord, SupabaseRepo, SupabaseRepoError

router = APIRouter()
load_dotenv()
logger = logging.getLogger(__name__)


def _repo() -> SupabaseRepo:
    return SupabaseRepo()


class ParseEventRequest(BaseModel):
    url: HttpUrl


class ParseEventResponse(BaseModel):
    id: str
    source_url: str
    title: str
    start_at: datetime | None
    location: str | None
    created_at: datetime | None


@router.post("/parse-event", response_model=ParseEventResponse)
async def parse_event(payload: ParseEventRequest) -> ParseEventResponse:
    try:
        extracted = await extract_event_from_url(str(payload.url))
        logger.info(
            "Event parsed successfully url=%s title=%s start_at=%s location=%s",
            payload.url,
            extracted.title,
            extracted.start_at,
            extracted.location,
        )
    except EventExtractionError as exc:
        logger.exception("Event extraction failed for url=%s", payload.url)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        saved = _repo().upsert_event(source_url=str(payload.url), extracted=extracted)
        logger.info("Event saved successfully id=%s source_url=%s", saved.id, payload.url)
    except SupabaseRepoError as exc:
        logger.exception("Supabase upsert failed for url=%s", payload.url)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ParseEventResponse.model_validate(SupabaseRepo.to_dict(saved))


@router.get("/events", response_model=list[ParseEventResponse])
async def list_events() -> list[ParseEventResponse]:
    try:
        rows = _repo().list_events()
    except SupabaseRepoError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return [
        ParseEventResponse.model_validate(SupabaseRepo.to_dict(EventRecord.from_row(row)))
        for row in rows
    ]

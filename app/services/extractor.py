import json
import logging
import os
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EventExtractionError(Exception):
    pass


@dataclass
class ExtractedEvent:
    title: str
    start_at: datetime | None
    location: str | None


def _normalize_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise EventExtractionError("LLM did not return JSON payload.")
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise EventExtractionError("Failed to parse JSON from LLM response.") from exc
    if not isinstance(parsed, dict):
        raise EventExtractionError("LLM JSON response must be an object.")
    return parsed


async def _fetch_page_text(url: str) -> str:
    logger.info("Fetching page content: %s", url)
    timeout = httpx.Timeout(15.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        last_error: httpx.ConnectError | None = None
        response: httpx.Response | None = None
        for attempt in range(1, 4):
            try:
                response = await client.get(url)
                break
            except httpx.ConnectError as exc:
                last_error = exc
                logger.warning(
                    "Transient connect error while fetching url=%s attempt=%s error=%s",
                    url,
                    attempt,
                    exc,
                )
                if attempt < 4:
                    await asyncio.sleep(0.6 * attempt)
        if response is None and last_error is not None:
            raise last_error
        if response is None:
            raise EventExtractionError("Failed to fetch source URL for unknown reason.")
        response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        raise EventExtractionError("Only HTML pages are supported in MVP.")
    soup = BeautifulSoup(response.text, "html.parser")
    page_text = " ".join(soup.get_text(separator=" ").split())[:12000]
    logger.info("Fetched page text length=%s chars", len(page_text))
    return page_text


async def _call_llm(page_text: str, source_url: str) -> dict[str, Any]:
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "gemini-2.0-flash")
    base_url = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    if not api_key:
        raise EventExtractionError("LLM_API_KEY is not configured.")
    provider = "openrouter" if "openrouter.ai" in base_url else "gemini"
    logger.info("Calling LLM provider=%s model=%s", provider, model)

    prompt = (
        "Extract event data from source content. Return strict JSON object only with keys: "
        '"title", "start_at_iso", "location". '
        "Use null for unknown values and never invent facts."
    )
    user_content = f"Source URL: {source_url}\nPage text:\n{page_text}"
    headers = {"Content-Type": "application/json"}

    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        if provider == "openrouter":
            endpoint = f"{base_url.rstrip('/')}/chat/completions"
            headers["Authorization"] = f"Bearer {api_key}"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            }
        else:
            endpoint = f"{base_url}/models/{model}:generateContent?key={api_key}"
            payload = {
                "system_instruction": {"parts": [{"text": prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_content}]}],
                "generationConfig": {"temperature": 0},
            }

        logger.info("Sending LLM request to %s", endpoint)
        response = await client.post(endpoint, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            error_body = response.text[:600].replace("\n", " ")
            logger.error(
                "LLM HTTP error status=%s body_preview=%s",
                response.status_code,
                error_body,
            )
            raise
        data = response.json()
    logger.info("LLM response received keys=%s", list(data.keys()))

    try:
        if provider == "openrouter":
            message = data["choices"][0]["message"]["content"]
            if isinstance(message, str):
                content = message
            elif isinstance(message, list):
                content = "\n".join(
                    part.get("text", "")
                    for part in message
                    if isinstance(part, dict) and isinstance(part.get("text"), str)
                )
            else:
                raise TypeError("Unsupported OpenRouter message content type.")
        else:
            parts = data["candidates"][0]["content"]["parts"]
            content = "\n".join(
                part["text"] for part in parts if isinstance(part, dict) and "text" in part
            )
    except (KeyError, IndexError, TypeError) as exc:
        logger.exception("Unexpected LLM response structure: %s", data)
        raise EventExtractionError("Unexpected LLM response format.") from exc
    if not content.strip():
        raise EventExtractionError("LLM returned empty content.")
    logger.info("LLM content preview: %s", content[:400].replace("\n", " "))
    return _extract_json_object(content)


async def extract_event_from_url(url: str) -> ExtractedEvent:
    try:
        page_text = await _fetch_page_text(url)
        raw = await _call_llm(page_text=page_text, source_url=url)
        logger.info("Parsed LLM JSON payload: %s", raw)
    except httpx.HTTPError as exc:
        raise EventExtractionError(f"Failed to fetch or parse source URL: {exc}") from exc

    title = (raw.get("title") or "").strip()
    if not title:
        logger.error("Missing title in LLM payload: %s", raw)
        raise EventExtractionError("Could not extract event title.")

    location = raw.get("location")
    if isinstance(location, str):
        location = location.strip() or None
    else:
        location = None

    return ExtractedEvent(
        title=title,
        start_at=_normalize_iso_datetime(raw.get("start_at_iso")),
        location=location,
    )

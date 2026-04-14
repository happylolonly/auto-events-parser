# Events Parser MVP

Python MVP for parsing event pages by URL, extracting structured event fields with an LLM, storing them in Supabase, and displaying saved events in a simple web page.

## 1) Install and run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python init.py
```

Then open `http://localhost:8000`.

## 2) Supabase SQL

Run this SQL in Supabase SQL editor:

```sql
create extension if not exists pgcrypto;

create table if not exists public.events (
  id uuid primary key default gen_random_uuid(),
  source_url text not null unique,
  title text not null,
  start_at timestamptz null,
  location text null,
  created_at timestamptz not null default now()
);

create table if not exists public.event_sources (
  id uuid primary key default gen_random_uuid(),
  url text not null unique,
  name text null,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);
```

## 3) Environment variables (LLM provider)

- `SUPABASE_URL`: your Supabase project URL
- `SUPABASE_KEY`: API key with write permissions to `events`
- `LLM_API_KEY`: LLM provider API key (`OpenRouter` or `Google AI Studio`)
- `LLM_MODEL`: model name, for OpenRouter example `google/gemini-2.5-flash`
- `LLM_BASE_URL`: provider base URL:
  - OpenRouter: `https://openrouter.ai/api/v1`
  - Gemini direct: `https://generativelanguage.googleapis.com/v1beta`

## 4) API endpoints

- `POST /parse-event` with body:
  ```json
  { "url": "https://example.com/event" }
  ```
- `GET /events` returns saved events sorted by `created_at` descending.

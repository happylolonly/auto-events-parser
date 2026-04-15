# Events Parser MVP

Hackathon - https://buildathon.live/e/buildathon-3-0-vietnamese-edition

---
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

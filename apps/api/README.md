# API App (FastAPI)

## Purpose

Phase 4 operational API providing:

- Market and governance endpoints
- Opportunity + risk pipeline
- Portfolio rank/allocate/exposure endpoints
- Paper execution endpoints

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python seed.py
uvicorn app.main:app --reload --port 8000
```

## Safety

- Paper trading only
- Live execution disabled by default

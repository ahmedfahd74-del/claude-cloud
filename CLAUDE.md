# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zero-Cost AI Multi-Asset Trading Company OS — a paper-trading-only scaffold for a multi-agent trading platform. Key invariant: **`PAPER_TRADING_ONLY=true`** and **`LIVE_EXECUTION_ENABLED=false`** are always on; live execution is intentionally not implemented.

**Tech stack:** FastAPI (Python 3) + Next.js 15 (TypeScript) monorepo, PostgreSQL 16 (Docker), SQLAlchemy 2.0, Alembic, npm workspaces.

## Development Commands

### Starting the stack

```bash
# 1. Start Postgres
npm run db:up

# 2. Start API (FastAPI on :8000)
npm run dev:api

# 3. Start web (Next.js on :3000)
npm run dev:web
```

### Database

```bash
npm run db:migrate    # alembic upgrade head
npm run db:seed       # run apps/api/seed.py
npm run db:down       # stop Docker Postgres
```

### API setup (first time)

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Smoke tests

```bash
npm run smoke:phase4  # Portfolio + Execution
npm run smoke:phase5  # Memory layer
npm run smoke:phase6  # Hardening
```

### Web lint/build

```bash
cd apps/web
npm run lint
npm run build
```

## Architecture

### Data flow

```
Browser (Next.js pages)
  → lib/api.ts (API client, falls back to @trading-os/mock-data if API down)
  → FastAPI routes (app/api/routes.py — all under /api/v1/)
  → Service layer (app/services/)
  → SQLAlchemy models (app/db/models.py)
  → PostgreSQL
```

### Core pipeline

**Scan → Challenge → Risk Review → Rank → Allocate → Paper Execute → Manage → Journal**

1. `OpportunityFactoryService` — scans assets, emits candidates
2. `ChallengerService` — flags each candidate PASS / CHALLENGE / BLOCK
3. `RiskReviewService` — deeper analysis on challenged candidates
4. `RankingService` — weighted scoring (setup quality, regime fit, data confidence, execution quality, portfolio fit, historical expectancy, fragility penalty)
5. `AllocationService` — sizes positions from approved candidates
6. `PaperExecutionService` — simulates fills; position state machine: `ACTIVE → PARTIAL_EXIT_TAKEN → STOPPED | TARGET_HIT | FLAT | CANCELLED`
7. `GovernanceService` — company state machine: `GREEN → YELLOW → RED → BLACKOUT`; kill-switch enforced at execution layer
8. `MemoryService` — trade journals, decision memory, review reports, policy queue

### Monorepo layout

```
apps/api/        FastAPI backend
apps/web/        Next.js frontend (App Router, server components)
packages/
  contracts/     Shared TypeScript types (Candidate, RankingResponse, CompanyState, …)
  ui/            Shared React components (Card, StatTile, ErrorState)
  mock-data/     Fallback responses used when API is unreachable
  config/        Shared config values
services/        Placeholder READMEs for future domain microservices (not implemented)
infrastructure/docker/  docker-compose.yml for Postgres
docs/architecture/      Phase 1-4 design docs
```

### API conventions

- All routes: `/api/v1/<domain>/`
- All responses: camelCase JSON
- Every response includes `paperTradingOnly` and `liveExecutionEnabled` flags
- Single routes file: `apps/api/app/api/routes.py`

### Frontend conventions

- Pages are Next.js server components in `apps/web/app/`
- All data fetching goes through `apps/web/lib/api.ts`
- If the API call fails, the page silently falls back to mock data from `@trading-os/mock-data`
- Shared types come from `@trading-os/contracts` — update contracts when changing API shapes

## Environment Setup

Copy and fill in:
- `.env.example` → `.env` (root)
- `apps/api/.env.example` → `apps/api/.env`
- `apps/web/.env.example` → `apps/web/.env.local`

Critical env vars:
```
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/trading_os
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
PAPER_TRADING_ONLY=true
LIVE_EXECUTION_ENABLED=false
```

## Key Constraints

- Do not implement live trading execution — the architecture intentionally excludes it.
- `StrategyPod` trust grades run A–E; risk controls gate on these.
- The `services/` directory contains placeholder READMEs only — domain microservices are not implemented yet.
- Database migrations live in `apps/api/alembic/versions/` — always create a new migration when changing models, never edit existing ones.

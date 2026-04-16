# Phase 1 Architecture Alignment

This repo follows the agreed company OS scaffold:

- `apps/api` FastAPI + PostgreSQL/Alembic
- `apps/web` Next.js TypeScript app
- `packages/*` shared contracts, UI, config, and mock data
- `services/*` domain service placeholders for phased implementation
- `infrastructure/docker` local infra definitions
- `docs` architecture notes

Safety defaults:

- Paper trading only
- Live execution disabled

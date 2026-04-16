# Zero-Cost AI Multi-Asset Trading Company OS

Paper-first multi-agent trading OS scaffold with canonical camelCase APIs.

> **Safety defaults:** paper trading only (`paperTradingOnly=true`), live execution disabled (`liveExecutionEnabled=false`).

## Quick local startup

1. Copy env templates:

```bash
cp .env.example .env
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env
```

2. Start Postgres:

```bash
npm run db:up
```

3. Run migrations + seed:

```bash
npm run db:migrate
npm run db:seed
```

4. Start API and web (separate terminals):

```bash
npm run dev:api
npm run dev:web
```

## Scripts

```bash
npm run dev:web
npm run dev:api
npm run db:up
npm run db:down
npm run db:migrate
npm run db:seed
npm run smoke:phase4
npm run smoke:phase5
npm run smoke:phase6
```

## API highlights

- Market: `/api/v1/market/*`
- Governance: `/api/v1/governance/*`
- Opportunities: `/api/v1/opportunities/*`
- Portfolio: `/api/v1/portfolio/*`
- Execution (paper): `/api/v1/execution/*`
- Memory/learning: `/api/v1/memory/*`
- Settings visibility: `/api/v1/settings/visibility`

## UI pages

- `/overview`
- `/market-radar`
- `/opportunities`
- `/portfolio`
- `/execution`
- `/memory`
- `/governance`
- `/settings`

## Phase status (what works now)

- Candidate flow: scan -> challenge -> risk review -> rank -> allocate.
- Paper execution flow: allocation guard -> paper order -> simulated fill -> position lifecycle -> management events.
- Memory flow: journal write, decision memory store/search, review generation/retrieval, pod-performance rollup, policy queue review list.
- Settings/config visibility: policy defaults, risk defaults, data/model routing, pod registry status.

## Intentionally deferred

- Any live execution adapters/order routing.
- Automated policy application.
- Production auth/multi-user admin controls.

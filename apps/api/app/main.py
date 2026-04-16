from fastapi import FastAPI

from app.api.routes import (
    execution_router,
    governance_router,
    market_router,
    memory_router,
    opportunity_router,
    portfolio_router,
    risk_router,
    settings_router,
    router as health_router,
)
from app.core.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(health_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(governance_router, prefix="/api")
app.include_router(opportunity_router, prefix="/api")
app.include_router(risk_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(execution_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(settings_router, prefix="/api")


@app.get("/")
def root() -> dict[str, str | bool]:
    return {
        "name": settings.app_name,
        "mode": "paper-trading-only" if settings.paper_trading_only else "unknown",
        "paper_trading_only": settings.paper_trading_only,
        "live_execution_enabled": settings.live_execution_enabled,
    }

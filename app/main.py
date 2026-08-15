"""
UNILAG Premed Nomination & Voting Portal — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.database import connect_db, disconnect_db
from app.routers import auth, identity, categories, nominations, ballots, votes, results

settings = get_settings()

# ---------------------------------------------------------------------------
# Rate limiter (in-memory for single-instance; swap for Redis on Railway)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Lifespan — DB connect/disconnect
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await disconnect_db()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="UNILAG Premed Nomination & Voting Portal",
    description=(
        "Secure, anonymous nomination and voting portal for the UNILAG Premed Department. "
        "Identity (matric numbers) and content (nominations/votes) are stored in completely "
        "separate collections with no referential link."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS — only allow the configured frontend origin
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,  # Required for httpOnly cookie auth
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(identity.router)
app.include_router(categories.router)
app.include_router(nominations.router)
app.include_router(ballots.router)
app.include_router(votes.router)
app.include_router(results.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "premed-nomination-portal"}

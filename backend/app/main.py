"""
FastAPI application entrypoint.

Wires up routers, middleware, exception handlers, structured logging,
and graceful shutdown. CORS is configured permissively here — in
production you'd restrict origins to your frontend domain.
"""

import signal
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import dispose_engine
from app.exceptions import register_exception_handlers
from app.routes import auth, projects, tasks

# Configure structured JSON logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle hooks."""
    log.info("server_starting")
    yield
    log.info("server_shutting_down")
    await dispose_engine()


app = FastAPI(
    title="TaskFlow API",
    description="A task management system with projects, tasks, and user authentication.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permissive for development; tighten origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)

# Register global exception handlers
register_exception_handlers(app)


# Graceful shutdown on SIGTERM (Docker sends this on container stop)
def _handle_sigterm(signum, frame):
    log.info("received_sigterm")
    sys.exit(0)


signal.signal(signal.SIGTERM, _handle_sigterm)

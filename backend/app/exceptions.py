"""
Custom exceptions and global error handlers.

Maps application-level errors to the spec-required JSON responses:
  - 400: { "error": "validation failed", "fields": { ... } }
  - 401: { "error": "unauthorized" }
  - 403: { "error": "forbidden" }
  - 404: { "error": "not found" }
  - 409: { "error": "..." }
  - 500: { "error": "internal server error" }  (catch-all, never leaks stack traces)
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

log = structlog.get_logger()


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""
    pass


class ForbiddenError(Exception):
    """Raised when the user lacks permission for the action."""
    pass


class ConflictError(Exception):
    """Raised on uniqueness violations (e.g., duplicate email)."""
    def __init__(self, message: str = "conflict"):
        self.message = message


class UnauthorizedError(Exception):
    """Raised when authentication is missing or invalid."""
    pass


class BadRequestError(Exception):
    """Raised for malformed input that isn't a Pydantic validation error."""
    def __init__(self, message: str = "bad request", fields: dict | None = None):
        self.message = message
        self.fields = fields or {}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all custom exception handlers to the app instance."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_req: Request, exc: RequestValidationError):
        """Transform Pydantic errors into the spec's { error, fields } format."""
        fields: dict[str, str] = {}
        for err in exc.errors():
            loc = err.get("loc", [])
            field_name = str(loc[-1]) if loc else "unknown"
            fields[field_name] = err.get("msg", "invalid")
        return JSONResponse(status_code=400, content={"error": "validation failed", "fields": fields})

    @app.exception_handler(BadRequestError)
    async def bad_request_handler(_req: Request, exc: BadRequestError):
        body = {"error": exc.message}
        if exc.fields:
            body["fields"] = exc.fields
        return JSONResponse(status_code=400, content=body)

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_req: Request, _exc: NotFoundError):
        return JSONResponse(status_code=404, content={"error": "not found"})

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(_req: Request, _exc: ForbiddenError):
        return JSONResponse(status_code=403, content={"error": "forbidden"})

    @app.exception_handler(ConflictError)
    async def conflict_handler(_req: Request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"error": exc.message})

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(_req: Request, _exc: UnauthorizedError):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_req: Request, exc: IntegrityError):
        """Handle DB constraint violations (FK, unique) with a clean 409/400."""
        detail = str(exc.orig) if exc.orig else str(exc)
        if "unique" in detail.lower() or "duplicate" in detail.lower():
            return JSONResponse(status_code=409, content={"error": "duplicate value violates unique constraint"})
        if "foreign key" in detail.lower() or "not present" in detail.lower():
            return JSONResponse(status_code=400, content={"error": "referenced resource does not exist"})
        log.error("integrity_error", error=detail)
        return JSONResponse(status_code=400, content={"error": "data integrity error"})

    @app.exception_handler(Exception)
    async def catch_all_handler(_req: Request, exc: Exception):
        """Catch-all so unhandled errors never leak stack traces to the client."""
        log.error("unhandled_exception", error=str(exc), type=type(exc).__name__)
        return JSONResponse(status_code=500, content={"error": "internal server error"})

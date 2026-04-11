"""
Custom exceptions and global error handlers.

Maps application-level errors to the spec-required JSON responses:
  - 400: { "error": "validation failed", "fields": { ... } }
  - 401: { "error": "unauthorized" }
  - 403: { "error": "forbidden" }
  - 404: { "error": "not found" }
  - 409: { "error": "..." }
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


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


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all custom exception handlers to the app instance."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_req: Request, exc: RequestValidationError):
        """Transform Pydantic errors into the spec's { error, fields } format."""
        fields: dict[str, str] = {}
        for err in exc.errors():
            loc = err.get("loc", [])
            # loc is typically ("body", "field_name") — grab the last element
            field_name = str(loc[-1]) if loc else "unknown"
            fields[field_name] = err.get("msg", "invalid")
        return JSONResponse(status_code=400, content={"error": "validation failed", "fields": fields})

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

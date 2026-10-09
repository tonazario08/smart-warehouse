"""Stable API error response models and exception handlers."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    """A machine-readable error code with a safe client-facing message."""

    code: str
    message: str
    fields: dict[str, list[str]] | None = None


class ErrorResponse(BaseModel):
    """The common envelope returned for API errors."""

    detail: ErrorDetail


class DomainError(Exception):
    """An expected domain failure that is safe to describe to API clients."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        fields: dict[str, list[str]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields


def _error_response(
    status_code: int,
    code: str,
    message: str,
    fields: dict[str, list[str]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code, "message": message, "fields": fields}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install error handlers that never expose database or exception details."""

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message, exc.fields)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, list[str]] = {}
        for item in exc.errors():
            key = ".".join(str(part) for part in item["loc"] if part != "body") or "request"
            fields.setdefault(key, []).append(str(item["msg"]))
        return _error_response(
            422,
            "REQUEST_VALIDATION_ERROR",
            "Request validation failed.",
            fields,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("HTTP %s error: %r", exc.status_code, exc.detail)
            return _error_response(500, "INTERNAL_SERVER_ERROR", "An internal error occurred.")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _error_response(exc.status_code, f"HTTP_{exc.status_code}_ERROR", message)

    @app.exception_handler(IntegrityError)
    async def integrity_error(_: Request, __: IntegrityError) -> JSONResponse:
        logger.warning("Database integrity error")
        return _error_response(409, "DATABASE_CONFLICT", "Database conflict occurred.")

    @app.exception_handler(Exception)
    async def unhandled_error(_: Request, __: Exception) -> JSONResponse:
        logger.exception("Unhandled application error")
        return _error_response(500, "INTERNAL_SERVER_ERROR", "An internal error occurred.")

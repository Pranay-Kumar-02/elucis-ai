"""Typed application errors and the single error envelope (D09 section 2, IR-06).

Services raise ``AppError`` subclasses; handlers here turn them into
``{"error": {"code", "message", "details", "request_id"}}``. Messages never contain stack
traces, SQL, file paths, prompts or customer text: unexpected exceptions are logged with the
request ID and returned as a generic ``internal_error``.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from elucis.core.logging import request_id_var

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = HTTPStatus.BAD_REQUEST
    code: str = "bad_request"
    message: str = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or []
        self.headers = headers
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = "not_found"
    message = "The resource was not found."


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "conflict"
    message = "The request conflicts with the current state."


class ValidationFailedError(AppError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "validation_failed"
    message = "The request is not valid."


class FileTooLargeError(AppError):
    status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    code = "file_too_large"
    message = "The upload is larger than the allowed size."


class PayloadTooLargeError(AppError):
    status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    code = "bad_request"
    message = "The request body is larger than the allowed size."


class UnsupportedFormatError(AppError):
    status_code = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_format"
    message = "Only CSV, JSON and TXT files are supported."


class ModelUnavailableError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "model_unavailable"
    message = "The local model runtime is not reachable."


class DatabaseUnavailableError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "database_unavailable"
    message = "The database is not reachable."


class NotAuthenticatedError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "not_authenticated"
    message = "Sign in to continue."


class SessionExpiredError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "session_expired"
    message = "Your session has ended. Sign in again."


class InvalidCredentialsError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "invalid_credentials"
    message = "The email or password is not correct."


class CsrfMissingError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "csrf_missing"
    message = "The X-CSRF-Token header is required for this request."


class CsrfInvalidError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "csrf_invalid"
    message = "The X-CSRF-Token header does not match this session."


class ForbiddenRoleError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "forbidden_role"
    message = "Your role in this workspace does not allow this action."


class EmailTakenError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "email_taken"
    message = "An account with this email already exists."


class TooManyAttemptsError(AppError):
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    code = "too_many_attempts"
    message = "Too many failed sign-in attempts. Try again later."


class EncryptionUnavailableError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "encryption_unavailable"
    message = "Encryption is not configured (APP_ENCRYPTION_KEY)."


# Default codes for framework-raised HTTP errors (routing, method, size).
_HTTP_CODES: dict[int, str] = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden_role",
    404: "not_found",
    405: "method_not_allowed",
    413: "bad_request",
    415: "unsupported_format",
    429: "rate_limited",
}


def error_body(
    code: str, message: str, details: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": request_id_var.get(),
        }
    }


def _loc_to_field(loc: tuple[Any, ...] | list[Any]) -> str:
    parts = [str(p) for p in loc if p not in {"body", "query", "path", "header", "cookie"}]
    return ".".join(parts) or str(loc[0] if loc else "request")


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101 - registered only for AppError
    if exc.status_code >= 500:
        logger.warning("service unavailable", extra={"code": exc.code})
    return JSONResponse(
        error_body(exc.code, exc.message, exc.details),
        status_code=int(exc.status_code),
        headers=exc.headers,
    )


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    details = [
        {"field": _loc_to_field(err.get("loc", ())), "issue": err.get("type", "invalid")}
        for err in exc.errors()
    ]
    return JSONResponse(
        error_body("validation_failed", "The request is not valid.", details),
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
    )


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    code = _HTTP_CODES.get(
        exc.status_code, "bad_request" if exc.status_code < 500 else "internal_error"
    )
    try:
        message = HTTPStatus(exc.status_code).phrase + "."
    except ValueError:
        message = "The request could not be processed."
    return JSONResponse(
        error_body(code, message),
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    # Unexpected exceptions are caught by RequestContextMiddleware so that the response
    # still carries the request ID (Starlette's own last-resort handler runs outside it).

"""Error envelope `{"error": {"code", "message", "details"}}` (SRS §8) and the exception
that carries it end-to-end from wherever it's raised to the HTTP response.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: list[Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        super().__init__(message)

    def to_envelope(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


def unauthorized(message: str = "Authentication required.") -> ApiError:
    return ApiError(status_code=401, code="unauthorized", message=message)


def forbidden(message: str = "You do not have permission to perform this action.") -> ApiError:
    return ApiError(status_code=403, code="forbidden", message=message)


def password_change_required(
    message: str = "You must change your password before continuing.",
) -> ApiError:
    return ApiError(status_code=403, code="password_change_required", message=message)


def not_found(message: str = "Resource not found.") -> ApiError:
    return ApiError(status_code=404, code="not_found", message=message)


def conflict(message: str) -> ApiError:
    return ApiError(status_code=409, code="conflict", message=message)


def bad_request(message: str, details: list[Any] | None = None) -> ApiError:
    return ApiError(status_code=400, code="bad_request", message=message, details=details)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_envelope())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": exc.errors(),
                }
            },
        )

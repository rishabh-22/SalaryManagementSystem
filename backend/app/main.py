from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, employees, insights, meta, users
from app.core.config import settings
from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    DomainError,
    NotFoundError,
    UnprocessableError,
)

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    BusinessRuleError: 400,
}


def _register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(UnprocessableError)
    async def _unprocessable(_: Request, exc: UnprocessableError) -> JSONResponse:
        detail = [{"loc": exc.loc, "msg": exc.message, "type": "value_error"}]
        return JSONResponse(status_code=422, content={"detail": detail})

    @application.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        status = _STATUS_BY_ERROR.get(type(exc), 400)
        return JSONResponse(status_code=status, content={"detail": exc.message})


def create_app() -> FastAPI:
    application = FastAPI(title="ACME Salary Management API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    _register_error_handlers(application)

    api = APIRouter(prefix="/api")

    @api.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for module in (meta, auth, users, employees, insights):
        api.include_router(module.router)
    application.include_router(api)
    return application


app = create_app()

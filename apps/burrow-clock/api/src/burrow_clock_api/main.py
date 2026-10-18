from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from burrow_clock_api.api.dependencies import SharingStorage
from burrow_clock_api.api.sharing import router
from burrow_clock_api.application.repositories import SharingStateConflict


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        app.state.sharing_storage.close()


app = FastAPI(title="The Burrow Clock API", lifespan=lifespan)
app.state.sharing_storage = SharingStorage()
app.include_router(router)


@app.middleware("http")
async def metadata_no_store(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/") and request.url.path != "/api/v1/health":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(SQLAlchemyError)
async def persistence_unavailable(request: Request, error: SQLAlchemyError):
    return JSONResponse(status_code=503, content={"detail": "Persistence unavailable"})


@app.exception_handler(SharingStateConflict)
async def state_conflict(request: Request, error: SharingStateConflict):
    return JSONResponse(status_code=409, content={"detail": "Transition conflicts with current consent state"})


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError):
    # Never reflect unexpected request fields, credentials or parser details.
    return JSONResponse(status_code=422, content={"detail": "Invalid request data"})


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/api/v1/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="burrow-clock-api")

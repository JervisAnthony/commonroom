"""Pensieve application composition; no automatic configuration or loading."""

from fastapi import FastAPI
from pydantic import BaseModel

from pensieve_api.claim_passage_api import router
from pensieve_api.domain.source_passages import PassageStore


class HealthResponse(BaseModel):
    status: str
    service: str


def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="pensieve-api")


def create_app(*, passage_store: PassageStore | None = None) -> FastAPI:
    if passage_store is not None and not isinstance(passage_store, PassageStore):
        raise TypeError("passage_store must be a PassageStore or None")
    application = FastAPI(title="Pensieve API")
    application.state.passage_store = passage_store
    application.add_api_route(
        "/api/v1/health", health_check, methods=["GET"], response_model=HealthResponse,
    )
    application.include_router(router)
    return application


app = create_app()

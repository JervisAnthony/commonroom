"""Pensieve's public health API; no external infrastructure required."""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Pensieve API")


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/api/v1/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="pensieve-api")

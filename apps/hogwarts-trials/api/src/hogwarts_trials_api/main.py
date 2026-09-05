from fastapi import FastAPI
from pydantic import BaseModel

from hogwarts_trials_api.api.quizzes import router as quizzes_router

app = FastAPI(title="Hogwarts Trials API")
app.include_router(quizzes_router)


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/api/v1/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="hogwarts-trials-api",
    )

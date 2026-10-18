"""Trusted identity, injectable UTC clock and lazy application-owned persistence."""

from datetime import datetime, timezone
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from burrow_clock_api.application.identity import AuthenticatedPrincipal
from burrow_clock_api.application.repositories import AuthorizedSharingRepository
from burrow_clock_api.infrastructure.database import (
    create_db_engine, create_session_factory, get_database_url,
)
from burrow_clock_api.infrastructure.postgres_sharing_repository import PostgresSharingRepository


def get_current_principal() -> AuthenticatedPrincipal:
    """Fail closed until a real adapter verifies credentials; headers/UUIDs are not credentials."""
    raise HTTPException(status_code=401, detail="Authentication required")


PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_current_principal)]


def get_now() -> datetime:
    return datetime.now(timezone.utc)


class SharingStorage:
    """One lazy engine per application, serialized initialization and explicit shutdown."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._engine = None
        self._repository = None

    def get(self) -> AuthorizedSharingRepository:
        with self._lock:
            if self._repository is None:
                engine = create_db_engine(get_database_url(), connect_args={"connect_timeout": 5})
                try:
                    repository = PostgresSharingRepository(create_session_factory(engine))
                except Exception:
                    engine.dispose()
                    raise
                self._engine, self._repository = engine, repository
            return self._repository

    def close(self) -> None:
        with self._lock:
            if self._engine is not None:
                self._engine.dispose()
            self._engine = self._repository = None


def get_sharing_repository(request: Request, principal: PrincipalDep) -> AuthorizedSharingRepository:
    # The nested dependency must succeed before storage can initialize.
    try:
        return request.app.state.sharing_storage.get()
    except (ValueError, SQLAlchemyError):
        raise HTTPException(status_code=503, detail="Persistence unavailable") from None


RepositoryDep = Annotated[AuthorizedSharingRepository, Depends(get_sharing_repository)]
NowDep = Annotated[datetime, Depends(get_now)]

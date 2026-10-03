"""FastAPI dependency providers for Hogwarts Trials API.

Provides dependency injection seams for application ports, allowing routes to
depend on abstractions (such as QuizRepository) while concrete implementations
are configured at runtime and easily overridden during testing.
"""

from collections.abc import Mapping
from typing import Any

from hogwarts_trials_api.application.quiz_attempt_repository import (
    QuizAttemptRepository,
)
from hogwarts_trials_api.application.quiz_repository import QuizRepository
from hogwarts_trials_api.infrastructure.database import (
    create_db_engine,
    create_session_factory,
    get_database_url,
    get_repository_backend,
)
from hogwarts_trials_api.infrastructure.in_memory_quiz_attempt_repository import (
    InMemoryQuizAttemptRepository,
)
from hogwarts_trials_api.infrastructure.in_memory_quiz_repository import (
    InMemoryQuizRepository,
)
from hogwarts_trials_api.infrastructure.postgres_quiz_attempt_repository import (
    PostgresQuizAttemptRepository,
)
from hogwarts_trials_api.infrastructure.postgres_quiz_repository import (
    PostgresQuizRepository,
)

_quiz_repository: QuizRepository | None = None
_quiz_attempt_repository: QuizAttemptRepository | None = None


def build_quiz_repository(
    backend: str | None = None,
    database_url: str | None = None,
    env: Mapping[str, str] | None = None,
    **engine_kwargs: Any,
) -> QuizRepository:
    """Construct a QuizRepository based on explicit arguments or environment settings.

    Supported backends:
    - 'memory' (default): In-memory synthetic demonstration repository. No database engine is constructed.
    - 'postgres': PostgreSQL-backed relational repository. Requires a valid database URL.
    """
    selected_backend = backend or get_repository_backend(env)

    if selected_backend == "memory":
        return InMemoryQuizRepository()

    if selected_backend == "postgres":
        url = database_url or get_database_url(env)
        engine = create_db_engine(url, **engine_kwargs)
        session_factory = create_session_factory(engine)
        return PostgresQuizRepository(session_factory=session_factory)

    raise ValueError(
        f"Unsupported quiz repository backend: {selected_backend!r}. "
        "Supported backends are: 'memory', 'postgres'."
    )


def get_quiz_repository() -> QuizRepository:
    """Provide the application QuizRepository instance.

    Lazily instantiates the repository on first access according to environment configuration.
    """
    global _quiz_repository
    if _quiz_repository is None:
        _quiz_repository = build_quiz_repository()
    return _quiz_repository


def set_quiz_repository(repository: QuizRepository | None) -> None:
    """Set or reset the cached QuizRepository instance."""
    global _quiz_repository
    _quiz_repository = repository


def reset_quiz_repository() -> None:
    """Reset cached repository instances so next access re-evaluates configuration."""
    global _quiz_repository, _quiz_attempt_repository
    _quiz_repository = None
    _quiz_attempt_repository = None


def build_quiz_attempt_repository(
    backend: str | None = None,
    database_url: str | None = None,
    env: Mapping[str, str] | None = None,
    session_factory: Any | None = None,
    **engine_kwargs: Any,
) -> QuizAttemptRepository:
    """Construct a QuizAttemptRepository based on explicit arguments or environment settings.

    Uses the same backend selection mode (HOGWARTS_TRIALS_QUIZ_REPOSITORY) as QuizRepository.
    Supported backends:
    - 'memory' (default): In-memory quiz attempt repository.
    - 'postgres': PostgreSQL-backed relational attempt repository.
    """
    selected_backend = backend or get_repository_backend(env)

    if selected_backend == "memory":
        return InMemoryQuizAttemptRepository()

    if selected_backend == "postgres":
        if session_factory is None:
            url = database_url or get_database_url(env)
            engine = create_db_engine(url, **engine_kwargs)
            session_factory = create_session_factory(engine)
        return PostgresQuizAttemptRepository(session_factory=session_factory)

    raise ValueError(
        f"Unsupported quiz repository backend: {selected_backend!r}. "
        "Supported backends are: 'memory', 'postgres'."
    )


def get_quiz_attempt_repository() -> QuizAttemptRepository:
    """Provide the application QuizAttemptRepository instance.

    Lazily instantiates the repository on first access according to environment configuration.
    """
    global _quiz_attempt_repository
    if _quiz_attempt_repository is None:
        _quiz_attempt_repository = build_quiz_attempt_repository()
    return _quiz_attempt_repository


def set_quiz_attempt_repository(
    repository: QuizAttemptRepository | None,
) -> None:
    """Set or reset the cached QuizAttemptRepository instance."""
    global _quiz_attempt_repository
    _quiz_attempt_repository = repository


def reset_quiz_attempt_repository() -> None:
    """Reset the cached QuizAttemptRepository instance."""
    global _quiz_attempt_repository
    _quiz_attempt_repository = None

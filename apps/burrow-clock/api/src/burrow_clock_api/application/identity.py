"""Burrow's trusted identity value; identifiers alone never authenticate callers."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Supplied only after a trusted authentication adapter validates credentials."""

    user_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, UUID):
            raise TypeError("user_id must be a UUID")

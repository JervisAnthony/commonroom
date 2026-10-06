"""Product-local contract for identity established by future authentication."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Identity supplied by a future trusted authentication adapter/dependency.

    Construction validates the identifier type; it does not authenticate anyone.
    Never construct this value from arbitrary client-controlled request data.
    """

    user_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, UUID):
            raise TypeError("user_id must be a UUID")

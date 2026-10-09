"""Active relationship facts, independent of participant ordering."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Friendship:
    """Two distinct members of a currently active relationship only."""

    friendship_id: UUID
    user_a_id: UUID
    user_b_id: UUID

    def __post_init__(self) -> None:
        for name in ("friendship_id", "user_a_id", "user_b_id"):
            if not isinstance(getattr(self, name), UUID):
                raise TypeError(f"{name} must be a UUID")
        if self.user_a_id == self.user_b_id:
            raise ValueError("friendship members must be distinct")

    def contains_user(self, user_id: UUID) -> bool:
        return isinstance(user_id, UUID) and user_id in (self.user_a_id, self.user_b_id)

    def connects(self, user_one_id: UUID, user_two_id: UUID) -> bool:
        return (
            user_one_id != user_two_id
            and self.contains_user(user_one_id)
            and self.contains_user(user_two_id)
        )

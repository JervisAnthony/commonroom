"""Source attribution contracts, not verification of canonical truth or licensing.

Statements and roleplay must be originally phrased. Structural validation cannot
verify originality, source authenticity, licensing, or support for a claim.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CanonTier(StrEnum):
    """Source categories; none establishes correctness or a ranking of truth."""

    BOOK = "book"
    FILM = "film"
    EXPANDED_PUBLICATION = "expanded_publication"


class SourceLocator(BaseModel):
    """A declared location within a source; its existence is not verified."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["chapter", "scene", "section", "other"]
    reference: NonBlankText


class SourceReference(BaseModel):
    """Identifiable source metadata supplied by the caller, not authenticated."""

    model_config = ConfigDict(extra="forbid", strict=True)

    source_id: NonBlankText
    title: NonBlankText
    canon_tier: CanonTier
    locator: SourceLocator

    @field_validator("canon_tier", mode="before")
    @classmethod
    def parse_canon_tier(cls, value: object) -> CanonTier:
        # Accept exact string values in Python and JSON without coercing other types.
        if not isinstance(value, str):
            raise ValueError("canon_tier must be a string source category")
        return CanonTier(value)


class SourcedLoreClaim(BaseModel):
    """An originally phrased attributed statement, not a verified canonical fact."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["sourced_lore"]
    statement: NonBlankText
    sources: Annotated[list[SourceReference], Field(min_length=1)]


class GeneratedRoleplay(BaseModel):
    """Original generated content, explicitly distinct from attributed lore."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["generated_roleplay"]
    content: NonBlankText

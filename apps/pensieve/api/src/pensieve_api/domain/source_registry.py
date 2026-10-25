"""Exact metadata matching only; no authenticity or claim-support verification."""

from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pensieve_api.domain.provenance import (
    CanonTier,
    NonBlankText,
    SourceLocator,
    SourceReference,
    SourcedLoreClaim,
)


class RegisteredSource(BaseModel):
    """Caller-declared source metadata with a nonempty, unique locator list."""

    model_config = ConfigDict(extra="forbid", strict=True)

    source_id: NonBlankText
    title: NonBlankText
    canon_tier: CanonTier
    locators: Annotated[list[SourceLocator], Field(min_length=1)]

    @field_validator("canon_tier", mode="before")
    @classmethod
    def parse_canon_tier(cls, value: object) -> CanonTier:
        return SourceReference.parse_canon_tier(value)

    @field_validator("locators")
    @classmethod
    def reject_duplicate_locators(cls, value: list[SourceLocator]) -> list[SourceLocator]:
        keys = {(locator.kind, locator.reference) for locator in value}
        if len(keys) != len(value):
            raise ValueError("locators must be unique after normalization")
        return value


class ResolutionStatus(StrEnum):
    """Registry lookup outcomes, never factual or canonical verification."""

    SOURCE_NOT_REGISTERED = "SOURCE_NOT_REGISTERED"
    SOURCE_METADATA_MISMATCH = "SOURCE_METADATA_MISMATCH"
    LOCATOR_NOT_REGISTERED = "LOCATOR_NOT_REGISTERED"
    REGISTRY_MATCH = "REGISTRY_MATCH"


@dataclass(frozen=True)
class ReferenceResolution:
    """Outcome with an independent snapshot of the submitted reference."""

    reference: SourceReference
    status: ResolutionStatus


@dataclass(frozen=True)
class ClaimResolution:
    """Ordered outcomes; aggregate success says nothing about the statement."""

    references: tuple[ReferenceResolution, ...]

    @property
    def all_references_registered(self) -> bool:
        return bool(self.references) and all(
            result.status is ResolutionStatus.REGISTRY_MATCH for result in self.references
        )


class SourceRegistry:
    """An unseeded, in-memory snapshot of a finite source collection.

    Stored values contain only immutable metadata, never caller-owned models.
    Construct a new registry to change its registered sources.
    """

    def __init__(self, sources: Collection[RegisteredSource]) -> None:
        self._sources: dict[str, tuple[str, CanonTier, frozenset[tuple[str, str]]]] = {}
        for source in sources:
            if not isinstance(source, RegisteredSource):
                raise TypeError("sources must contain RegisteredSource objects")
            # Revalidate snapshots because existing Pydantic models are mutable.
            snapshot = RegisteredSource.model_validate(source.model_dump())
            if snapshot.source_id in self._sources:
                raise ValueError(f"duplicate source_id: {snapshot.source_id}")
            self._sources[snapshot.source_id] = (
                snapshot.title,
                snapshot.canon_tier,
                frozenset((locator.kind, locator.reference) for locator in snapshot.locators),
            )

    def resolve_reference(self, reference: SourceReference) -> ReferenceResolution:
        """Match ID, then title/tier, then locator kind/reference exactly."""
        if not isinstance(reference, SourceReference):
            raise TypeError("reference must be a SourceReference")
        snapshot = SourceReference.model_validate(reference.model_dump())
        source = self._sources.get(snapshot.source_id)
        if source is None:
            status = ResolutionStatus.SOURCE_NOT_REGISTERED
        elif (snapshot.title, snapshot.canon_tier) != source[:2]:
            status = ResolutionStatus.SOURCE_METADATA_MISMATCH
        elif (snapshot.locator.kind, snapshot.locator.reference) not in source[2]:
            status = ResolutionStatus.LOCATOR_NOT_REGISTERED
        else:
            status = ResolutionStatus.REGISTRY_MATCH
        return ReferenceResolution(reference=snapshot, status=status)

    def resolve_claim(self, claim: SourcedLoreClaim) -> ClaimResolution:
        """Resolve every attribution, preserving order and duplicates.

        GeneratedRoleplay is rejected; no statement is interpreted as evidence.
        """
        if not isinstance(claim, SourcedLoreClaim):
            raise TypeError("claim must be a SourcedLoreClaim")
        snapshot = SourcedLoreClaim.model_validate(claim.model_dump())
        return ClaimResolution(tuple(self.resolve_reference(source) for source in snapshot.sources))

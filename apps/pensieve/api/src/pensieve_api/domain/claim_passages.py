"""Ordered local passage availability for declared citations, never claim support."""

from dataclasses import dataclass

from pensieve_api.domain.provenance import SourceReference, SourcedLoreClaim
from pensieve_api.domain.source_passages import PassageStore, SourcePassage
from pensieve_api.domain.source_registry import ResolutionStatus


@dataclass(frozen=True)
class ReferencePassages:
    """Submitted citation and lookup outcome with independent mutable snapshots."""

    reference: SourceReference
    status: ResolutionStatus
    passages: tuple[SourcePassage, ...]


@dataclass(frozen=True)
class ClaimPassageLookup:
    """Normalized supplied statement and ordered outcomes, without interpretation."""

    statement: str
    references: tuple[ReferencePassages, ...]

    @property
    def all_references_registered(self) -> bool:
        return bool(self.references) and all(
            result.status is ResolutionStatus.REGISTRY_MATCH for result in self.references
        )

    @property
    def all_references_have_passages(self) -> bool:
        return bool(self.references) and all(
            result.status is ResolutionStatus.REGISTRY_MATCH and bool(result.passages)
            for result in self.references
        )


def lookup_claim_passages(claim: SourcedLoreClaim, store: PassageStore) -> ClaimPassageLookup:
    """Revalidate the whole claim, then look up every citation through the store.

    Frozen containers do not freeze nested Pydantic copies. No statement is
    generated or evaluated; the aggregates describe metadata and text availability.
    """
    if not isinstance(claim, SourcedLoreClaim):
        raise TypeError("claim must be a SourcedLoreClaim")
    if not isinstance(store, PassageStore):
        raise TypeError("store must be a PassageStore")
    snapshot = SourcedLoreClaim.model_validate(claim.model_dump(warnings=False))
    references = []
    for reference in snapshot.sources:
        result = store.lookup_reference(reference)
        references.append(ReferencePassages(
            reference=reference.model_copy(deep=True),
            status=result.status,
            passages=result.passages,
        ))
    return ClaimPassageLookup(snapshot.statement, tuple(references))

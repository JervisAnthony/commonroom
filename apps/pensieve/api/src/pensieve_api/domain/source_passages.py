"""Caller-supplied local text at declared citations, never verified evidence."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from pensieve_api.domain.provenance import NonBlankText, SourceReference
from pensieve_api.domain.source_registry import ResolutionStatus, SourceRegistry


class SourcePassage(BaseModel):
    """A caller declaration; neither prose fidelity nor claim support is checked."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["source_passage"]
    passage_id: NonBlankText
    reference: SourceReference
    text: NonBlankText


@dataclass(frozen=True)
class PassageLookup:
    """Frozen outer result with independent, mutable nested passage snapshots."""

    status: ResolutionStatus
    passages: tuple[SourcePassage, ...]


class PassageStore:
    """Explicit local text bound to the supplied registry metadata snapshot.

    Later catalog changes require a new registry and store. Availability says
    nothing about authenticity, rights, canonical status or substantive support.
    """

    def __init__(self, registry: SourceRegistry, passages: Sequence[SourcePassage]) -> None:
        if not isinstance(registry, SourceRegistry):
            raise TypeError("registry must be a SourceRegistry")
        if not isinstance(passages, Sequence) or isinstance(passages, (str, bytes, bytearray)):
            raise TypeError("passages must be an ordered finite sequence of SourcePassage objects")
        records = []
        seen = set()
        for passage in passages:
            if not isinstance(passage, SourcePassage):
                raise TypeError("passages must contain SourcePassage objects")
            snapshot = SourcePassage.model_validate(passage.model_dump(warnings=False))
            if snapshot.passage_id in seen:
                raise ValueError(f"duplicate passage_id: {snapshot.passage_id}")
            seen.add(snapshot.passage_id)
            resolution = registry.resolve_reference(snapshot.reference)
            if resolution.status is not ResolutionStatus.REGISTRY_MATCH:
                raise ValueError(f"passage {snapshot.passage_id}: {resolution.status.value}")
            records.append(snapshot.model_dump_json())
        self._registry = registry
        self._records = tuple(records)

    def lookup_reference(self, reference: SourceReference) -> PassageLookup:
        """Resolve metadata first, then return all exact matches in input order."""
        if not isinstance(reference, SourceReference):
            raise TypeError("reference must be a SourceReference")
        snapshot = SourceReference.model_validate(reference.model_dump(warnings=False))
        resolution = self._registry.resolve_reference(snapshot)
        if resolution.status is not ResolutionStatus.REGISTRY_MATCH:
            return PassageLookup(resolution.status, ())
        passages = tuple(SourcePassage.model_validate_json(record) for record in self._records)
        return PassageLookup(resolution.status, tuple(
            passage for passage in passages if passage.reference == resolution.reference
        ))

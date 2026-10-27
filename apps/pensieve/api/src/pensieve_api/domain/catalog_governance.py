"""Opt-in revision acknowledgment, not authenticated approval or adoption history."""

from dataclasses import dataclass
import json
from typing import Literal

from pensieve_api.domain.provenance import CanonTier
from pensieve_api.domain.source_catalog import SourceCatalog
from pensieve_api.domain.source_registry import SourceRegistry


LocatorPair = tuple[str, str]


@dataclass(frozen=True)
class EntrySnapshot:
    """Independent normalized entry, retaining the declared locator sequence."""

    source_id: str
    title: str
    canon_tier: CanonTier
    locators: tuple[LocatorPair, ...]
    curation_status: Literal["proposed", "metadata_reviewed"]
    curation_note: str


@dataclass(frozen=True)
class SourceChange:
    """Addition, removal or modification keyed by exact normalized source ID."""

    source_id: str
    before: EntrySnapshot | None
    after: EntrySnapshot | None
    added_locators: tuple[LocatorPair, ...]
    removed_locators: tuple[LocatorPair, ...]


@dataclass(frozen=True)
class CatalogComparison:
    """Full-document bindings and inspectable changes, with no mutable aliases."""

    previous_document: str
    candidate_document: str
    previous_entry_order: tuple[str, ...]
    candidate_entry_order: tuple[str, ...]
    source_changes: tuple[SourceChange, ...]
    eligibility_added: tuple[str, ...]
    eligibility_removed: tuple[str, ...]
    eligible_metadata_changed: tuple[str, ...]

    @property
    def has_changes(self) -> bool:
        return self.previous_document != self.candidate_document

    @property
    def registry_metadata_changed(self) -> bool:
        return bool(self.eligibility_added or self.eligibility_removed or self.eligible_metadata_changed)


@dataclass(frozen=True)
class CatalogAcknowledgment:
    """Caller declaration bound to two documents; no reviewer identity or authority."""

    previous_document: str
    candidate_document: str


def _validated_snapshot(catalog: SourceCatalog) -> SourceCatalog:
    if not isinstance(catalog, SourceCatalog):
        raise TypeError("catalog must be a SourceCatalog")
    return SourceCatalog.model_validate(catalog.model_dump(warnings=False))


def _document(catalog: SourceCatalog) -> str:
    # ASCII escapes fix the representation independently of output encodings.
    return json.dumps(catalog.model_dump(mode="json"), sort_keys=True,
                      ensure_ascii=True, separators=(",", ":"))


def _entries(catalog: SourceCatalog) -> tuple[EntrySnapshot, ...]:
    return tuple(EntrySnapshot(
        source_id=entry.source.source_id,
        title=entry.source.title,
        canon_tier=entry.source.canon_tier,
        locators=tuple((locator.kind, locator.reference) for locator in entry.source.locators),
        curation_status=entry.curation_status,
        curation_note=entry.curation_note,
    ) for entry in catalog.entries)


def _matching_metadata(entry: EntrySnapshot) -> tuple[str, CanonTier, frozenset[LocatorPair]]:
    return entry.title, entry.canon_tier, frozenset(entry.locators)


def _compare_snapshots(previous: SourceCatalog, candidate: SourceCatalog) -> CatalogComparison:
    before_entries, after_entries = _entries(previous), _entries(candidate)
    before = {entry.source_id: entry for entry in before_entries}
    after = {entry.source_id: entry for entry in after_entries}
    changes = []
    for source_id in sorted(before.keys() | after.keys()):
        old, new = before.get(source_id), after.get(source_id)
        if old != new:
            old_locators = set(old.locators) if old else set()
            new_locators = set(new.locators) if new else set()
            changes.append(SourceChange(
                source_id, old, new,
                tuple(sorted(new_locators - old_locators)),
                tuple(sorted(old_locators - new_locators)),
            ))
    old_eligible = {key for key, entry in before.items() if entry.curation_status == "metadata_reviewed"}
    new_eligible = {key for key, entry in after.items() if entry.curation_status == "metadata_reviewed"}
    return CatalogComparison(
        previous_document=_document(previous), candidate_document=_document(candidate),
        previous_entry_order=tuple(entry.source_id for entry in before_entries),
        candidate_entry_order=tuple(entry.source_id for entry in after_entries),
        source_changes=tuple(changes),
        eligibility_added=tuple(sorted(new_eligible - old_eligible)),
        eligibility_removed=tuple(sorted(old_eligible - new_eligible)),
        eligible_metadata_changed=tuple(sorted(
            key for key in old_eligible & new_eligible
            if _matching_metadata(before[key]) != _matching_metadata(after[key])
        )),
    )


def compare_catalogs(previous: SourceCatalog, candidate: SourceCatalog) -> CatalogComparison:
    """Revalidate complete catalogs and report exact normalized document changes."""
    return _compare_snapshots(_validated_snapshot(previous), _validated_snapshot(candidate))


def acknowledge_catalog_changes(comparison: CatalogComparison) -> CatalogAcknowledgment:
    """Explicitly declare acknowledgment of this exact pair, without consuming it."""
    if not isinstance(comparison, CatalogComparison):
        raise TypeError("comparison must be a CatalogComparison")
    return CatalogAcknowledgment(comparison.previous_document, comparison.candidate_document)


def build_registry_for_revision(
    previous: SourceCatalog,
    candidate: SourceCatalog,
    acknowledgment: CatalogAcknowledgment | None = None,
) -> SourceRegistry:
    """Check revision policy and build from the same independent candidate snapshot.

    The caller chooses the baseline. No adoption, authenticated approval, freshness
    or protection against hostile in-process code is provided. Direct catalog
    registry construction remains available outside this opt-in workflow.
    """
    old, new = _validated_snapshot(previous), _validated_snapshot(candidate)
    comparison = _compare_snapshots(old, new)
    if acknowledgment is not None:
        if not isinstance(acknowledgment, CatalogAcknowledgment):
            raise TypeError("acknowledgment must be a CatalogAcknowledgment")
        if (acknowledgment.previous_document, acknowledgment.candidate_document) != (
            comparison.previous_document, comparison.candidate_document,
        ):
            raise ValueError("acknowledgment does not match the exact catalog transition")
    if comparison.has_changes:
        if old.catalog_id == new.catalog_id:
            raise ValueError("a changed replacement requires a distinct catalog_id")
        if acknowledgment is None:
            raise ValueError("catalog changes require explicit acknowledgment")
    return new.build_registry()

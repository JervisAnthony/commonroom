"""Caller-curated metadata eligibility, never authenticity or claim verification."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from pensieve_api.domain.provenance import NonBlankText
from pensieve_api.domain.source_registry import RegisteredSource, SourceRegistry


class CatalogEntry(BaseModel):
    """An explicit author declaration; structural validity does not imply review."""

    model_config = ConfigDict(extra="forbid", strict=True)

    source: RegisteredSource
    curation_status: Literal["proposed", "metadata_reviewed"]
    curation_note: NonBlankText


class SourceCatalog(BaseModel):
    """Version 1 metadata document, preserving proposed and eligible entry order."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    catalog_id: NonBlankText
    entries: list[CatalogEntry]

    @field_validator("schema_version", mode="before")
    @classmethod
    def require_integer_version(cls, value: object) -> object:
        # Literal[1] alone also accepts True and 1.0 under Pydantic strict mode.
        if type(value) is not int:
            raise ValueError("schema_version must be the integer 1")
        return value

    @field_validator("entries")
    @classmethod
    def reject_duplicate_source_ids(cls, value: list[CatalogEntry]) -> list[CatalogEntry]:
        if len({entry.source.source_id for entry in value}) != len(value):
            raise ValueError("source IDs must be unique after normalization")
        return value

    def build_registry(self) -> SourceRegistry:
        """Revalidate all mutable state, then snapshot explicitly eligible sources.

        Proposed entries must also remain valid. This operation neither changes
        curation status nor evaluates source content or the author's declaration.
        """
        snapshot = SourceCatalog.model_validate(self.model_dump(warnings=False))
        return SourceRegistry([
            entry.source for entry in snapshot.entries
            if entry.curation_status == "metadata_reviewed"
        ])

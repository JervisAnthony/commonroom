"""Versioned local data composition, without loading, adoption or verification."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from pensieve_api.domain.source_catalog import SourceCatalog
from pensieve_api.domain.source_passages import PassageStore, SourcePassage


class PassageBundle(BaseModel):
    """Strict format document; structural validity does not imply store eligibility."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    catalog: SourceCatalog
    passages: list[SourcePassage]

    @field_validator("schema_version", mode="before")
    @classmethod
    def require_integer_version(cls, value: object) -> object:
        # Literal[1] alone accepts True and 1.0 even under strict validation.
        if type(value) is not int:
            raise ValueError("schema_version must be the integer 1")
        return value

    def build_store(self) -> PassageStore:
        """Revalidate everything before building independent public snapshots.

        Uses direct catalog construction, not the opt-in revision acknowledgment
        workflow. Catalog acknowledgments do not bind caller-supplied passage text.
        Existing validation and construction failures propagate without filtering.
        """
        snapshot = PassageBundle.model_validate(self.model_dump(warnings=False))
        registry = snapshot.catalog.build_registry()
        return PassageStore(registry, snapshot.passages)

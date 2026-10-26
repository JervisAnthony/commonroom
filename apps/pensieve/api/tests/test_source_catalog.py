"""Synthetic catalog declarations and exact matching, never claim verification."""

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pensieve_api.domain.provenance import GeneratedRoleplay, SourceReference, SourcedLoreClaim
from pensieve_api.domain.source_catalog import CatalogEntry, SourceCatalog
from pensieve_api.domain.source_registry import RegisteredSource, ResolutionStatus, SourceRegistry


def entry_data(status="metadata_reviewed", source_id="synthetic-moonseed-atlas"):
    return {
        "source": {
            "source_id": source_id,
            "title": "The Moonseed Lantern Atlas",
            "canon_tier": "book",
            "locators": [{"kind": "chapter", "reference": "3"}],
        },
        "curation_status": status,
        "curation_note": "The author declares this invented metadata eligible for matching.",
    }


def catalog_data():
    return {
        "schema_version": 1, "catalog_id": "synthetic-catalog-v1",
        "entries": [entry_data(), entry_data("proposed", "synthetic-proposed")],
    }


def reference(source_id="synthetic-moonseed-atlas", **changes):
    data = entry_data(source_id=source_id)["source"]
    data["locator"] = data.pop("locators")[0]
    return SourceReference.model_validate(data | changes)


def test_python_models_normalization_and_json_round_trips():
    entry = CatalogEntry(
        source=RegisteredSource.model_validate(entry_data()["source"]),
        curation_status="metadata_reviewed", curation_note="  Original note.  ",
    )
    catalog = SourceCatalog(schema_version=1, catalog_id=" catalog-v1 ", entries=[entry])
    assert catalog.catalog_id == "catalog-v1"
    assert entry.curation_note == "Original note."
    payload = catalog.model_dump_json()
    assert SourceCatalog.model_validate_json(payload) == catalog
    assert SourceCatalog.model_validate(catalog.model_dump(mode="json")) == catalog
    assert json.loads(payload) == catalog.model_dump(mode="json")
    assert all(catalog.model_dump_json() == payload for _ in range(5))
    assert CatalogEntry.model_validate_json(entry.model_dump_json()) == entry


@pytest.mark.parametrize("field", ["schema_version", "catalog_id", "entries"])
def test_required_catalog_fields(field):
    data = catalog_data()
    del data[field]
    with pytest.raises(ValidationError):
        SourceCatalog.model_validate(data)


@pytest.mark.parametrize("version", [0, 2, -1, "1", True, False, 1.0, None, [], {}])
def test_exact_version_in_python_and_json(version):
    data = catalog_data() | {"schema_version": version}
    for validate, payload in [(SourceCatalog.model_validate, data),
                              (SourceCatalog.model_validate_json, json.dumps(data))]:
        with pytest.raises(ValidationError):
            validate(payload)


@pytest.mark.parametrize("value", ["", " \t\n", 1, True, None, b"text", [], {}])
@pytest.mark.parametrize("field", ["catalog_id", "curation_note"])
def test_strict_nonblank_text(field, value):
    data = catalog_data()
    if field == "catalog_id":
        data[field] = value
    else:
        data["entries"][0][field] = value
    with pytest.raises(ValidationError):
        SourceCatalog.model_validate(data)


@pytest.mark.parametrize("entries", [None, {}, "entries", (), [None], [1], ["entry"], [[]]])
def test_strict_entry_collection(entries):
    with pytest.raises(ValidationError):
        SourceCatalog.model_validate(catalog_data() | {"entries": entries})


@pytest.mark.parametrize("field", ["source", "curation_status", "curation_note"])
def test_required_entry_fields(field):
    data = catalog_data()
    del data["entries"][0][field]
    with pytest.raises(ValidationError):
        SourceCatalog.model_validate(data)


@pytest.mark.parametrize("status", ["reviewed", "METADATA_REVIEWED", " proposed ", "", 1, True, None, b"proposed"])
def test_exact_status(status):
    with pytest.raises(ValidationError):
        CatalogEntry.model_validate(entry_data() | {"curation_status": status})


@pytest.mark.parametrize("level", ["catalog", "entry", "source", "locator"])
def test_unknown_fields_at_every_level(level):
    data = catalog_data()
    targets = {"catalog": data, "entry": data["entries"][0],
               "source": data["entries"][0]["source"],
               "locator": data["entries"][0]["source"]["locators"][0]}
    targets[level]["verified"] = True
    with pytest.raises(ValidationError):
        SourceCatalog.model_validate(data)


@pytest.mark.parametrize("field", ["source_id", "title", "canon_tier", "locators"])
def test_missing_nested_source_fields(field):
    data = catalog_data()
    del data["entries"][0]["source"][field]
    with pytest.raises(ValidationError):
        SourceCatalog.model_validate(data)


@pytest.mark.parametrize("changes", [
    {"source_id": " "}, {"title": 1}, {"canon_tier": "BOOK"}, {"canon_tier": 1},
    {"locators": []}, {"locators": ()}, {"locators": [{}]},
    {"locators": [{"kind": "page", "reference": "3"}]},
    {"locators": [{"kind": "chapter"}]},
    {"locators": [{"kind": "chapter", "reference": " "}]},
    {"locators": [{"kind": "chapter", "reference": 3}]},
    {"locators": [{"kind": "chapter", "reference": "3"},
                  {"kind": "chapter", "reference": " 3 "}]},
])
def test_invalid_nested_sources_including_proposed(changes):
    data = catalog_data()
    data["entries"][1]["source"].update(changes)
    with pytest.raises(ValidationError):
        SourceCatalog.model_validate(data)


@pytest.mark.parametrize("status", ["proposed", "metadata_reviewed"])
def test_duplicate_normalized_ids_across_all_statuses(status):
    data = catalog_data()
    data["entries"][1] = entry_data(status, " synthetic-moonseed-atlas ")
    with pytest.raises(ValidationError, match="unique"):
        SourceCatalog.model_validate(data)


def test_case_sensitive_ids_and_entry_order():
    data = catalog_data()
    data["entries"].append(entry_data(source_id="SYNTHETIC-MOONSEED-ATLAS"))
    catalog = SourceCatalog.model_validate(data)
    assert [entry.source.source_id for entry in catalog.entries] == [
        "synthetic-moonseed-atlas", "synthetic-proposed", "SYNTHETIC-MOONSEED-ATLAS",
    ]
    assert catalog.build_registry().resolve_reference(reference("SYNTHETIC-MOONSEED-ATLAS")).status is ResolutionStatus.REGISTRY_MATCH


@pytest.mark.parametrize("entries", [[], [entry_data("proposed")]])
def test_empty_and_all_proposed_catalogs(entries):
    catalog = SourceCatalog.model_validate(catalog_data() | {"entries": entries})
    assert isinstance(catalog.build_registry(), SourceRegistry)
    assert catalog.build_registry().resolve_reference(reference()).status is ResolutionStatus.SOURCE_NOT_REGISTERED


@pytest.mark.parametrize(("changes", "status"), [
    ({}, ResolutionStatus.REGISTRY_MATCH),
    ({"source_id": "synthetic-proposed"}, ResolutionStatus.SOURCE_NOT_REGISTERED),
    ({"title": "Other"}, ResolutionStatus.SOURCE_METADATA_MISMATCH),
    ({"canon_tier": "film"}, ResolutionStatus.SOURCE_METADATA_MISMATCH),
    ({"locator": {"kind": "chapter", "reference": "4"}}, ResolutionStatus.LOCATOR_NOT_REGISTERED),
    ({"source_id": "synthetic-moonseed-ATLAS"}, ResolutionStatus.SOURCE_NOT_REGISTERED),
])
def test_mixed_catalog_gating_matching_and_no_promotion(changes, status):
    catalog = SourceCatalog.model_validate(catalog_data())
    before = catalog.model_dump()
    assert catalog.build_registry().resolve_reference(reference(**changes)).status is status
    assert catalog.model_dump() == before


@pytest.mark.parametrize("include_proposed", [False, True])
def test_claim_order_duplicates_and_aggregate(include_proposed):
    registry = SourceCatalog.model_validate(catalog_data()).build_registry()
    refs = [reference(), reference()]
    if include_proposed:
        refs.insert(1, reference("synthetic-proposed"))
    claim = SourcedLoreClaim(kind="sourced_lore", statement="An original invented statement.", sources=refs)
    result = registry.resolve_claim(claim)
    assert result.references == tuple(registry.resolve_reference(ref) for ref in refs)
    assert result.all_references_registered is (not include_proposed)
    assert [item.reference for item in result.references] == refs
    with pytest.raises(TypeError, match="SourcedLoreClaim"):
        registry.resolve_claim(GeneratedRoleplay(kind="generated_roleplay", content="An invented greeting."))


def test_registry_snapshot_survives_metadata_status_and_locator_mutation():
    catalog = SourceCatalog.model_validate(catalog_data())
    registry = catalog.build_registry()
    catalog.entries[0].curation_status = "proposed"
    catalog.entries[1].curation_status = "metadata_reviewed"
    catalog.entries[0].source.title = "Changed title"
    catalog.entries[0].source.locators[0].reference = "4"
    catalog.entries[0].source.locators.append({"kind": "scene", "reference": "5"})
    catalog.entries[0].source.locators.clear()
    assert registry.resolve_reference(reference()).status is ResolutionStatus.REGISTRY_MATCH
    assert registry.resolve_reference(reference("synthetic-proposed")).status is ResolutionStatus.SOURCE_NOT_REGISTERED


def test_new_registry_reflects_explicit_status_change_only():
    catalog = SourceCatalog.model_validate(catalog_data())
    old = catalog.build_registry()
    catalog.entries[0].curation_status = "proposed"
    catalog.entries[1].curation_status = "metadata_reviewed"
    new = catalog.build_registry()
    assert old.resolve_reference(reference()).status is ResolutionStatus.REGISTRY_MATCH
    assert new.resolve_reference(reference()).status is ResolutionStatus.SOURCE_NOT_REGISTERED
    assert new.resolve_reference(reference("synthetic-proposed")).status is ResolutionStatus.REGISTRY_MATCH


@pytest.mark.parametrize("mutation", [
    lambda c: setattr(c, "schema_version", True),
    lambda c: setattr(c, "schema_version", 2),
    lambda c: setattr(c, "catalog_id", " "),
    lambda c: setattr(c, "entries", ()),
    lambda c: c.entries.append(None),
    lambda c: setattr(c.entries[1], "curation_status", "reviewed"),
    lambda c: setattr(c.entries[1], "curation_note", " "),
    lambda c: setattr(c.entries[1].source, "title", " "),
    lambda c: setattr(c.entries[1].source, "canon_tier", "unknown"),
    lambda c: setattr(c.entries[1].source, "source_id", " synthetic-moonseed-atlas "),
    lambda c: setattr(c.entries[1].source.locators[0], "kind", "page"),
    lambda c: c.entries[1].source.locators.clear(),
    lambda c: c.entries[1].source.locators.append(c.entries[1].source.locators[0]),
])
def test_build_revalidates_entire_mutated_catalog(mutation):
    catalog = SourceCatalog.model_validate(catalog_data())
    mutation(catalog)
    with pytest.raises(ValidationError):
        catalog.build_registry()


def test_committed_synthetic_example():
    path = Path(__file__).resolve().parents[1] / "examples" / "synthetic_catalog.v1.json"
    catalog = SourceCatalog.model_validate_json(path.read_text(encoding="utf-8"))
    assert [entry.curation_status for entry in catalog.entries] == ["metadata_reviewed", "proposed"]
    registry = catalog.build_registry()
    for entry, expected in zip(catalog.entries, [ResolutionStatus.REGISTRY_MATCH, ResolutionStatus.SOURCE_NOT_REGISTERED]):
        source = entry.source.model_dump()
        source["locator"] = source.pop("locators")[0]
        assert registry.resolve_reference(SourceReference.model_validate(source)).status is expected


def test_health_and_openapi_unchanged():
    from pensieve_api.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "pensieve-api"}
        schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/api/v1/health"}
    assert set(schema["components"]["schemas"]) == {"HealthResponse"}


def test_fresh_import_and_catalog_build_without_configuration_or_external_io(tmp_path):
    code = textwrap.dedent('''
        import os
        import sys
        import fastapi
        import pydantic

        class FrameworkWarmup(pydantic.BaseModel):
            pass

        def reject_external_io(event, args):
            if event in {"socket.connect", "socket.getaddrinfo", "sqlite3.connect",
                         "os.mkdir", "os.remove", "os.rename", "subprocess.Popen"}:
                raise AssertionError(f"Unexpected external I/O: {event}")
            if event == "open":
                path, mode, flags = args
                if (mode and any(char in mode for char in "wax+")) or flags & (
                    os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
                ):
                    raise AssertionError("Unexpected filesystem write")
                if not str(path).endswith((".py", ".pyc", ".pyd")):
                    raise AssertionError(f"Unexpected data read: {path}")

        sys.addaudithook(reject_external_io)
        from pensieve_api.main import app
        assert "pensieve_api.domain.source_catalog" not in sys.modules
        from pensieve_api.domain.source_catalog import SourceCatalog
        from pensieve_api.domain.provenance import SourceReference
        from pensieve_api.domain.source_registry import ResolutionStatus
        ref = SourceReference(source_id="synthetic", title="Invented Atlas", canon_tier="book",
                              locator={"kind": "chapter", "reference": "1"})
        source = ref.model_dump()
        source["locators"] = [source.pop("locator")]
        catalog = SourceCatalog(schema_version=1, catalog_id="synthetic-v1", entries=[{
            "source": source, "curation_status": "metadata_reviewed",
            "curation_note": "Original author declaration for an invented source.",
        }])
        registry = catalog.build_registry()
        assert registry.resolve_reference(ref).status is ResolutionStatus.REGISTRY_MATCH
    ''')
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code], cwd=tmp_path,
        env={"SystemRoot": os.environ["SystemRoot"]} if "SystemRoot" in os.environ else {},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

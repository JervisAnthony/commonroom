"""Synthetic source metadata only; matching never verifies a statement."""

import os
import subprocess
import sys
import textwrap

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pensieve_api.domain.provenance import (
    CanonTier, GeneratedRoleplay, SourceLocator, SourceReference, SourcedLoreClaim,
)
from pensieve_api.domain.source_registry import (
    RegisteredSource, ResolutionStatus, SourceRegistry,
)


def source_data():
    return {
        "source_id": "synthetic-atlas",
        "title": "The Imaginary Lantern Atlas",
        "canon_tier": "book",
        "locators": [{"kind": "chapter", "reference": "3"}],
    }


def reference(**changes):
    data = source_data()
    data["locator"] = data.pop("locators")[0]
    return SourceReference.model_validate(data | changes)


def registry():
    return SourceRegistry([RegisteredSource.model_validate(source_data())])


@pytest.mark.parametrize("tier", list(CanonTier))
@pytest.mark.parametrize("kind", ["chapter", "scene", "section", "other"])
def test_all_tiers_and_locator_kinds(tier, kind):
    data = source_data() | {
        "canon_tier": tier.value,
        "locators": [{"kind": kind, "reference": "3"}],
    }
    source = RegisteredSource.model_validate(data)
    assert source.canon_tier is tier
    assert RegisteredSource.model_validate_json(source.model_dump_json()) == source
    result = SourceRegistry([source]).resolve_reference(reference(
        canon_tier=tier, locator=SourceLocator(kind=kind, reference="3"),
    ))
    assert result.status is ResolutionStatus.REGISTRY_MATCH


@pytest.mark.parametrize(("changes", "status"), [
    ({}, ResolutionStatus.REGISTRY_MATCH),
    ({"source_id": "unknown", "title": "Wrong", "canon_tier": "film",
      "locator": {"kind": "other", "reference": "missing"}}, ResolutionStatus.SOURCE_NOT_REGISTERED),
    ({"title": "Wrong"}, ResolutionStatus.SOURCE_METADATA_MISMATCH),
    ({"canon_tier": "film"}, ResolutionStatus.SOURCE_METADATA_MISMATCH),
    ({"title": "Wrong", "canon_tier": "film"}, ResolutionStatus.SOURCE_METADATA_MISMATCH),
    ({"title": "Wrong", "locator": {"kind": "other", "reference": "missing"}},
     ResolutionStatus.SOURCE_METADATA_MISMATCH),
    ({"locator": {"kind": "chapter", "reference": "4"}}, ResolutionStatus.LOCATOR_NOT_REGISTERED),
    ({"locator": {"kind": "scene", "reference": "3"}}, ResolutionStatus.LOCATOR_NOT_REGISTERED),
    ({"locator": {"kind": "chapter", "reference": "03"}}, ResolutionStatus.LOCATOR_NOT_REGISTERED),
    ({"source_id": "SYNTHETIC-ATLAS"}, ResolutionStatus.SOURCE_NOT_REGISTERED),
    ({"title": "the imaginary lantern atlas"}, ResolutionStatus.SOURCE_METADATA_MISMATCH),
])
def test_exact_matching_and_precedence(changes, status):
    store = registry()
    ref = reference(**changes)
    first = store.resolve_reference(ref)
    assert first.status is status
    assert all(store.resolve_reference(ref) == first for _ in range(5))


def test_normalization_and_reference_case_sensitivity():
    data = source_data() | {
        "source_id": " synthetic-atlas ", "title": " The Imaginary Lantern Atlas ",
        "locators": [{"kind": "other", "reference": " Section A "}],
    }
    store = SourceRegistry([RegisteredSource.model_validate(data)])
    assert store.resolve_reference(reference(locator={"kind": "other", "reference": " Section A "})).status is ResolutionStatus.REGISTRY_MATCH
    assert store.resolve_reference(reference(locator={"kind": "other", "reference": "section a"})).status is ResolutionStatus.LOCATOR_NOT_REGISTERED


def test_empty_registry_and_independent_instances():
    assert SourceRegistry([]).resolve_reference(reference()).status is ResolutionStatus.SOURCE_NOT_REGISTERED
    assert registry().resolve_reference(reference()).status is ResolutionStatus.REGISTRY_MATCH
    assert SourceRegistry(()).resolve_reference(reference()).status is ResolutionStatus.SOURCE_NOT_REGISTERED


def test_duplicate_ids_after_normalization():
    one = RegisteredSource.model_validate(source_data())
    two = RegisteredSource.model_validate(source_data() | {"source_id": " synthetic-atlas ", "title": "Other"})
    with pytest.raises(ValueError, match="duplicate source_id"):
        SourceRegistry([one, two])


def test_duplicate_locators_after_normalization():
    with pytest.raises(ValidationError, match="unique"):
        RegisteredSource.model_validate(source_data() | {"locators": [
            {"kind": "chapter", "reference": "3"},
            {"kind": "chapter", "reference": " 3 "},
        ]})


def test_distinct_locator_pairs_and_multiple_sources():
    one = RegisteredSource.model_validate(source_data() | {"locators": [
        {"kind": "chapter", "reference": "3"},
        {"kind": "scene", "reference": "3"},
        {"kind": "chapter", "reference": "4"},
    ]})
    two = RegisteredSource.model_validate(source_data() | {"source_id": "synthetic-second"})
    store = SourceRegistry([one, two])
    for locator in one.locators:
        assert store.resolve_reference(reference(locator=locator)).status is ResolutionStatus.REGISTRY_MATCH
    assert store.resolve_reference(reference(source_id=two.source_id)).status is ResolutionStatus.REGISTRY_MATCH


@pytest.mark.parametrize("locators", [
    [], (), None, {}, "chapter", [None], ["chapter"], [1],
    [{}], [{"kind": "page", "reference": "3"}],
    [{"kind": "chapter", "reference": " "}],
    [{"kind": "chapter", "reference": 3}],
    [{"kind": "chapter", "reference": "3", "url": "unexpected"}],
])
def test_invalid_locator_collections(locators):
    with pytest.raises(ValidationError):
        RegisteredSource.model_validate(source_data() | {"locators": locators})


@pytest.mark.parametrize("field", ["source_id", "title", "canon_tier", "locators"])
def test_required_fields(field):
    data = source_data()
    del data[field]
    with pytest.raises(ValidationError):
        RegisteredSource.model_validate(data)


@pytest.mark.parametrize("field", ["source_id", "title"])
@pytest.mark.parametrize("value", ["", " \t\n", 1, True, None, b"text", [], {}])
def test_strict_nonblank_text(field, value):
    with pytest.raises(ValidationError):
        RegisteredSource.model_validate(source_data() | {field: value})


@pytest.mark.parametrize("tier", ["BOOK", " book ", "unknown", 1, True, None, b"book"])
def test_invalid_tiers(tier):
    with pytest.raises(ValidationError):
        RegisteredSource.model_validate(source_data() | {"canon_tier": tier})


def test_unexpected_fields():
    with pytest.raises(ValidationError):
        RegisteredSource.model_validate(source_data() | {"verified": True})


@pytest.mark.parametrize("refs", [
    [reference()],
    [reference(), reference()],
    [reference(), reference(title="Other"), reference(), reference(source_id="missing")],
    [reference(locator={"kind": "scene", "reference": "3"})],
])
def test_claim_order_duplicates_aggregate_and_no_mutation(refs):
    claim = SourcedLoreClaim(kind="sourced_lore", statement="An original invented statement.", sources=refs)
    before = claim.model_dump()
    store = registry()
    result = store.resolve_claim(claim)
    expected = tuple(store.resolve_reference(ref) for ref in refs)
    assert result.references == expected
    assert [outcome.reference for outcome in result.references] == refs
    assert result.all_references_registered == all(
        item.status is ResolutionStatus.REGISTRY_MATCH for item in expected
    )
    assert claim.model_dump() == before
    assert store.resolve_claim(claim) == result
    if len(refs) > 1 and refs[0] == refs[1]:
        assert result.references[0].reference is not result.references[1].reference


@pytest.mark.parametrize("value", [
    GeneratedRoleplay(kind="generated_roleplay", content="An invented lantern greets you."),
    {"kind": "sourced_lore", "statement": "Invented", "sources": []}, None,
])
def test_reject_non_claims(value):
    with pytest.raises(TypeError, match="SourcedLoreClaim"):
        registry().resolve_claim(value)


def test_caller_and_returned_data_cannot_mutate_registry():
    data = source_data()
    source = RegisteredSource.model_validate(data)
    sources = [source]
    store = SourceRegistry(sources)
    source.title = "Changed"
    source.source_id = "Changed"
    source.canon_tier = CanonTier.FILM
    source.locators[0].reference = "Changed"
    source.locators.clear()
    sources.clear()
    data["locators"].clear()
    ref = reference()
    result = store.resolve_reference(ref)
    assert result.status is ResolutionStatus.REGISTRY_MATCH
    ref.title = "Caller change"
    assert result.reference.title == source_data()["title"]
    result.reference.title = "Returned change"
    result.reference.locator.reference = "Returned change"
    claim = SourcedLoreClaim(kind="sourced_lore", statement="Invented.", sources=[reference(), reference()])
    outcomes = store.resolve_claim(claim)
    outcomes.references[0].reference.locator.reference = "Changed"
    assert outcomes.references[1].reference == reference()
    assert claim.sources == [reference(), reference()]
    assert store.resolve_reference(reference()).status is ResolutionStatus.REGISTRY_MATCH
    assert store.resolve_claim(claim).all_references_registered


def test_revalidate_mutated_models_and_reject_wrong_input_types():
    source = RegisteredSource.model_validate(source_data())
    source.locators.clear()
    with pytest.raises(ValidationError):
        SourceRegistry([source])
    with pytest.raises(TypeError):
        SourceRegistry([source_data()])
    with pytest.raises(TypeError):
        registry().resolve_reference(source_data())
    ref = reference()
    ref.title = " "
    with pytest.raises(ValidationError):
        registry().resolve_reference(ref)
    claim = SourcedLoreClaim(kind="sourced_lore", statement="Invented.", sources=[reference()])
    claim.sources.clear()
    with pytest.raises(ValidationError):
        registry().resolve_claim(claim)


def test_health_and_openapi_unchanged():
    from pensieve_api.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "pensieve-api"}
        schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/api/v1/health"}
    assert set(schema["components"]["schemas"]) == {"HealthResponse"}


def test_fresh_import_and_resolution_without_external_io(tmp_path):
    code = textwrap.dedent('''
        import os
        import sys
        import pydantic

        # Initialize framework plugin discovery before guarding domain imports.
        # Pydantic reads installed distributions' entry-point metadata once.
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
                # Python module reads are necessary to import an uncached module.
                if not str(path).endswith((".py", ".pyc", ".pyd")):
                    raise AssertionError(f"Unexpected data read: {path}")

        sys.addaudithook(reject_external_io)
        from pensieve_api.domain.source_registry import RegisteredSource, SourceRegistry, ResolutionStatus
        from pensieve_api.domain.provenance import SourceReference, SourcedLoreClaim
        ref = SourceReference(source_id="synthetic", title="Invented Atlas", canon_tier="book",
                              locator={"kind": "chapter", "reference": "1"})
        data = ref.model_dump()
        data["locators"] = [data.pop("locator")]
        store = SourceRegistry([RegisteredSource.model_validate(data)])
        assert store.resolve_reference(ref).status is ResolutionStatus.REGISTRY_MATCH
        claim = SourcedLoreClaim(kind="sourced_lore", statement="Invented.", sources=[ref])
        assert store.resolve_claim(claim).all_references_registered
    ''')
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code], cwd=tmp_path,
        env={"SystemRoot": os.environ["SystemRoot"]} if "SystemRoot" in os.environ else {},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

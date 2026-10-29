"""Original synthetic text; availability never establishes authenticity or support."""

from dataclasses import FrozenInstanceError
import itertools
import json
import os
import subprocess
import sys
import textwrap

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pensieve_api.domain.catalog_governance import (
    acknowledge_catalog_changes, build_registry_for_revision, compare_catalogs,
)
from pensieve_api.domain.provenance import GeneratedRoleplay, SourceReference, SourcedLoreClaim
from pensieve_api.domain.source_catalog import SourceCatalog
from pensieve_api.domain.source_passages import PassageLookup, PassageStore, SourcePassage
from pensieve_api.domain.source_registry import RegisteredSource, ResolutionStatus, SourceRegistry


def reference(**changes):
    return SourceReference.model_validate({
        "source_id": "synthetic-atlas", "title": "The Paper Lantern Atlas", "canon_tier": "book",
        "locator": {"kind": "chapter", "reference": "A"},
    } | changes)


def passage(passage_id="one", ref=None):
    return SourcePassage(kind="source_passage", passage_id=passage_id,
                         reference=ref if ref is not None else reference(),
                         text="A paper lantern floated above an invented garden.")


def catalog():
    return SourceCatalog(schema_version=1, catalog_id="synthetic-v1", entries=[{
        "source": {"source_id": source_id, "title": "The Paper Lantern Atlas", "canon_tier": "book",
                   "locators": [{"kind": "chapter", "reference": "A"},
                                {"kind": "scene", "reference": "A"},
                                {"kind": "chapter", "reference": "B"}]},
        "curation_status": status, "curation_note": "Original synthetic metadata declaration.",
    } for source_id, status in [("synthetic-atlas", "metadata_reviewed"),
                                 ("synthetic-second", "metadata_reviewed"),
                                 ("synthetic-proposal", "proposed")]])


def test_python_json_and_normalization():
    record = passage(" one ")
    record.text = " \nCafé  lantern\n\t雪 glows. \t"
    record.reference.title = " The Paper Lantern Atlas "
    normalized = SourcePassage.model_validate(record.model_dump())
    assert normalized.passage_id == "one"
    assert normalized.text == "Café  lantern\n\t雪 glows."
    assert normalized.reference == reference()
    assert SourcePassage.model_validate_json(normalized.model_dump_json()) == normalized
    assert SourcePassage.model_validate(normalized.model_dump(mode="json")) == normalized
    assert json.loads(normalized.model_dump_json()) == normalized.model_dump(mode="json")


@pytest.mark.parametrize("field", ["kind", "passage_id", "reference", "text"])
def test_required_fields(field):
    data = passage().model_dump()
    del data[field]
    with pytest.raises(ValidationError):
        SourcePassage.model_validate(data)
    with pytest.raises(ValidationError):
        SourcePassage.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("field", ["passage_id", "text"])
@pytest.mark.parametrize("value", ["", " \t\n", 1, True, None, b"text", [], {}])
def test_strict_nonblank_text(field, value):
    with pytest.raises(ValidationError):
        SourcePassage.model_validate(passage().model_dump() | {field: value})


@pytest.mark.parametrize("changes", [
    {"kind": "generated_roleplay"}, {"kind": "sourced_lore"}, {"kind": None},
    {"verified": True}, {"reference": None}, {"reference": {}},
    {"reference": reference().model_dump() | {"title": 1}},
    {"reference": reference().model_dump() | {"locator": {"kind": "page", "reference": "A"}}},
    {"reference": reference().model_dump() | {"authentic": True}},
])
def test_malformed_records(changes):
    with pytest.raises(ValidationError):
        SourcePassage.model_validate(passage().model_dump() | changes)


def unrelated_records():
    return [GeneratedRoleplay(kind="generated_roleplay", content="An invented greeting."),
            SourcedLoreClaim(kind="sourced_lore", statement="An original observation.", sources=[reference()])]


@pytest.mark.parametrize("record", unrelated_records())
def test_unrelated_content_is_never_source_text(record):
    with pytest.raises(ValidationError):
        SourcePassage.model_validate(record)
    with pytest.raises(ValidationError):
        SourcePassage.model_validate(record.model_dump())
    with pytest.raises(TypeError, match="SourcePassage"):
        PassageStore(catalog().build_registry(), [record])


@pytest.mark.parametrize("collection", [[], ()])
def test_empty_store(collection):
    store = PassageStore(catalog().build_registry(), collection)
    assert store.lookup_reference(reference()) == PassageLookup(ResolutionStatus.REGISTRY_MATCH, ())
    assert PassageStore(SourceRegistry([]), collection).lookup_reference(reference()).status is ResolutionStatus.SOURCE_NOT_REGISTERED


@pytest.mark.parametrize("second_id", ["one", " one "])
def test_duplicate_normalized_ids(second_id):
    second = passage(second_id)
    second.passage_id = second_id  # Also exercise revalidation of mutated whitespace.
    with pytest.raises(ValueError, match="duplicate passage_id: one"):
        PassageStore(catalog().build_registry(), [passage(), second])


def test_multiple_passages_order_case_distinct_ids_and_duplicate_content():
    records = [passage("z"), passage("Z"), passage("a")]
    store = PassageStore(catalog().build_registry(), tuple(records))
    assert store.lookup_reference(reference()).passages == tuple(records)


@pytest.mark.parametrize("value", [None, {}, "passages", b"passages", bytearray(), set(),
                                       iter([]), itertools.repeat(passage()), [None], [reference()],
                                       [passage().model_dump()]])
def test_wrong_collections_and_records(value):
    with pytest.raises(TypeError):
        PassageStore(catalog().build_registry(), value)


@pytest.mark.parametrize("value", [None, {}, [], catalog(), RegisteredSource(
    source_id="synthetic", title="Invented", canon_tier="book",
    locators=[{"kind": "chapter", "reference": "A"}],
)])
def test_wrong_registry(value):
    with pytest.raises(TypeError, match="SourceRegistry"):
        PassageStore(value, [])


RESOLUTION_CASES = [
    ({}, ResolutionStatus.REGISTRY_MATCH),
    ({"source_id": "missing", "title": "Wrong", "locator": {"kind": "other", "reference": "X"}},
     ResolutionStatus.SOURCE_NOT_REGISTERED),
    ({"source_id": "synthetic-proposal"}, ResolutionStatus.SOURCE_NOT_REGISTERED),
    ({"source_id": "SYNTHETIC-ATLAS"}, ResolutionStatus.SOURCE_NOT_REGISTERED),
    ({"title": "the paper lantern atlas"}, ResolutionStatus.SOURCE_METADATA_MISMATCH),
    ({"canon_tier": "film"}, ResolutionStatus.SOURCE_METADATA_MISMATCH),
    ({"title": "Wrong", "locator": {"kind": "other", "reference": "X"}},
     ResolutionStatus.SOURCE_METADATA_MISMATCH),
    ({"locator": {"kind": "other", "reference": "A"}}, ResolutionStatus.LOCATOR_NOT_REGISTERED),
    ({"locator": {"kind": "chapter", "reference": "a"}}, ResolutionStatus.LOCATOR_NOT_REGISTERED),
]


@pytest.mark.parametrize(("changes", "status"), RESOLUTION_CASES)
def test_lookup_status_precedence_and_construction_eligibility(changes, status):
    registry = catalog().build_registry()
    ref = reference(**changes)
    store = PassageStore(registry, [passage()])
    result = store.lookup_reference(ref)
    assert result.status is status
    if status is ResolutionStatus.REGISTRY_MATCH:
        assert result.passages == (passage(),)
    else:
        assert result.passages == ()
        with pytest.raises(ValueError, match=f"passage one: {status.value}"):
            PassageStore(registry, [passage(ref=ref)])


def test_complete_reference_isolation_and_trim_equivalence():
    refs = [reference(), reference(source_id="synthetic-second"),
            reference(locator={"kind": "scene", "reference": "A"})]
    records = [passage(str(i), ref) for i, ref in enumerate(refs)]
    store = PassageStore(catalog().build_registry(), records)
    for ref, record in zip(refs, records):
        assert store.lookup_reference(ref).passages == (record,)
    trimmed = reference()
    trimmed.source_id = " synthetic-atlas "
    trimmed.title = " The Paper Lantern Atlas "
    trimmed.locator.reference = " A "
    before = trimmed.model_dump()
    assert store.lookup_reference(trimmed).passages == (records[0],)
    assert trimmed.model_dump() == before
    assert store.lookup_reference(reference(locator={"kind": "chapter", "reference": "B"})).passages == ()


@pytest.mark.parametrize("value", [None, {}, "citation", passage(), *unrelated_records()])
def test_wrong_lookup_input(value):
    with pytest.raises(TypeError, match="SourceReference"):
        PassageStore(catalog().build_registry(), []).lookup_reference(value)


@pytest.mark.parametrize("mutation", [
    lambda p: setattr(p, "kind", "generated_roleplay"),
    lambda p: setattr(p, "passage_id", " "), lambda p: setattr(p, "text", 7),
    lambda p: setattr(p.reference, "title", " "),
    lambda p: setattr(p.reference, "canon_tier", "BOOK"),
    lambda p: setattr(p.reference.locator, "reference", 7),
    lambda p: setattr(p.reference.locator, "kind", "page"),
])
def test_mutated_records_are_revalidated(mutation):
    record = passage()
    mutation(record)
    with pytest.raises(ValidationError):
        PassageStore(catalog().build_registry(), [record])
    if record.reference != reference():
        with pytest.raises(ValidationError):
            PassageStore(catalog().build_registry(), []).lookup_reference(record.reference)


def test_input_and_output_isolation_and_frozen_outer_result():
    registry = catalog().build_registry()
    shared = reference()
    records = [passage("one", shared), passage("two", shared)]
    before = [p.model_dump() for p in records]
    store = PassageStore(registry, records)
    ref = reference()
    first = store.lookup_reference(ref)
    second = store.lookup_reference(ref)
    assert [p.model_dump() for p in records] == before
    assert ref == reference()
    records[0].passage_id = "changed"
    records[0].text = "Changed text."
    shared.title = "Changed title"
    shared.locator.reference = "Changed locator"
    records.clear()
    assert first == second == store.lookup_reference(reference())
    with pytest.raises(FrozenInstanceError):
        first.status = ResolutionStatus.SOURCE_NOT_REGISTERED
    first.passages[0].passage_id = "result edit"
    first.passages[0].text = "Edited result."
    first.passages[0].reference.title = "Result title"
    first.passages[0].reference.locator.reference = "Result locator"
    assert first.passages[1] == passage("two")
    assert second == store.lookup_reference(reference())
    assert registry.resolve_reference(reference()).status is ResolutionStatus.REGISTRY_MATCH


@pytest.mark.parametrize(("edit", "status"), [
    ("demote", ResolutionStatus.SOURCE_NOT_REGISTERED),
    ("remove", ResolutionStatus.SOURCE_NOT_REGISTERED),
    ("title", ResolutionStatus.SOURCE_METADATA_MISMATCH),
    ("tier", ResolutionStatus.SOURCE_METADATA_MISMATCH),
    ("locator", ResolutionStatus.LOCATOR_NOT_REGISTERED),
])
def test_revision_workflow_rebuild_and_existing_snapshot(edit, status):
    previous, candidate = catalog(), catalog()
    candidate.catalog_id = "synthetic-v2"
    ack = acknowledge_catalog_changes(compare_catalogs(previous, candidate))
    registry = build_registry_for_revision(previous, candidate, ack)
    record = passage()
    store = PassageStore(registry, [record])
    candidate.catalog_id = "synthetic-v3"
    entry = candidate.entries[0]
    if edit == "demote":
        entry.curation_status = "proposed"
    elif edit == "remove":
        candidate.entries.pop(0)
    elif edit == "title":
        entry.source.title = "The Folded Moon Atlas"
    elif edit == "tier":
        entry.source.canon_tier = "film"
    else:
        entry.source.locators.pop(0)
    # A proposal edit is never an automatic promotion or revision adoption.
    assert candidate.entries[-1].curation_status == "proposed"
    assert store.lookup_reference(reference()).passages == (record,)
    assert store.lookup_reference(reference(source_id="synthetic-proposal")).status is ResolutionStatus.SOURCE_NOT_REGISTERED
    with pytest.raises(ValueError, match="explicit acknowledgment"):
        build_registry_for_revision(previous, candidate)
    replacement = build_registry_for_revision(
        previous, candidate, acknowledge_catalog_changes(compare_catalogs(previous, candidate)),
    )
    assert replacement.resolve_reference(reference()).status is status
    with pytest.raises(ValueError, match=status.value):
        PassageStore(replacement, [record])
    assert store.lookup_reference(reference()).passages == (record,)


def test_health_and_openapi_unchanged():
    from pensieve_api.main import app

    with TestClient(app) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok", "service": "pensieve-api"}
        schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/api/v1/health"}
    assert set(schema["components"]["schemas"]) == {"HealthResponse"}


def test_fresh_process_without_configuration_or_external_io(tmp_path):
    # Audit hooks guard regressions; they are not an OS sandbox.
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
                if not str(path).endswith((".py", ".pyc", ".pyd", ".so")):
                    raise AssertionError(f"Unexpected data read: {path}")

        sys.addaudithook(reject_external_io)
        from pensieve_api.main import app
        assert "pensieve_api.domain.source_passages" not in sys.modules
        from pensieve_api.domain.source_passages import SourcePassage, PassageStore
        from pensieve_api.domain.source_registry import SourceRegistry, RegisteredSource, ResolutionStatus
        from pensieve_api.domain.provenance import SourceReference
        ref = SourceReference(source_id="synthetic", title="The Paper Atlas", canon_tier="book",
                              locator={"kind": "chapter", "reference": "A"})
        registry = SourceRegistry([RegisteredSource(
            source_id=ref.source_id, title=ref.title, canon_tier=ref.canon_tier, locators=[ref.locator],
        )])
        record = SourcePassage(kind="source_passage", passage_id="one", reference=ref,
                               text="An invented paper lantern glowed.")
        result = PassageStore(registry, [record]).lookup_reference(ref)
        assert result.status is ResolutionStatus.REGISTRY_MATCH
        assert result.passages == (record,)
    ''')
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code], cwd=tmp_path,
        env={"SystemRoot": os.environ["SystemRoot"]} if "SystemRoot" in os.environ else {},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

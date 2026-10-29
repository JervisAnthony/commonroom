"""Synthetic citations and original prose; lookup never evaluates a statement."""

from dataclasses import FrozenInstanceError
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
from pensieve_api.domain.claim_passages import (
    ClaimPassageLookup, ReferencePassages, lookup_claim_passages,
)
from pensieve_api.domain.provenance import SourceReference, SourcedLoreClaim, GeneratedRoleplay
from pensieve_api.domain.source_catalog import SourceCatalog
from pensieve_api.domain.source_passages import PassageStore, SourcePassage
from pensieve_api.domain.source_registry import ResolutionStatus, SourceRegistry


def reference(**changes):
    return SourceReference.model_validate({
        "source_id": "synthetic-atlas", "title": "The Folded Lantern Atlas", "canon_tier": "book",
        "locator": {"kind": "chapter", "reference": "A"},
    } | changes)


def claim(*refs):
    return SourcedLoreClaim(kind="sourced_lore", statement="A paper lantern crossed the invented orchard.",
                            sources=list(refs) if refs else [reference()])


def passage(passage_id="one", ref=None):
    return SourcePassage(kind="source_passage", passage_id=passage_id,
                         reference=ref if ref is not None else reference(),
                         text="A folded paper lantern drifted above the imaginary orchard.")


def catalog():
    return SourceCatalog(schema_version=1, catalog_id="synthetic-v1", entries=[{
        "source": {
            "source_id": source_id, "title": "The Folded Lantern Atlas", "canon_tier": "book",
            "locators": [{"kind": "chapter", "reference": "A"},
                         {"kind": "scene", "reference": "A"},
                         {"kind": "chapter", "reference": "B"}],
        },
        "curation_status": status, "curation_note": "Original fictional eligibility declaration.",
    } for source_id, status in [("synthetic-atlas", "metadata_reviewed"),
                                ("synthetic-second", "metadata_reviewed"),
                                ("synthetic-proposal", "proposed")]])


def store():
    return PassageStore(catalog().build_registry(), [passage("z"), passage("a")])


@pytest.mark.parametrize("records", [[passage()], [passage("z"), passage("a")]])
def test_single_citation_and_normalized_statement(records):
    supplied = claim()
    supplied.statement = " \nAn unrelated  café\nobservation. \t"
    supplied.sources[0].source_id = " synthetic-atlas "
    supplied.sources[0].title = " The Folded Lantern Atlas "
    supplied.sources[0].locator.reference = " A "
    before = supplied.model_dump()
    result = lookup_claim_passages(supplied, PassageStore(catalog().build_registry(), records))
    assert result.statement == "An unrelated  café\nobservation."
    assert result.references == (ReferencePassages(reference(), ResolutionStatus.REGISTRY_MATCH, tuple(records)),)
    assert result.all_references_registered and result.all_references_have_passages
    assert supplied.model_dump() == before


@pytest.mark.parametrize("value", [None, {}, "claim", object(), reference(), passage(),
    GeneratedRoleplay(kind="generated_roleplay", content="An invented greeting."), claim().model_dump()])
def test_wrong_claim_types(value):
    with pytest.raises(TypeError, match="claim must be a SourcedLoreClaim"):
        lookup_claim_passages(value, store())


@pytest.mark.parametrize("value", [None, {}, "store", object(), SourceRegistry([]), catalog(), passage()])
def test_wrong_store_types(value):
    with pytest.raises(TypeError, match="store must be a PassageStore"):
        lookup_claim_passages(claim(), value)


@pytest.mark.parametrize("mutate", [
    lambda c: setattr(c, "kind", "generated_roleplay"),
    lambda c: setattr(c, "statement", " \t"), lambda c: setattr(c, "statement", 7),
    lambda c: c.sources.clear(), lambda c: setattr(c, "sources", "references"),
    lambda c: c.sources.append(None),
    lambda c: setattr(c.sources[1], "source_id", " "),
    lambda c: setattr(c.sources[1], "title", 7),
    lambda c: setattr(c.sources[1], "canon_tier", "BOOK"),
    lambda c: setattr(c.sources[1], "locator", {}),
    lambda c: setattr(c.sources[1].locator, "kind", "page"),
    lambda c: setattr(c.sources[1].locator, "reference", " "),
    lambda c: c.sources.append(reference().model_dump() | {"extra": True}),
])
def test_entire_mutable_claim_validated_before_any_lookup(mutate, monkeypatch):
    supplied = claim(reference(), reference())
    mutate(supplied)
    passages = store()
    calls = []
    direct = passages.lookup_reference

    def observe(ref):
        calls.append(ref)
        return direct(ref)

    monkeypatch.setattr(passages, "lookup_reference", observe)
    with pytest.raises(ValidationError):
        lookup_claim_passages(supplied, passages)
    assert calls == []


def test_public_lookup_composition_status_precedence_order_and_duplicates(monkeypatch):
    refs = [
        reference(source_id="missing", title="Wrong", canon_tier="film",
                  locator={"kind": "other", "reference": "missing"}),
        reference(),
        reference(title="Wrong", locator={"kind": "other", "reference": "missing"}),
        reference(locator={"kind": "other", "reference": "missing"}),
        reference(), reference(locator={"kind": "chapter", "reference": "B"}),
    ]
    passages = store()
    direct = passages.lookup_reference
    expected = [direct(ref) for ref in refs]
    calls = []

    def observe(ref):
        calls.append(ref.model_copy(deep=True))
        return direct(ref)

    monkeypatch.setattr(passages, "lookup_reference", observe)
    result = lookup_claim_passages(claim(*refs), passages)
    assert calls == refs
    assert [entry.reference for entry in result.references] == refs
    assert [entry.status for entry in result.references] == [
        ResolutionStatus.SOURCE_NOT_REGISTERED, ResolutionStatus.REGISTRY_MATCH,
        ResolutionStatus.SOURCE_METADATA_MISMATCH, ResolutionStatus.LOCATOR_NOT_REGISTERED,
        ResolutionStatus.REGISTRY_MATCH, ResolutionStatus.REGISTRY_MATCH,
    ]
    assert [(entry.status, entry.passages) for entry in result.references] == [
        (entry.status, entry.passages) for entry in expected
    ]
    assert [p.passage_id for p in result.references[1].passages] == ["z", "a"]
    assert result.references[1] == result.references[4]
    assert result.references[-1].passages == ()
    assert not result.all_references_registered and not result.all_references_have_passages


@pytest.mark.parametrize(("refs", "registered", "available"), [
    ([reference(), reference()], True, True),
    ([reference(), reference(locator={"kind": "chapter", "reference": "B"})], True, False),
    ([reference(), reference(source_id="missing")], False, False),
    ([reference(source_id="missing"), reference(title="Wrong")], False, False),
])
def test_aggregate_properties_and_statement_is_not_evaluated(refs, registered, available):
    passages = store()
    supplied = claim(*refs)
    result = lookup_claim_passages(supplied, passages)
    assert result.all_references_registered is registered
    assert result.all_references_have_passages is available
    supplied.statement = "An unrelated invented submarine counts purple clouds."
    unrelated = lookup_claim_passages(supplied, passages)
    assert unrelated.statement == supplied.statement
    assert unrelated.references == result.references
    assert unrelated.all_references_registered is registered
    assert unrelated.all_references_have_passages is available


def test_empty_result_and_aggregates_require_matching_status():
    empty = ClaimPassageLookup(statement="An original synthetic statement.", references=())
    assert not empty.all_references_registered and not empty.all_references_have_passages
    inconsistent = ClaimPassageLookup("Synthetic", (
        ReferencePassages(reference(), ResolutionStatus.SOURCE_NOT_REGISTERED, (passage(),)),
    ))
    assert not inconsistent.all_references_registered and not inconsistent.all_references_have_passages


def test_empty_passage_store_retains_registered_and_unregistered_outcomes():
    result = lookup_claim_passages(claim(reference(), reference(source_id="missing")),
                                   PassageStore(catalog().build_registry(), []))
    assert [entry.status for entry in result.references] == [
        ResolutionStatus.REGISTRY_MATCH, ResolutionStatus.SOURCE_NOT_REGISTERED,
    ]
    assert all(entry.passages == () for entry in result.references)
    assert not result.all_references_registered and not result.all_references_have_passages


def test_source_tier_locator_and_case_isolation():
    refs = [reference(), reference(source_id="synthetic-second"),
            reference(locator={"kind": "scene", "reference": "A"})]
    records = [passage(str(index), ref) for index, ref in enumerate(refs)]
    passages = PassageStore(catalog().build_registry(), records)
    result = lookup_claim_passages(claim(*refs, reference(canon_tier="film"),
        reference(locator={"kind": "chapter", "reference": "a"}),
        reference(source_id="SYNTHETIC-ATLAS")), passages)
    assert [entry.passages for entry in result.references] == [(p,) for p in records] + [(), (), ()]
    assert [entry.status for entry in result.references[3:]] == [
        ResolutionStatus.SOURCE_METADATA_MISMATCH, ResolutionStatus.LOCATOR_NOT_REGISTERED,
        ResolutionStatus.SOURCE_NOT_REGISTERED,
    ]


def test_input_and_result_snapshots_with_duplicate_citations():
    registry = catalog().build_registry()
    passages = PassageStore(registry, [passage("z"), passage("a")])
    shared = reference()
    supplied = claim(shared, shared)
    before = supplied.model_dump()
    first = lookup_claim_passages(supplied, passages)
    second = lookup_claim_passages(supplied, passages)
    assert supplied.model_dump() == before
    with pytest.raises(FrozenInstanceError):
        first.statement = "Reassigned"
    with pytest.raises(FrozenInstanceError):
        first.references[0].status = ResolutionStatus.SOURCE_NOT_REGISTERED
    with pytest.raises(FrozenInstanceError):
        first.all_references_registered = False
    with pytest.raises(FrozenInstanceError):
        first.all_references_have_passages = False

    entry = first.references[0]
    entry.reference.title = "Edited submitted snapshot"
    entry.reference.locator.reference = "Edited submitted locator"
    assert entry.passages[0].reference == reference()
    entry.passages[0].passage_id = "edited"
    entry.passages[0].text = "Edited original prose."
    entry.passages[0].reference.source_id = "edited"
    entry.passages[0].reference.locator.reference = "Edited passage locator"
    assert entry.reference.title == "Edited submitted snapshot"
    assert entry.reference.locator.reference == "Edited submitted locator"
    assert entry.passages[1] == passage("a")
    assert first.references[1] == second.references[1]
    assert supplied.model_dump() == before
    assert lookup_claim_passages(supplied, passages) == second
    assert passages.lookup_reference(reference()).passages == (passage("z"), passage("a"))
    assert registry.resolve_reference(reference()).status is ResolutionStatus.REGISTRY_MATCH

    supplied.statement = "Later caller statement"
    shared.title = "Later caller title"
    shared.locator.reference = "Later caller locator"
    supplied.sources.clear()
    assert second.statement == before["statement"]
    assert second.references[0] == second.references[1]
    assert second == lookup_claim_passages(claim(reference(), reference()), passages)


@pytest.mark.parametrize("ref", [reference(title="Wrong"),
    reference(locator={"kind": "chapter", "reference": "B"})])
def test_failed_and_text_empty_citation_snapshots_are_independent(ref):
    supplied = claim(ref, ref)
    passages = store()
    result = lookup_claim_passages(supplied, passages)
    saved = lookup_claim_passages(supplied, passages)
    assert result.references[0].passages == ()
    result.references[0].reference.locator.reference = "Edited result"
    assert result.references[1] == saved.references[1]
    assert saved == lookup_claim_passages(supplied, passages)
    ref.title = "Edited caller"
    assert saved.references[0] == saved.references[1]


@pytest.mark.parametrize("eligibility", ["remove", "demote"])
@pytest.mark.parametrize("metadata", ["title", "locator"])
def test_explicit_catalog_revision_store_replacement(eligibility, metadata):
    previous = catalog()
    registry = previous.build_registry()
    second = reference(source_id="synthetic-second")
    retained = [passage(), passage("second", second)]
    passages = PassageStore(registry, retained)
    supplied = claim(reference(), second, reference(source_id="synthetic-proposal"))
    result = lookup_claim_passages(supplied, passages)
    candidate = catalog()
    candidate.catalog_id = "synthetic-v2"
    if eligibility == "remove":
        candidate.entries.pop(0)
    else:
        candidate.entries[0].curation_status = "proposed"
    changed = next(e for e in candidate.entries if e.source.source_id == "synthetic-second")
    replacement_ref = second.model_copy(deep=True)
    if metadata == "title":
        changed.source.title = replacement_ref.title = "The Imaginary Paper Almanac"
        expected = ResolutionStatus.SOURCE_METADATA_MISMATCH
    else:
        changed.source.locators[0].reference = replacement_ref.locator.reference = "C"
        expected = ResolutionStatus.LOCATOR_NOT_REGISTERED
    candidate_before = candidate.model_dump()
    assert lookup_claim_passages(supplied, passages) == result
    with pytest.raises(ValueError, match="explicit acknowledgment"):
        build_registry_for_revision(previous, candidate)
    acknowledgment = acknowledge_catalog_changes(compare_catalogs(previous, candidate))
    replacement = build_registry_for_revision(previous, candidate, acknowledgment)
    for record, status in zip(retained, [ResolutionStatus.SOURCE_NOT_REGISTERED, expected]):
        with pytest.raises(ValueError, match=status.value):
            PassageStore(replacement, [record])
    new_store = PassageStore(replacement, [passage("replacement", replacement_ref)])
    new_result = lookup_claim_passages(supplied, new_store)
    assert [entry.status for entry in new_result.references] == [
        ResolutionStatus.SOURCE_NOT_REGISTERED, expected, ResolutionStatus.SOURCE_NOT_REGISTERED,
    ]
    assert all(entry.passages == () for entry in new_result.references)
    compatible = lookup_claim_passages(claim(replacement_ref), new_store)
    assert compatible.all_references_registered and compatible.all_references_have_passages
    assert candidate.model_dump() == candidate_before
    assert candidate.entries[-1].curation_status == "proposed"
    candidate.entries.clear()
    previous.entries.clear()
    assert lookup_claim_passages(supplied, passages) == result
    assert lookup_claim_passages(claim(replacement_ref), new_store) == compatible


def test_health_and_openapi_unchanged():
    from pensieve_api.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "pensieve-api"}
        schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/api/v1/health"}
    assert set(schema["components"]["schemas"]) == {"HealthResponse"}


def test_fresh_process_claim_lookup_without_configuration_or_external_io(tmp_path):
    # Framework discovery precedes the audit hook; hooks guard regressions, not an OS sandbox.
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
        assert "pensieve_api.domain.claim_passages" not in sys.modules
        from pensieve_api.domain.claim_passages import lookup_claim_passages
        from pensieve_api.domain.source_catalog import SourceCatalog
        from pensieve_api.domain.source_passages import SourcePassage, PassageStore
        from pensieve_api.domain.source_registry import ResolutionStatus
        from pensieve_api.domain.provenance import SourceReference, SourcedLoreClaim
        catalog = SourceCatalog(schema_version=1, catalog_id="synthetic-v1", entries=[{
            "source": {"source_id": "synthetic", "title": "The Paper Atlas", "canon_tier": "book",
                       "locators": [{"kind": "chapter", "reference": "A"},
                                    {"kind": "chapter", "reference": "B"}]},
            "curation_status": "metadata_reviewed", "curation_note": "Original invented metadata.",
        }])
        ref = SourceReference(source_id="synthetic", title="The Paper Atlas", canon_tier="book",
                              locator={"kind": "chapter", "reference": "A"})
        empty = ref.model_copy(deep=True)
        empty.locator.reference = "B"
        record = SourcePassage(kind="source_passage", passage_id="one", reference=ref,
                               text="An invented paper lantern glowed.")
        store = PassageStore(catalog.build_registry(), [record])
        claim = SourcedLoreClaim(kind="sourced_lore", statement="An original observation.",
                                sources=[ref, empty, ref])
        result = lookup_claim_passages(claim, store)
        assert result.all_references_registered and not result.all_references_have_passages
        assert [r.status for r in result.references] == [ResolutionStatus.REGISTRY_MATCH] * 3
        assert [r.passages for r in result.references] == [(record,), (), (record,)]
    ''')
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code], cwd=tmp_path,
        env={"SystemRoot": os.environ["SystemRoot"]} if "SystemRoot" in os.environ else {},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

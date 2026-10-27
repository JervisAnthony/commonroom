"""Original synthetic metadata; acknowledgments declare no authenticated approval."""

from dataclasses import FrozenInstanceError, asdict, fields, is_dataclass, replace
import json
import os
import subprocess
import sys
import textwrap

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import pensieve_api.domain.catalog_governance as governance
from pensieve_api.domain.catalog_governance import (
    acknowledge_catalog_changes, build_registry_for_revision, compare_catalogs,
)
from pensieve_api.domain.provenance import (
    CanonTier, GeneratedRoleplay, SourceLocator, SourceReference, SourcedLoreClaim,
)
from pensieve_api.domain.source_catalog import CatalogEntry, SourceCatalog
from pensieve_api.domain.source_registry import ResolutionStatus


def entry(source_id="synthetic-atlas", status="metadata_reviewed"):
    return CatalogEntry.model_validate({
        "source": {
            "source_id": source_id, "title": "The Paper Lantern Almanac",
            "canon_tier": "book",
            "locators": [{"kind": "chapter", "reference": "1"},
                         {"kind": "section", "reference": "B"}],
        },
        "curation_status": status,
        "curation_note": "Original author declaration for this invented metadata.",
    })


def catalog(catalog_id="synthetic-v1"):
    return SourceCatalog(schema_version=1, catalog_id=catalog_id, entries=[
        entry(), entry("synthetic-proposal", "proposed"),
    ])


def ref(source_id="synthetic-atlas", **changes):
    return SourceReference.model_validate({
        "source_id": source_id, "title": "The Paper Lantern Almanac", "canon_tier": "book",
        "locator": {"kind": "chapter", "reference": "1"},
    } | changes)


def acknowledgment(previous, candidate):
    return acknowledge_catalog_changes(compare_catalogs(previous, candidate))


@pytest.mark.parametrize("empty", [False, True])
def test_identical_and_empty_documents(empty):
    previous = catalog()
    if empty:
        previous.entries.clear()
    candidate = SourceCatalog.model_validate_json(previous.model_dump_json())
    report = compare_catalogs(previous, candidate)
    assert not report.has_changes
    assert not report.registry_metadata_changed
    assert report.source_changes == ()
    build_registry_for_revision(previous, candidate)
    build_registry_for_revision(previous, candidate, acknowledge_catalog_changes(report))


def test_normalization_equivalence_without_input_mutation():
    previous, candidate = catalog(), catalog()
    candidate.catalog_id = " synthetic-v1 "
    for item in candidate.entries:
        item.source.source_id = f" {item.source.source_id} "
        item.source.title = f" {item.source.title} "
        item.curation_note = f" {item.curation_note} "
        item.source.locators[0].reference = " 1 "
    before = candidate.model_dump()
    assert not compare_catalogs(previous, candidate).has_changes
    assert build_registry_for_revision(previous, candidate).resolve_reference(ref()).status is ResolutionStatus.REGISTRY_MATCH
    assert candidate.model_dump() == before


@pytest.mark.parametrize("status", ["proposed", "metadata_reviewed"])
@pytest.mark.parametrize("addition", [True, False])
def test_source_membership_changes(status, addition):
    previous, candidate = catalog(), catalog()
    target = candidate if addition else previous
    target.entries.append(entry("synthetic-new", status))
    report = compare_catalogs(previous, candidate)
    change, = report.source_changes
    assert change.source_id == "synthetic-new"
    assert (change.before is None) is addition
    assert (change.after is None) is (not addition)
    assert report.has_changes
    assert report.registry_metadata_changed is (status == "metadata_reviewed")
    assert report.eligible_metadata_changed == ()
    expected = ("synthetic-new",) if status == "metadata_reviewed" else ()
    assert report.eligibility_added == (expected if addition else ())
    assert report.eligibility_removed == (() if addition else expected)
    assert (change.added_locators if addition else change.removed_locators) == (
        ("chapter", "1"), ("section", "B"),
    )


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(("field", "value"), [("title", "The Folded Moon Atlas"), ("canon_tier", CanonTier.FILM)])
def test_title_and_tier_edits(index, field, value):
    previous, candidate = catalog(), catalog()
    setattr(candidate.entries[index].source, field, value)
    report = compare_catalogs(previous, candidate)
    change, = report.source_changes
    assert getattr(change.before, field) != getattr(change.after, field)
    assert report.has_changes
    assert report.registry_metadata_changed is (index == 0)
    assert report.eligible_metadata_changed == (("synthetic-atlas",) if index == 0 else ())
    assert report.eligibility_added == report.eligibility_removed == ()


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(("action", "added", "removed"), [
    ("append", (("scene", "2"),), ()),
    ("remove", (), (("chapter", "1"),)),
    ("kind", (("scene", "1"),), (("chapter", "1"),)),
    ("reference", (("chapter", "2"),), (("chapter", "1"),)),
])
def test_locator_membership_and_edits(index, action, added, removed):
    previous, candidate = catalog(), catalog()
    locators = candidate.entries[index].source.locators
    if action == "append":
        locators.append(SourceLocator(kind="scene", reference="2"))
    elif action == "remove":
        locators.pop(0)
    elif action == "kind":
        locators[0].kind = "scene"
    else:
        locators[0].reference = "2"
    report = compare_catalogs(previous, candidate)
    change, = report.source_changes
    assert change.added_locators == added
    assert change.removed_locators == removed
    assert change.before.locators == (("chapter", "1"), ("section", "B"))
    assert change.after.locators == tuple((loc.kind, loc.reference) for loc in locators)
    assert report.registry_metadata_changed is (index == 0)


def test_promotion_demotion_distinguished_from_eligible_metadata_edits():
    previous, candidate = catalog(), catalog()
    candidate.entries[0].curation_status = "proposed"
    candidate.entries[1].curation_status = "metadata_reviewed"
    candidate.entries[1].source.title = "The Newly Declared Lantern Ledger"
    report = compare_catalogs(previous, candidate)
    assert report.eligibility_removed == ("synthetic-atlas",)
    assert report.eligibility_added == ("synthetic-proposal",)
    assert report.eligible_metadata_changed == ()
    assert report.registry_metadata_changed


def change_document(candidate, category):
    if category == "note":
        candidate.entries[0].curation_note = "An amended original explanatory note."
    elif category == "proposed":
        candidate.entries[1].source.title = "The Proposed Cloud Almanac"
    elif category == "entry_order":
        candidate.entries.reverse()
    elif category == "locator_order":
        candidate.entries[0].source.locators.reverse()
    elif category == "eligible":
        candidate.entries[0].source.title = "The Revised Lantern Almanac"
    elif category in {"eligible_add", "proposed_add"}:
        status = "metadata_reviewed" if category == "eligible_add" else "proposed"
        candidate.entries.append(entry("synthetic-new", status))
    elif category in {"eligible_remove", "proposed_remove"}:
        candidate.entries.pop(0 if category == "eligible_remove" else 1)
    elif category == "promote":
        candidate.entries[1].curation_status = "metadata_reviewed"
    elif category == "demote":
        candidate.entries[0].curation_status = "proposed"
    elif category == "locator_membership":
        candidate.entries[0].source.locators.pop()
    elif category != "id_only":
        raise AssertionError(category)


@pytest.mark.parametrize("category", [
    "note", "proposed", "entry_order", "locator_order", "eligible", "id_only",
    "eligible_add", "proposed_add", "eligible_remove", "proposed_remove",
    "promote", "demote", "locator_membership",
])
def test_every_document_change_needs_acknowledgment(category):
    previous, candidate = catalog(), catalog("synthetic-v2")
    change_document(candidate, category)
    report = compare_catalogs(previous, candidate)
    assert report.has_changes
    assert report.registry_metadata_changed is (category in {
        "eligible", "eligible_add", "eligible_remove", "promote", "demote", "locator_membership",
    })
    if category == "entry_order":
        assert report.source_changes == ()
        assert report.previous_entry_order == tuple(reversed(report.candidate_entry_order))
    if category == "id_only":
        assert report.source_changes == ()
    if category == "locator_order":
        change, = report.source_changes
        assert change.added_locators == change.removed_locators == ()
    with pytest.raises(ValueError, match="explicit acknowledgment"):
        build_registry_for_revision(previous, candidate)
    ack = acknowledge_catalog_changes(report)
    build_registry_for_revision(previous, candidate, ack)


def test_source_id_edits_are_removal_plus_addition_and_case_sensitive():
    previous, candidate = catalog(), catalog()
    candidate.entries[0].source.source_id = "SYNTHETIC-atlas"
    report = compare_catalogs(previous, candidate)
    assert [change.source_id for change in report.source_changes] == ["SYNTHETIC-atlas", "synthetic-atlas"]
    added, removed = report.source_changes
    assert added.before is None and removed.after is None
    assert report.eligibility_added == ("SYNTHETIC-atlas",)
    assert report.eligibility_removed == ("synthetic-atlas",)
    candidate = catalog()
    candidate.entries[0].source.locators[1].reference = "b"
    change, = compare_catalogs(previous, candidate).source_changes
    assert change.added_locators == (("section", "b"),)
    assert change.removed_locators == (("section", "B"),)


def test_stable_source_and_locator_delta_order_and_serialization():
    previous, candidate = catalog(), catalog("synthetic-v2")
    candidate.entries.insert(0, entry("Z-synthetic"))
    candidate.entries.append(entry("A-synthetic"))
    candidate.entries[1].source.locators = [
        SourceLocator(kind="section", reference="Z"), SourceLocator(kind="chapter", reference="9"),
        SourceLocator(kind="chapter", reference="2"),
    ]
    report = compare_catalogs(previous, candidate)
    assert [change.source_id for change in report.source_changes] == ["A-synthetic", "Z-synthetic", "synthetic-atlas"]
    assert report.source_changes[-1].added_locators == (("chapter", "2"), ("chapter", "9"), ("section", "Z"))
    payload = json.dumps(asdict(report), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    assert all(json.dumps(asdict(compare_catalogs(previous, candidate)), sort_keys=True,
                          ensure_ascii=True, separators=(",", ":")) == payload for _ in range(3))
    assert json.loads(report.previous_document) == previous.model_dump(mode="json")


@pytest.mark.parametrize("category", ["note", "proposed", "entry_order", "locator_order", "eligible"])
def test_same_id_edits_reported_but_guarded_construction_rejects(category):
    previous, candidate = catalog(), catalog(" synthetic-v1 ")
    change_document(candidate, category)
    report = compare_catalogs(previous, candidate)
    assert report.has_changes
    with pytest.raises(ValueError, match="distinct catalog_id"):
        build_registry_for_revision(previous, candidate, acknowledge_catalog_changes(report))


@pytest.mark.parametrize("side", ["previous", "candidate"])
@pytest.mark.parametrize("category", ["note", "proposed", "entry_order", "locator_order", "eligible"])
def test_binding_covers_both_documents_despite_reused_ids(side, category):
    previous, candidate = catalog(), catalog("synthetic-v2")
    ack = acknowledgment(previous, candidate)
    change_document(previous if side == "previous" else candidate, category)
    with pytest.raises(ValueError, match="exact catalog transition"):
        build_registry_for_revision(previous, candidate, ack)


def test_reverse_transition_equivalent_reconstruction_and_exact_pair_reuse():
    previous, candidate = catalog(), catalog("synthetic-v2")
    ack = acknowledgment(previous, candidate)
    with pytest.raises(ValueError, match="exact catalog transition"):
        build_registry_for_revision(candidate, previous, ack)
    for _ in range(2):
        reconstructed = SourceCatalog.model_validate_json(candidate.model_dump_json())
        reconstructed.catalog_id = " synthetic-v2 "
        assert build_registry_for_revision(previous, reconstructed, ack).resolve_reference(ref()).status is ResolutionStatus.REGISTRY_MATCH
    with pytest.raises(ValueError, match="exact catalog transition"):
        build_registry_for_revision(previous, previous, ack)


@pytest.mark.parametrize("value", [True, False, {}, "acknowledged", object()])
@pytest.mark.parametrize("changed", [False, True])
def test_wrong_acknowledgment_types_even_for_no_change(value, changed):
    previous, candidate = catalog(), catalog("synthetic-v2" if changed else "synthetic-v1")
    with pytest.raises(TypeError, match="CatalogAcknowledgment"):
        build_registry_for_revision(previous, candidate, value)


@pytest.mark.parametrize("value", [None, {}, "{}", [], GeneratedRoleplay(kind="generated_roleplay", content="An invented welcome.")])
def test_wrong_operation_inputs(value):
    valid = catalog()
    for operation in (compare_catalogs, build_registry_for_revision):
        with pytest.raises(TypeError, match="SourceCatalog"):
            operation(value, valid)
        with pytest.raises(TypeError, match="SourceCatalog"):
            operation(valid, value)
    with pytest.raises(TypeError, match="CatalogComparison"):
        acknowledge_catalog_changes(value)


@pytest.mark.parametrize("mutation", [
    lambda c: setattr(c, "schema_version", True),
    lambda c: setattr(c, "catalog_id", " "),
    lambda c: setattr(c.entries[1], "curation_note", " "),
    lambda c: setattr(c.entries[1], "curation_status", "approved"),
    lambda c: setattr(c.entries[1].source, "title", 7),
    lambda c: setattr(c.entries[1].source, "canon_tier", "BOOK"),
    lambda c: setattr(c.entries[1].source.locators[0], "kind", "page"),
    lambda c: setattr(c.entries[1].source.locators[0], "reference", " "),
    lambda c: c.entries[1].source.locators.clear(),
    lambda c: c.entries[1].source.locators.append(c.entries[1].source.locators[0]),
    lambda c: setattr(c.entries[1].source, "source_id", " synthetic-atlas "),
])
def test_both_complete_catalogs_revalidated_before_comparison_or_construction(mutation):
    invalid, valid = catalog(), catalog()
    mutation(invalid)
    for previous, candidate in [(invalid, valid), (valid, invalid)]:
        for operation in (compare_catalogs, build_registry_for_revision):
            with pytest.raises(ValidationError):
                operation(previous, candidate)


def assert_deeply_immutable(value):
    if is_dataclass(value):
        assert type(value).__dataclass_params__.frozen
        for field in fields(value):
            assert_deeply_immutable(getattr(value, field.name))
    elif isinstance(value, tuple):
        for item in value:
            assert_deeply_immutable(item)
    else:
        assert value is None or isinstance(value, (str, int, bool))


def test_results_have_no_mutable_aliases_and_inputs_unchanged():
    previous, candidate = catalog(), catalog("synthetic-v2")
    candidate.entries[0].source.title = "The Silver Paper Almanac"
    before = previous.model_dump(), candidate.model_dump()
    report = compare_catalogs(previous, candidate)
    ack = acknowledge_catalog_changes(report)
    saved = asdict(report), asdict(ack)
    assert_deeply_immutable(report)
    assert_deeply_immutable(ack)
    with pytest.raises(FrozenInstanceError):
        report.source_changes[0].after.title = "Changed"
    build_registry_for_revision(previous, candidate, ack)
    assert (previous.model_dump(), candidate.model_dump()) == before
    previous.entries.clear()
    candidate.entries[0].source.locators[0].reference = "9"
    candidate.entries.clear()
    assert (asdict(report), asdict(ack)) == saved


def test_caller_supplied_report_flags_are_not_authority():
    previous, candidate = catalog(), catalog("synthetic-v2")
    report = compare_catalogs(previous, candidate)
    # Emptying the report does not change either exact document binding.
    misleading = replace(report, source_changes=(), eligibility_added=(), eligibility_removed=(),
                         eligible_metadata_changed=())
    assert misleading.has_changes
    wrong = replace(misleading, candidate_document=misleading.previous_document)
    with pytest.raises(ValueError, match="exact catalog transition"):
        build_registry_for_revision(previous, candidate, acknowledge_catalog_changes(wrong))


def test_checked_candidate_snapshot_is_used_for_construction(monkeypatch):
    previous, candidate = catalog(), catalog("synthetic-v2")
    ack = acknowledgment(previous, candidate)
    original_compare = governance._compare_snapshots

    def mutate_caller_after_check(old, new):
        report = original_compare(old, new)
        candidate.entries[0].source.title = "An Intervening Caller Edit"
        candidate.entries[0].source.locators.clear()
        return report

    monkeypatch.setattr(governance, "_compare_snapshots", mutate_caller_after_check)
    registry = build_registry_for_revision(previous, candidate, ack)
    assert registry.resolve_reference(ref()).status is ResolutionStatus.REGISTRY_MATCH


def test_resolution_compatibility_and_existing_registry_snapshot():
    previous, candidate = catalog(), catalog("synthetic-v2")
    registry = build_registry_for_revision(previous, candidate, acknowledgment(previous, candidate))
    refs = [ref(), ref(title="Other"), ref(canon_tier="film"),
            ref(locator={"kind": "chapter", "reference": "9"}),
            ref("synthetic-proposal", title="Other"), ref()]
    expected = [ResolutionStatus.REGISTRY_MATCH, ResolutionStatus.SOURCE_METADATA_MISMATCH,
                ResolutionStatus.SOURCE_METADATA_MISMATCH, ResolutionStatus.LOCATOR_NOT_REGISTERED,
                ResolutionStatus.SOURCE_NOT_REGISTERED, ResolutionStatus.REGISTRY_MATCH]
    claim = SourcedLoreClaim(kind="sourced_lore", statement="An original imaginary observation.", sources=refs)
    result = registry.resolve_claim(claim)
    assert [item.status for item in result.references] == expected
    assert [item.reference for item in result.references] == refs
    assert not result.all_references_registered
    assert registry.resolve_claim(SourcedLoreClaim(
        kind="sourced_lore", statement="Another invented observation.", sources=[ref(), ref()],
    )).all_references_registered
    with pytest.raises(TypeError, match="SourcedLoreClaim"):
        registry.resolve_claim(GeneratedRoleplay(kind="generated_roleplay", content="An invented greeting."))
    candidate.entries[0].source.title = "Caller edit"
    candidate.entries[0].source.locators.clear()
    candidate.entries[0].curation_status = "proposed"
    candidate.entries[1].curation_status = "metadata_reviewed"
    assert registry.resolve_reference(ref()).status is ResolutionStatus.REGISTRY_MATCH
    assert registry.resolve_reference(ref("synthetic-proposal")).status is ResolutionStatus.SOURCE_NOT_REGISTERED


def test_constructed_revision_applies_eligibility_changes_without_changing_baseline():
    previous, candidate = catalog(), catalog("synthetic-v2")
    candidate.entries[0].curation_status = "proposed"
    candidate.entries[1].curation_status = "metadata_reviewed"
    registry = build_registry_for_revision(previous, candidate, acknowledgment(previous, candidate))
    assert registry.resolve_reference(ref()).status is ResolutionStatus.SOURCE_NOT_REGISTERED
    assert registry.resolve_reference(ref("synthetic-proposal")).status is ResolutionStatus.REGISTRY_MATCH
    assert [item.curation_status for item in previous.entries] == ["metadata_reviewed", "proposed"]
    assert previous.build_registry().resolve_reference(ref()).status is ResolutionStatus.REGISTRY_MATCH


def test_health_and_openapi_unchanged():
    from pensieve_api.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "pensieve-api"}
        schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/api/v1/health"}
    assert set(schema["components"]["schemas"]) == {"HealthResponse"}


def test_fresh_process_workflow_without_configuration_or_external_io(tmp_path):
    # Audit hooks are regression safeguards, not an OS sandbox.
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
        assert "pensieve_api.domain.catalog_governance" not in sys.modules
        from pensieve_api.domain.catalog_governance import (
            compare_catalogs, acknowledge_catalog_changes, build_registry_for_revision,
        )
        from pensieve_api.domain.source_catalog import SourceCatalog
        from pensieve_api.domain.provenance import SourceReference
        from pensieve_api.domain.source_registry import ResolutionStatus
        previous = SourceCatalog(schema_version=1, catalog_id="synthetic-v1", entries=[])
        candidate = SourceCatalog(schema_version=1, catalog_id="synthetic-v2", entries=[{
            "source": {"source_id": "synthetic", "title": "The Folded Lantern Atlas",
                       "canon_tier": "book", "locators": [{"kind": "chapter", "reference": "1"}]},
            "curation_status": "metadata_reviewed", "curation_note": "An original declared example.",
        }])
        report = compare_catalogs(previous, candidate)
        assert report.has_changes and report.registry_metadata_changed
        ack = acknowledge_catalog_changes(report)
        registry = build_registry_for_revision(previous, candidate, ack)
        ref = SourceReference(source_id="synthetic", title="The Folded Lantern Atlas",
                              canon_tier="book", locator={"kind": "chapter", "reference": "1"})
        assert registry.resolve_reference(ref).status is ResolutionStatus.REGISTRY_MATCH
    ''')
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code], cwd=tmp_path,
        env={"SystemRoot": os.environ["SystemRoot"]} if "SystemRoot" in os.environ else {},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

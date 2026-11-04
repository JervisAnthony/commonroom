"""Original synthetic data; availability never evaluates substantive support."""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import pensieve_api.domain.passage_bundle as module
from pensieve_api.domain.passage_bundle import PassageBundle
from pensieve_api.domain.catalog_governance import (
    acknowledge_catalog_changes, build_registry_for_revision, compare_catalogs,
)
from pensieve_api.domain.provenance import GeneratedRoleplay, SourceReference, SourcedLoreClaim
from pensieve_api.domain.source_catalog import SourceCatalog
from pensieve_api.domain.source_passages import PassageStore
from pensieve_api.main import app, create_app


EXAMPLE = Path(__file__).parents[1] / "examples/synthetic_passage_bundle.v1.json"
URL = "/api/v1/claims/passages/lookup"


def document():
    # Explicit caller I/O, outside guarded in-memory operations.
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def bundle():
    return PassageBundle.model_validate(document())


def reference(**changes):
    return SourceReference.model_validate(document()["passages"][0]["reference"] | changes)


def replace_at(data, path, value):
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


def test_python_json_and_nested_models_round_trip():
    data = document()
    parsed = PassageBundle(**data)
    assert isinstance(parsed.catalog, SourceCatalog)
    assert PassageBundle.model_validate(parsed.model_dump()) == parsed
    assert PassageBundle.model_validate_json(parsed.model_dump_json()) == parsed
    assert parsed.model_dump(mode="json") == data
    assert PassageBundle(schema_version=1, catalog=parsed.catalog, passages=parsed.passages) == parsed
    assert PassageBundle.model_validate_json(EXAMPLE.read_text(encoding="utf-8")) == parsed


@pytest.mark.parametrize("field", ["schema_version", "catalog", "passages"])
def test_required_fields(field):
    data = document()
    del data[field]
    for validate, value in [(PassageBundle.model_validate, data),
                            (PassageBundle.model_validate_json, json.dumps(data))]:
        with pytest.raises(ValidationError):
            validate(value)


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, 0, 2, -1])
def test_exact_integer_format_version(value):
    data = document() | {"schema_version": value}
    with pytest.raises(ValidationError):
        PassageBundle.model_validate(data)
    with pytest.raises(ValidationError):
        PassageBundle.model_validate_json(json.dumps(data))


INVALID_EDITS = [
    (("extra",), True),
    (("catalog", "extra"), True),
    (("catalog", "schema_version"), True),
    (("catalog", "catalog_id"), 7),
    (("catalog", "entries", 0, "extra"), True),
    (("catalog", "entries", 0, "curation_status"), "reviewed"),
    (("catalog", "entries", 1, "curation_note"), " "),
    (("catalog", "entries", 0, "source", "extra"), True),
    (("catalog", "entries", 0, "source", "title"), 8),
    (("catalog", "entries", 0, "source", "canon_tier"), "BOOK"),
    (("catalog", "entries", 0, "source", "locators"), []),
    (("catalog", "entries", 0, "source", "locators", 0, "extra"), True),
    (("catalog", "entries", 0, "source", "locators", 0, "kind"), "page"),
    (("passages", 1, "extra"), True),
    (("passages", 1, "kind"), "generated_roleplay"),
    (("passages", 1, "passage_id"), " "),
    *[(("passages", 1, "text"), value) for value in [None, True, 42, " ", [], {}]],
    (("passages", 1, "reference", "extra"), True),
    (("passages", 1, "reference", "source_id"), 3),
    (("passages", 1, "reference", "title"), " "),
    (("passages", 1, "reference", "canon_tier"), True),
    (("passages", 1, "reference", "locator", "extra"), True),
    (("passages", 1, "reference", "locator", "kind"), "Chapter"),
    (("passages", 1, "reference", "locator", "reference"), 3),
]


@pytest.mark.parametrize(("path", "value"), INVALID_EDITS)
def test_strict_nested_contracts(path, value):
    data = document()
    replace_at(data, path, value)
    with pytest.raises(ValidationError):
        PassageBundle.model_validate(data)
    with pytest.raises(ValidationError):
        PassageBundle.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("value", [None, {}, "passages", (), iter([]), [None],
    [GeneratedRoleplay(kind="generated_roleplay", content="Original greeting.")],
    [SourcedLoreClaim(kind="sourced_lore", statement="Original claim.", sources=[reference()])],
    [reference()], [{"unrelated": True}]])
def test_strict_ordered_passage_list(value):
    with pytest.raises(ValidationError):
        PassageBundle.model_validate(document() | {"passages": value})


@pytest.mark.parametrize("value", [None, {}, "passages", [None], [{"kind": "generated_roleplay", "content": "Original."}]])
def test_json_passage_collection_contract(value):
    with pytest.raises(ValidationError):
        PassageBundle.model_validate_json(json.dumps(document() | {"passages": value}))


def test_catalog_uniqueness_and_empty_structures():
    data = document()
    data["catalog"]["entries"].append(deepcopy(data["catalog"]["entries"][0]))
    data["catalog"]["entries"][-1]["source"]["source_id"] = " synthetic-atlas "
    with pytest.raises(ValidationError, match="source IDs must be unique"):
        PassageBundle.model_validate(data)
    for entries in [[], [document()["catalog"]["entries"][1]]]:
        empty = PassageBundle(schema_version=1, catalog={"schema_version": 1,
            "catalog_id": "empty", "entries": entries}, passages=[])
        assert empty.build_store().lookup_reference(reference()).status.value == "SOURCE_NOT_REGISTERED"
    eligible = bundle()
    eligible.passages.clear()
    result = eligible.build_store().lookup_reference(reference())
    assert result.status.value == "REGISTRY_MATCH" and result.passages == ()


def test_normalization_order_unicode_and_permitted_identical_text():
    data = document()
    data["passages"][0]["text"] = " \nInès  opened\nthe café. \t"
    data["passages"][1]["text"] = data["passages"][0]["text"]
    data["passages"][0]["passage_id"] = " arrival "
    data["passages"][0]["reference"]["locator"]["reference"] = " A "
    before = deepcopy(data)
    parsed = PassageBundle.model_validate(data)
    result = parsed.build_store().lookup_reference(reference())
    assert [p.passage_id for p in result.passages] == ["arrival", "departure"]
    assert [p.text for p in result.passages] == ["Inès  opened\nthe café."] * 2
    assert data == before


def test_duplicate_ids_parse_but_fail_build_and_case_distinct_ids_work():
    parsed = bundle()
    parsed.passages[1].passage_id = " arrival "
    parsed = PassageBundle.model_validate(parsed.model_dump())
    with pytest.raises(ValueError, match="duplicate passage_id: arrival"):
        parsed.build_store()
    parsed.passages[1].passage_id = "Arrival"
    assert [p.passage_id for p in parsed.build_store().lookup_reference(reference()).passages] == [
        "arrival", "Arrival"]


@pytest.mark.parametrize(("changes", "status"), [
    ({"source_id": "synthetic-film"}, "SOURCE_NOT_REGISTERED"),
    ({"source_id": "missing", "title": "Wrong", "locator": {"kind": "chapter", "reference": "Z"}}, "SOURCE_NOT_REGISTERED"),
    ({"source_id": "SYNTHETIC-ATLAS"}, "SOURCE_NOT_REGISTERED"),
    ({"title": "the folded lantern atlas", "locator": {"kind": "chapter", "reference": "Z"}}, "SOURCE_METADATA_MISMATCH"),
    ({"canon_tier": "film"}, "SOURCE_METADATA_MISMATCH"),
    ({"locator": {"kind": "scene", "reference": "A"}}, "LOCATOR_NOT_REGISTERED"),
    ({"locator": {"kind": "chapter", "reference": "a"}}, "LOCATOR_NOT_REGISTERED"),
])
def test_structural_validity_is_separate_from_construction_and_resolution(changes, status):
    parsed = bundle()
    ref = reference(**changes)
    assert parsed.build_store().lookup_reference(ref).status.value == status
    parsed.passages[1].reference = ref
    parsed = PassageBundle.model_validate_json(parsed.model_dump_json())
    with pytest.raises(ValueError, match=status):
        parsed.build_store()


def test_parse_has_no_construction_and_build_delegates_once(monkeypatch):
    # Autosnapshot catalog is a new object; spy on its public operation.
    calls = []
    original = SourceCatalog.build_registry
    def build(catalog):
        calls.append(catalog)
        return original(catalog)
    store = Mock(wraps=PassageStore)
    monkeypatch.setattr(SourceCatalog, "build_registry", build)
    monkeypatch.setattr(module, "PassageStore", store)
    parsed = bundle()
    assert calls == []
    store.assert_not_called()
    result = parsed.build_store()
    assert isinstance(result, PassageStore)
    assert len(calls) == 1 and calls[0] is not parsed.catalog
    assert calls[0].entries[1].curation_status == "proposed"
    store.assert_called_once()
    assert store.call_args.args[1] == parsed.passages
    assert store.call_args.args[1] is not parsed.passages


@pytest.mark.parametrize(("path", "value"), [
    (path, value) for path, value in INVALID_EDITS if path[-1] != "extra"
])
def test_complete_mutable_revalidation_precedes_all_delegates(monkeypatch, path, value):
    parsed = bundle()
    # Inject malformed mutable state at arbitrary depth, including a later record.
    target = parsed
    for key in path[:-1]:
        target = target[key] if isinstance(key, int) else getattr(target, key)
    setattr(target, path[-1], value)
    before = parsed.model_dump(warnings=False)
    registry = Mock(side_effect=AssertionError("Registry called too early"))
    store = Mock(side_effect=AssertionError("Store called too early"))
    monkeypatch.setattr(SourceCatalog, "build_registry", registry)
    monkeypatch.setattr(module, "PassageStore", store)
    with pytest.raises(ValidationError):
        parsed.build_store()
    registry.assert_not_called()
    store.assert_not_called()
    assert parsed.model_dump(warnings=False) == before


@pytest.mark.parametrize("edit", ["version", "proposal", "collection", "later_reference"])
def test_other_mutations_fail_before_delegates(monkeypatch, edit):
    parsed = bundle()
    if edit == "version":
        parsed.schema_version = 1.0
    elif edit == "proposal":
        parsed.catalog.entries[1].source.locators[0].reference = None
    elif edit == "collection":
        parsed.passages = tuple(parsed.passages)
    else:
        parsed.passages.append(parsed.passages[0].model_copy(deep=True))
        parsed.passages[-1].reference = {"bad": True}
    registry = Mock(side_effect=AssertionError("Unexpected construction"))
    monkeypatch.setattr(SourceCatalog, "build_registry", registry)
    with pytest.raises(ValidationError):
        parsed.build_store()
    registry.assert_not_called()


def test_independent_snapshots_and_failed_build_preserves_inputs():
    parsed = bundle()
    first, second = parsed.build_store(), parsed.build_store()
    ref = reference()
    saved = first.lookup_reference(ref)
    returned = first.lookup_reference(ref)
    returned.passages[0].text = "Result edit"
    returned.passages[0].reference.title = "Result title"
    returned.passages[0].reference.locator.reference = "Z"
    assert first.lookup_reference(ref) == second.lookup_reference(ref) == saved
    assert parsed.passages[0].text == saved.passages[0].text
    parsed.passages[0].text = "Explicit passage-only edit."
    third = parsed.build_store()
    assert third.lookup_reference(ref).passages[0].text == "Explicit passage-only edit."
    assert first.lookup_reference(ref) == second.lookup_reference(ref) == saved
    parsed.catalog.entries[0].source.title = "Changed title"
    parsed.passages[1].reference.locator.reference = "Z"
    before = parsed.model_dump()
    with pytest.raises(ValueError, match="SOURCE_METADATA_MISMATCH"):
        parsed.build_store()
    assert parsed.model_dump() == before
    parsed.catalog.entries.clear()
    parsed.passages.clear()
    assert first.lookup_reference(ref) == second.lookup_reference(ref) == saved
    assert len(third.lookup_reference(ref).passages) == 2


def test_valid_metadata_and_collection_edits_apply_only_to_later_builds():
    parsed = bundle()
    old = parsed.build_store()
    old_ref = reference()
    parsed.catalog.entries[0].source.title = "The Revised Lantern Atlas"
    parsed.catalog.entries[0].source.locators[0].reference = "C"
    for passage in parsed.passages:
        passage.reference.title = "The Revised Lantern Atlas"
        passage.reference.locator.reference = "C"
    parsed.passages.reverse()
    new_ref = parsed.passages[0].reference.model_copy(deep=True)
    new = parsed.build_store()
    assert [p.passage_id for p in new.lookup_reference(new_ref).passages] == ["departure", "arrival"]
    assert [p.passage_id for p in old.lookup_reference(old_ref).passages] == ["arrival", "departure"]
    assert new.lookup_reference(old_ref).status.value == "SOURCE_METADATA_MISMATCH"
    parsed.catalog.entries[0].curation_status = "proposed"
    parsed.passages.clear()
    assert parsed.build_store().lookup_reference(new_ref).status.value == "SOURCE_NOT_REGISTERED"
    assert len(new.lookup_reference(new_ref).passages) == 2


def test_exact_source_and_locator_isolation():
    parsed = bundle()
    second = parsed.catalog.entries[0].model_copy(deep=True)
    second.source.source_id = "synthetic-second"
    parsed.catalog.entries.append(second)
    parsed.catalog.entries[0].source.locators.append(
        parsed.catalog.entries[0].source.locators[0].model_copy(update={"kind": "scene"}))
    second_passage = parsed.passages[0].model_copy(deep=True)
    second_passage.passage_id = "second-source"
    second_passage.reference.source_id = "synthetic-second"
    scene_passage = parsed.passages[0].model_copy(deep=True)
    scene_passage.passage_id = "scene"
    scene_passage.reference.locator.kind = "scene"
    parsed.passages.extend([second_passage, scene_passage])
    store = parsed.build_store()
    assert [p.passage_id for p in store.lookup_reference(reference()).passages] == ["arrival", "departure"]
    assert store.lookup_reference(second_passage.reference).passages == (second_passage,)
    assert store.lookup_reference(scene_passage.reference).passages == (scene_passage,)


def test_governed_path_still_requires_exact_pair_id_and_acknowledgment():
    previous = bundle()
    candidate = bundle()
    candidate.passages[0].text = "New unverified prose."
    assert not compare_catalogs(previous.catalog, candidate.catalog).has_changes
    registry = build_registry_for_revision(previous.catalog, candidate.catalog)
    assert PassageStore(registry, candidate.passages).lookup_reference(reference()).passages[0].text == "New unverified prose."
    candidate.catalog.entries[1].curation_note = "Revised original note."
    ack = acknowledge_catalog_changes(compare_catalogs(previous.catalog, candidate.catalog))
    with pytest.raises(ValueError, match="distinct catalog_id"):
        build_registry_for_revision(previous.catalog, candidate.catalog, ack)
    candidate.catalog.catalog_id = "synthetic-v2"
    with pytest.raises(ValueError, match="explicit acknowledgment"):
        build_registry_for_revision(previous.catalog, candidate.catalog)
    with pytest.raises(ValueError, match="exact catalog transition"):
        build_registry_for_revision(previous.catalog, candidate.catalog, ack)
    ack = acknowledge_catalog_changes(compare_catalogs(previous.catalog, candidate.catalog))
    registry = build_registry_for_revision(previous.catalog, candidate.catalog, ack)
    assert PassageStore(registry, candidate.passages).lookup_reference(reference()).passages == tuple(candidate.passages)
    wrong_baseline = bundle().catalog
    wrong_baseline.catalog_id = "other-baseline"
    with pytest.raises(ValueError, match="exact catalog transition"):
        build_registry_for_revision(wrong_baseline, candidate.catalog, ack)


def test_checked_in_example_http_and_unchanged_schema():
    parsed = bundle()
    store = parsed.build_store()
    assert isinstance(store, PassageStore)
    proposal = parsed.catalog.entries[1].source
    assert store.lookup_reference(SourceReference(source_id=proposal.source_id, title=proposal.title,
        canon_tier=proposal.canon_tier, locator=proposal.locators[0])).status.value == "SOURCE_NOT_REGISTERED"
    a, b = reference(), reference(locator={"kind": "chapter", "reference": "B"})
    refs = [a, b, a]
    claim = {"kind": "sourced_lore", "statement": "A fictional lantern arrives.",
             "sources": [r.model_dump(mode="json") for r in refs]}
    expected = {"statement": claim["statement"], "references": [
        {"reference": r.model_dump(mode="json"), "status": "REGISTRY_MATCH",
         "passages": [] if r == b else [p.model_dump(mode="json") for p in parsed.passages]}
        for r in refs], "all_references_registered": True, "all_references_have_passages": False}
    with TestClient(create_app(passage_store=store)) as client:
        response = client.post(URL, json=claim)
        assert response.status_code == 200 and response.json() == expected
        assert [len(r["passages"]) for r in response.json()["references"]] == [2, 0, 2]
        assert [p["passage_id"] for p in response.json()["references"][0]["passages"]] == ["arrival", "departure"]
        unrelated = "A submarine counts purple clouds."
        assert client.post(URL, json=claim | {"statement": unrelated}).json() == expected | {"statement": unrelated}
        schema = client.get("/openapi.json").json()
    with TestClient(app) as default:
        response = default.post(URL, json=claim)
        assert response.status_code == 503
        assert response.json() == {"detail": "Passage lookup is not configured"}
        for path in ["/api/v1/health", "/docs", "/redoc", "/openapi.json"]:
            assert default.get(path).status_code == 200
        assert schema == default.get("/openapi.json").json()
    assert {p: set(ops) for p, ops in schema["paths"].items()} == {
        "/api/v1/health": {"get"}, URL: {"post"}}
    assert set(schema["components"]["schemas"]) == {
        "HealthResponse", "SourcedLoreClaim", "SourceReference", "SourceLocator", "SourcePassage",
        "ReferencePassagesResponse", "ClaimPassageResponse", "LookupUnavailableResponse",
        "CanonTier", "ResolutionStatus", "HTTPValidationError", "ValidationError"}


def test_fresh_process_import_parse_build_lookup_without_external_io(tmp_path):
    data = document()  # Reading the example is explicit and precedes the guard.
    code = textwrap.dedent('''
        import asyncio
        import json
        import os
        import sys
        import pydantic
        from fastapi.testclient import TestClient

        class FrameworkWarmup(pydantic.BaseModel):
            pass

        loop = asyncio.new_event_loop()  # Windows framework socket setup.
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
        from pensieve_api.domain.passage_bundle import PassageBundle
        from pensieve_api.main import create_app
        parsed = PassageBundle.model_validate_json(sys.argv[1])
        store = parsed.build_store()
        ref = parsed.passages[0].reference
        assert store.lookup_reference(ref).passages == tuple(parsed.passages)
        with TestClient(create_app(passage_store=store),
                        backend_options={"loop_factory": lambda: loop}) as client:
            response = client.post("/api/v1/claims/passages/lookup", json={
                "kind": "sourced_lore", "statement": "An original observation.",
                "sources": [ref.model_dump(mode="json")]})
            assert response.status_code == 200
            assert response.json()["all_references_have_passages"] is True
    ''')
    # Audit hooks check regressions; they are not an OS sandbox.
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, json.dumps(data)],
        cwd=tmp_path, env={"SystemRoot": os.environ["SystemRoot"]} if "SystemRoot" in os.environ else {},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr

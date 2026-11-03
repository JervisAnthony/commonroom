"""HTTP availability contract using original fictional metadata and prose."""

from copy import deepcopy
import json
import os
import subprocess
import sys
import textwrap
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import pensieve_api.claim_passage_api as api
from pensieve_api.domain.catalog_governance import (
    acknowledge_catalog_changes, build_registry_for_revision, compare_catalogs,
)
from pensieve_api.domain.claim_passages import ClaimPassageLookup, ReferencePassages
from pensieve_api.domain.provenance import SourceReference, SourcedLoreClaim
from pensieve_api.domain.source_catalog import SourceCatalog
from pensieve_api.domain.source_passages import PassageStore, SourcePassage
from pensieve_api.domain.source_registry import ResolutionStatus
from pensieve_api.main import app, create_app


URL = "/api/v1/claims/passages/lookup"


def reference(**changes):
    return {
        "source_id": "synthetic-atlas", "title": "The Paper Lantern Atlas", "canon_tier": "book",
        "locator": {"kind": "chapter", "reference": "A"},
    } | changes


def claim(*refs):
    return {"kind": "sourced_lore", "statement": "An invented lantern crosses the orchard.",
            "sources": list(refs) if refs else [reference()]}


def catalog():
    return SourceCatalog(schema_version=1, catalog_id="synthetic-v1", entries=[{
        "source": {"source_id": source_id, "title": "The Paper Lantern Atlas", "canon_tier": "book",
                   "locators": [{"kind": "chapter", "reference": "A"},
                                {"kind": "scene", "reference": "A"},
                                {"kind": "chapter", "reference": "B"}]},
        "curation_status": status, "curation_note": "Original fictional eligibility declaration.",
    } for source_id, status in [("synthetic-atlas", "metadata_reviewed"),
                                 ("synthetic-second", "metadata_reviewed"),
                                 ("synthetic-proposal", "proposed")]])


def passage(passage_id="one", ref=None):
    return SourcePassage(kind="source_passage", passage_id=passage_id,
                         reference=reference() if ref is None else ref,
                         text="  Caf\u00e9  lantern\n\t\u96ea glows.  ")


@pytest.fixture
def store():
    return PassageStore(catalog().build_registry(), [passage("z"), passage("a")])


@pytest.fixture
def client(store):
    with TestClient(create_app(passage_store=store)) as client:
        yield client


def test_default_empty_and_independent_apps(store):
    empty = PassageStore(SourceCatalog(schema_version=1, catalog_id="empty", entries=[]).build_registry(), [])
    other = PassageStore(catalog().build_registry(), [passage("other")])
    with TestClient(app) as default, TestClient(create_app(passage_store=store)) as first:
        for _ in range(2):
            assert default.get("/api/v1/health").json() == {"status": "ok", "service": "pensieve-api"}
            response = default.post(URL, json=claim())
            assert response.status_code == 503
            assert response.json() == {"detail": "Passage lookup is not configured"}
            with TestClient(create_app(passage_store=empty)) as second:
                response = second.post(URL, json=claim())
                assert response.status_code == 200
                assert response.json() == {
                    "statement": claim()["statement"], "references": [{"reference": reference(),
                        "status": "SOURCE_NOT_REGISTERED", "passages": []}],
                    "all_references_registered": False, "all_references_have_passages": False,
                }
            with TestClient(create_app(passage_store=other)) as third:
                assert third.post(URL, json=claim()).json()["references"][0]["passages"] == [
                    passage("other").model_dump(mode="json")]
            assert [p["passage_id"] for p in first.post(URL, json=claim()).json()["references"][0]["passages"]] == ["z", "a"]
    with TestClient(create_app()) as fresh:
        assert fresh.post(URL, json=claim()).status_code == 503


@pytest.mark.parametrize("value", [{}, [], "store", False, 0, object(), catalog()])
def test_factory_rejects_unrelated_objects(value):
    with pytest.raises(TypeError, match="passage_store must be a PassageStore or None"):
        create_app(passage_store=value)


@pytest.mark.parametrize("count", [1, 2])
def test_exact_success_json_and_normalization(count):
    records = [passage(str(i)) for i in range(count)]
    supplied = claim(reference(source_id=" synthetic-atlas ", title=" The Paper Lantern Atlas ",
                               locator={"kind": "chapter", "reference": " A "}))
    supplied["statement"] = " \nAn unrelated  caf\u00e9\n\u96ea observation. \t"
    with TestClient(create_app(passage_store=PassageStore(catalog().build_registry(), records))) as client:
        response = client.post(URL, json=supplied)
    assert response.status_code == 200
    assert response.json() == {
        "statement": "An unrelated  caf\u00e9\n\u96ea observation.",
        "references": [{"reference": reference(), "status": "REGISTRY_MATCH",
                        "passages": [p.model_dump(mode="json") for p in records]}],
        "all_references_registered": True, "all_references_have_passages": True,
    }


def test_all_statuses_precedence_order_duplicates_and_later_results(client):
    refs = [reference(source_id="missing", title="Wrong", canon_tier="film",
                      locator={"kind": "other", "reference": "missing"}), reference(),
            reference(title="Wrong", locator={"kind": "other", "reference": "missing"}),
            reference(locator={"kind": "other", "reference": "missing"}), reference(),
            reference(locator={"kind": "chapter", "reference": "B"})]
    response = client.post(URL, json=claim(*refs))
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "statement": claim()["statement"],
        "references": [{"reference": ref, "status": status, "passages": records}
                       for ref, status, records in zip(refs, [
            "SOURCE_NOT_REGISTERED", "REGISTRY_MATCH", "SOURCE_METADATA_MISMATCH",
            "LOCATOR_NOT_REGISTERED", "REGISTRY_MATCH", "REGISTRY_MATCH"], [
                [], [passage("z").model_dump(mode="json"), passage("a").model_dump(mode="json")],
                [], [], [passage("z").model_dump(mode="json"), passage("a").model_dump(mode="json")], []])],
        "all_references_registered": False, "all_references_have_passages": False,
    }


@pytest.mark.parametrize(("refs", "registered", "available"), [
    ([reference(), reference()], True, True),
    ([reference(), reference(locator={"kind": "chapter", "reference": "B"})], True, False),
    ([reference(source_id="missing"), reference()], False, False),
    ([reference(source_id="missing")], False, False),
])
def test_aggregates_and_unrelated_statement(client, refs, registered, available):
    body = client.post(URL, json=claim(*refs)).json()
    assert body["all_references_registered"] is registered
    assert body["all_references_have_passages"] is available
    unrelated = client.post(URL, json=claim(*refs) | {"statement": "A submarine counts purple clouds."}).json()
    assert unrelated == body | {"statement": "A submarine counts purple clouds."}


def test_source_tier_locator_and_case_isolation():
    refs = [reference(), reference(source_id="synthetic-second"),
            reference(locator={"kind": "scene", "reference": "A"})]
    records = [passage(str(i), ref) for i, ref in enumerate(refs)]
    extras = [reference(canon_tier="film"), reference(title="the paper lantern atlas"),
              reference(locator={"kind": "chapter", "reference": "a"}),
              reference(source_id="SYNTHETIC-ATLAS"), reference(source_id="synthetic-proposal")]
    with TestClient(create_app(passage_store=PassageStore(catalog().build_registry(), records))) as client:
        body = client.post(URL, json=claim(*refs, *extras)).json()
    assert [entry["passages"] for entry in body["references"]] == [
        [p.model_dump(mode="json")] for p in records] + [[]] * len(extras)
    assert [entry["status"] for entry in body["references"][3:]] == [
        "SOURCE_METADATA_MISMATCH", "SOURCE_METADATA_MISMATCH", "LOCATOR_NOT_REGISTERED",
        "SOURCE_NOT_REGISTERED", "SOURCE_NOT_REGISTERED"]


INVALID_BODIES = [
    {}, {"kind": "generated_roleplay", "content": "An original greeting."},
    {k: v for k, v in claim().items() if k != "kind"},
    {k: v for k, v in claim().items() if k != "sources"},
    {k: v for k, v in claim().items() if k != "statement"},
    *[claim() | {"kind": kind} for kind in [None, "generated_roleplay", "SOURCED_LORE", 1]],
    *[claim() | {"statement": value} for value in ["", " \n", 1, True, None, [], {}]],
    *[claim() | {"sources": value} for value in [[], None, {}, "source", [None]]],
    *[claim() | {key: value} for key, value in [
        ("passage_store", {}), ("registry", {}), ("catalog", {}), ("text", "Trusted prose"),
        ("acknowledgment", True), ("all_references_registered", True),
        ("all_references_have_passages", True), ("verified", True), ("content", "Roleplay")]],
    *[claim(reference(), reference(**change)) for change in [
        {"source_id": " "}, {"title": 7}, {"canon_tier": "BOOK"}, {"canon_tier": True},
        {"locator": {}}, {"locator": {"kind": "page", "reference": "A"}},
        {"locator": {"kind": "chapter", "reference": " "}},
        {"locator": {"kind": "chapter", "reference": 1}},
        {"locator": {"kind": "chapter", "reference": "A", "text": "Override"}},
        {"trusted": True},
    ]],
    [], "claim", 1, True, None,
]


@pytest.mark.parametrize("body", INVALID_BODIES)
def test_validation_precedes_lookup_on_configured_app(client, store, monkeypatch, body):
    operation = Mock(side_effect=AssertionError("Unexpected domain lookup"))
    passage_lookup = Mock(side_effect=AssertionError("Unexpected passage lookup"))
    monkeypatch.setattr(api, "lookup_claim_passages", operation)
    monkeypatch.setattr(store, "lookup_reference", passage_lookup)
    response = client.post(URL, content=json.dumps(body), headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    operation.assert_not_called()
    passage_lookup.assert_not_called()


def test_malformed_json_and_missing_body(client, monkeypatch):
    operation = Mock(side_effect=AssertionError("Unexpected lookup"))
    monkeypatch.setattr(api, "lookup_claim_passages", operation)
    for content in ['{"kind":', '']:
        assert client.post(URL, content=content, headers={"Content-Type": "application/json"}).status_code == 422
    operation.assert_not_called()


def test_delegates_once_and_projects_domain_values(client, store, monkeypatch):
    # Deliberately unusual aggregates ensure the adapter consumes domain properties.
    class DomainResult(ClaimPassageLookup):
        @property
        def all_references_registered(self):
            return False

        @property
        def all_references_have_passages(self):
            return True

    result = DomainResult("Domain normalized statement", (
        ReferencePassages(SourceReference(**reference()), ResolutionStatus.REGISTRY_MATCH, (passage(),)),
    ))
    operation = Mock(return_value=result)
    monkeypatch.setattr(api, "lookup_claim_passages", operation)
    body = client.post(URL, json=claim()).json()
    operation.assert_called_once()
    supplied, used_store = operation.call_args.args
    assert isinstance(supplied, SourcedLoreClaim)
    assert supplied.model_dump(mode="json") == claim()
    assert used_store is store
    assert body == {"statement": result.statement, "references": [{"reference": reference(),
        "status": "REGISTRY_MATCH", "passages": [passage().model_dump(mode="json")]}],
        "all_references_registered": False, "all_references_have_passages": True}


def test_unexpected_domain_failures_propagate(client, monkeypatch):
    operation = Mock(side_effect=RuntimeError("Synthetic lookup failure"))
    monkeypatch.setattr(api, "lookup_claim_passages", operation)
    with pytest.raises(RuntimeError, match="Synthetic lookup failure"):
        client.post(URL, json=claim())
    operation.assert_called_once()


def test_client_and_input_mutations_do_not_change_app_snapshot():
    supplied_catalog = catalog()
    record = passage()
    records = [record]
    store = PassageStore(supplied_catalog.build_registry(), records)
    with TestClient(create_app(passage_store=store)) as client:
        saved = client.post(URL, json=claim(reference(), reference())).json()
        edited = deepcopy(saved)
        edited["references"][0]["passages"][0]["text"] = "Client edit"
        edited["references"][0]["reference"]["locator"]["reference"] = "Changed"
        edited["references"].clear()
        record.text = "Caller edit"
        record.reference.title = "Caller title"
        record.reference.locator.reference = "Changed"
        records.clear()
        supplied_catalog.entries[0].source.title = "Later catalog"
        supplied_catalog.entries[0].curation_status = "proposed"
        supplied_catalog.entries.clear()
        assert client.post(URL, json=claim(reference(), reference())).json() == saved
    assert store.lookup_reference(SourceReference(**reference())).passages == (passage(),)


def test_explicit_revision_replacement_and_proposal_exclusion():
    previous, candidate = catalog(), catalog()
    old_store = PassageStore(previous.build_registry(), [passage()])
    candidate.catalog_id = "synthetic-v2"
    candidate.entries[0].source.title = "The Revised Paper Atlas"
    revised = reference(title="The Revised Paper Atlas")
    with TestClient(create_app(passage_store=old_store)) as old:
        before = old.post(URL, json=claim()).json()
        with pytest.raises(ValueError, match="explicit acknowledgment"):
            build_registry_for_revision(previous, candidate)
        registry = build_registry_for_revision(previous, candidate,
            acknowledge_catalog_changes(compare_catalogs(previous, candidate)))
        with pytest.raises(ValueError, match="SOURCE_METADATA_MISMATCH"):
            PassageStore(registry, [passage()])
        with TestClient(create_app(passage_store=PassageStore(registry, [passage("revised", revised)]))) as new:
            assert new.post(URL, json=claim()).json()["references"][0]["status"] == "SOURCE_METADATA_MISMATCH"
            body = new.post(URL, json=claim(revised)).json()
            assert body["all_references_have_passages"] is True
            assert body["references"][0]["passages"] == [passage("revised", revised).model_dump(mode="json")]
            assert new.post(URL, json=claim(reference(source_id="synthetic-proposal"))).json()["references"][0]["status"] == "SOURCE_NOT_REGISTERED"
            candidate.entries.clear()
            previous.entries.clear()
            assert new.post(URL, json=claim(revised)).json() == body
        assert old.post(URL, json=claim()).json() == before
        assert old.post(URL, json=claim(revised)).json()["references"][0]["status"] == "SOURCE_METADATA_MISMATCH"


def test_health_docs_methods_and_complete_openapi(client):
    assert client.app.title == "Pensieve API"
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "pensieve-api"}
    for path in ["/docs", "/redoc", "/openapi.json"]:
        assert client.get(path).status_code == 200
    assert client.get("/api/v1/unknown").status_code == 404
    assert client.get(URL).status_code == 405
    schema = client.get("/openapi.json").json()
    assert {path: set(operations) for path, operations in schema["paths"].items()} == {
        "/api/v1/health": {"get"}, URL: {"post"}}
    operation = schema["paths"][URL]["post"]
    assert "parameters" not in operation
    assert operation["requestBody"] == {"required": True, "content": {"application/json": {
        "schema": {"$ref": "#/components/schemas/SourcedLoreClaim"}}}}
    assert set(operation["responses"]) == {"200", "422", "503"}
    for status, model in [("200", "ClaimPassageResponse"), ("422", "HTTPValidationError"),
                          ("503", "LookupUnavailableResponse")]:
        assert operation["responses"][status]["content"]["application/json"]["schema"] == {
            "$ref": f"#/components/schemas/{model}"}
    models = schema["components"]["schemas"]
    fields = {
        "HealthResponse": {"status", "service"},
        "SourcedLoreClaim": {"kind", "statement", "sources"},
        "SourceReference": {"source_id", "title", "canon_tier", "locator"},
        "SourceLocator": {"kind", "reference"},
        "SourcePassage": {"kind", "passage_id", "reference", "text"},
        "ReferencePassagesResponse": {"reference", "status", "passages"},
        "ClaimPassageResponse": {"statement", "references", "all_references_registered", "all_references_have_passages"},
        "LookupUnavailableResponse": {"detail"},
    }
    assert set(models) == set(fields) | {"CanonTier", "ResolutionStatus", "HTTPValidationError", "ValidationError"}
    for name, required in fields.items():
        assert set(models[name]["properties"]) == required
        assert set(models[name]["required"]) == required
        assert all("default" not in p for p in models[name]["properties"].values())
        if name != "HealthResponse":
            assert models[name]["additionalProperties"] is False
    assert models["HealthResponse"]["properties"] == {
        "status": {"type": "string", "title": "Status"},
        "service": {"type": "string", "title": "Service"}}
    assert models["CanonTier"]["enum"] == ["book", "film", "expanded_publication"]
    assert models["ResolutionStatus"]["enum"] == ["SOURCE_NOT_REGISTERED", "SOURCE_METADATA_MISMATCH", "LOCATOR_NOT_REGISTERED", "REGISTRY_MATCH"]
    assert models["SourceLocator"]["properties"]["kind"]["enum"] == ["chapter", "scene", "section", "other"]
    assert models["SourcedLoreClaim"]["properties"]["kind"]["const"] == "sourced_lore"
    assert models["SourcedLoreClaim"]["properties"]["sources"]["minItems"] == 1
    for name, field, target in [
        ("SourcedLoreClaim", "sources", "SourceReference"),
        ("ClaimPassageResponse", "references", "ReferencePassagesResponse"),
        ("ReferencePassagesResponse", "passages", "SourcePassage")]:
        prop = models[name]["properties"][field]
        assert prop["type"] == "array"
        assert prop["items"] == {"$ref": f"#/components/schemas/{target}"}
    for name, field, target in [
        ("SourceReference", "canon_tier", "CanonTier"), ("SourceReference", "locator", "SourceLocator"),
        ("SourcePassage", "reference", "SourceReference"),
        ("ReferencePassagesResponse", "reference", "SourceReference"),
        ("ReferencePassagesResponse", "status", "ResolutionStatus")]:
        assert models[name]["properties"][field] == {"$ref": f"#/components/schemas/{target}"}
    for field in ["all_references_registered", "all_references_have_passages"]:
        assert models["ClaimPassageResponse"]["properties"][field]["type"] == "boolean"


@pytest.mark.parametrize(("model", "data"), [
    (api.ReferencePassagesResponse, {"reference": SourceReference(**reference()),
        "status": ResolutionStatus.REGISTRY_MATCH, "passages": [passage()]}),
    (api.ClaimPassageResponse, {"statement": "Original prose", "references": [],
        "all_references_registered": True, "all_references_have_passages": False}),
    (api.LookupUnavailableResponse, {"detail": "Unavailable"}),
])
def test_response_models_require_fields_forbid_extras_and_are_strict(model, data):
    assert model.model_config == {"extra": "forbid", "strict": True}
    assert model.model_validate(data)
    for field in data:
        with pytest.raises(ValidationError):
            model.model_validate({key: value for key, value in data.items() if key != field})
    with pytest.raises(ValidationError):
        model.model_validate(data | {"verified": True})
    field = next(iter(data))
    with pytest.raises(ValidationError):
        model.model_validate(data | {field: 7})


def test_fresh_process_http_without_configuration_or_external_io(tmp_path):
    # Warm up framework discovery and Windows event loops before guarding app imports.
    # Audit hooks are regression checks, not an OS sandbox.
    code = textwrap.dedent('''
        import asyncio
        import os
        import sys
        import pydantic
        from fastapi.testclient import TestClient

        class FrameworkWarmup(pydantic.BaseModel):
            pass

        loops = [asyncio.new_event_loop() for _ in range(2)]

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
        from pensieve_api.main import app, create_app
        assert "pensieve_api.domain.source_catalog" not in sys.modules
        assert "pensieve_api.domain.catalog_governance" not in sys.modules
        ref = {"source_id": "synthetic", "title": "The Paper Atlas", "canon_tier": "book",
               "locator": {"kind": "chapter", "reference": "A"}}
        claim = {"kind": "sourced_lore", "statement": "An original observation.", "sources": [ref]}
        with TestClient(app, backend_options={"loop_factory": lambda: loops[0]}) as client:
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok", "service": "pensieve-api"}
            response = client.post("/api/v1/claims/passages/lookup", json=claim)
            assert response.status_code == 503
            assert response.json() == {"detail": "Passage lookup is not configured"}
        from pensieve_api.domain.source_catalog import SourceCatalog
        from pensieve_api.domain.source_passages import SourcePassage, PassageStore
        catalog = SourceCatalog(schema_version=1, catalog_id="synthetic-v1", entries=[{
            "source": {"source_id": ref["source_id"], "title": ref["title"], "canon_tier": "book",
                       "locators": [ref["locator"]]},
            "curation_status": "metadata_reviewed", "curation_note": "Original invented metadata.",
        }])
        record = SourcePassage(kind="source_passage", passage_id="one", reference=ref,
                               text="An invented paper lantern glowed.")
        configured = create_app(passage_store=PassageStore(catalog.build_registry(), [record]))
        with TestClient(configured, backend_options={"loop_factory": lambda: loops[1]}) as client:
            response = client.post("/api/v1/claims/passages/lookup", json=claim)
            assert response.status_code == 200
            assert response.json() == {
                "statement": claim["statement"], "references": [{"reference": ref,
                    "status": "REGISTRY_MATCH", "passages": [record.model_dump(mode="json")]}],
                "all_references_registered": True, "all_references_have_passages": True,
            }
    ''')
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code], cwd=tmp_path,
        env={"SystemRoot": os.environ["SystemRoot"]} if "SystemRoot" in os.environ else {},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

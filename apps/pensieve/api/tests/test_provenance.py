"""Synthetic attribution metadata only; no real sources or external I/O."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pensieve_api.domain.provenance import (
    CanonTier,
    GeneratedRoleplay,
    SourceLocator,
    SourceReference,
    SourcedLoreClaim,
)


def source_data():
    return {
        "source_id": "synthetic-atlas",
        "title": "The Imaginary Lantern Atlas",
        "canon_tier": "book",
        "locator": {"kind": "chapter", "reference": "3"},
    }


def claim_data():
    return {
        "kind": "sourced_lore",
        "statement": "The imaginary atlas describes a lantern garden.",
        "sources": [source_data()],
    }


def roleplay_data():
    return {
        "kind": "generated_roleplay",
        "content": "I raise a paper lantern beside the imaginary garden gate.",
    }


@pytest.mark.parametrize("tier", ["book", "film", "expanded_publication"])
def test_source_tiers_and_nested_construction(tier):
    data = source_data() | {"canon_tier": tier}
    source = SourceReference.model_validate(data)
    assert source.canon_tier is CanonTier(tier)
    assert source.locator == SourceLocator(kind="chapter", reference="3")
    assert SourceReference(**(data | {"canon_tier": CanonTier(tier)})) == source
    assert SourceReference.model_validate_json(source.model_dump_json()) == source


@pytest.mark.parametrize("kind", ["chapter", "scene", "section", "other"])
def test_locator_kinds(kind):
    assert SourceLocator(kind=kind, reference="  synthetic location  ").reference == "synthetic location"


@pytest.mark.parametrize("tier", ["unknown", "BOOK", " book ", 1, True, None, b"book"])
def test_invalid_tier(tier):
    with pytest.raises(ValidationError):
        SourceReference.model_validate(source_data() | {"canon_tier": tier})


MODEL_CASES = [
    (SourceLocator, lambda: source_data()["locator"]),
    (SourceReference, source_data),
    (SourcedLoreClaim, claim_data),
    (GeneratedRoleplay, roleplay_data),
]


@pytest.mark.parametrize(("model", "factory"), MODEL_CASES)
def test_all_fields_required_and_unknown_fields_forbidden(model, factory):
    data = factory()
    for field in data:
        with pytest.raises(ValidationError):
            model.model_validate({key: value for key, value in data.items() if key != field})
    with pytest.raises(ValidationError):
        model.model_validate(data | {"verified": True})


@pytest.mark.parametrize(("model", "factory", "field"), [
    (SourceLocator, lambda: source_data()["locator"], "reference"),
    (SourceReference, source_data, "source_id"),
    (SourceReference, source_data, "title"),
    (SourcedLoreClaim, claim_data, "statement"),
    (GeneratedRoleplay, roleplay_data, "content"),
])
@pytest.mark.parametrize("value", ["", " \t\r\n ", None, 42, True, b"text", [], {}])
def test_text_is_nonblank_and_strict(model, factory, field, value):
    with pytest.raises(ValidationError):
        model.model_validate(factory() | {field: value})


@pytest.mark.parametrize(("model", "factory", "field"), [
    (SourceReference, source_data, "source_id"),
    (SourceReference, source_data, "title"),
    (SourcedLoreClaim, claim_data, "statement"),
    (GeneratedRoleplay, roleplay_data, "content"),
])
def test_text_trimming(model, factory, field):
    data = factory()
    assert getattr(model.model_validate(data | {field: f"  {data[field]}  "}), field) == data[field]


@pytest.mark.parametrize("sources", [[], None, {}, "source", [None], ["source"], [1], ()])
def test_lore_requires_nonempty_source_list(sources):
    with pytest.raises(ValidationError):
        SourcedLoreClaim.model_validate(claim_data() | {"sources": sources})


@pytest.mark.parametrize("locator", [None, "chapter 3", {}, {"kind": "page", "reference": "3"}])
def test_invalid_locator(locator):
    with pytest.raises(ValidationError):
        SourceReference.model_validate(source_data() | {"locator": locator})


def test_nested_invalid_and_unexpected_fields_are_rejected():
    for change in ({"title": " "}, {"authentic": True}, {"locator": {"kind": "chapter", "reference": "3", "url": "synthetic"}}):
        with pytest.raises(ValidationError):
            SourcedLoreClaim.model_validate(claim_data() | {"sources": [source_data() | change]})


@pytest.mark.parametrize(("model", "factory"), MODEL_CASES)
def test_json_serialization_round_trip(model, factory):
    data = factory()
    value = model.model_validate(data)
    assert value.model_dump(mode="json") == data
    assert json.loads(value.model_dump_json()) == data
    assert model.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize(("model", "factory", "kind"), [
    (SourcedLoreClaim, claim_data, "generated_roleplay"),
    (GeneratedRoleplay, roleplay_data, "sourced_lore"),
    (SourcedLoreClaim, claim_data, "unknown"),
    (GeneratedRoleplay, roleplay_data, None),
])
def test_incorrect_content_kind(model, factory, kind):
    with pytest.raises(ValidationError):
        model.model_validate(factory() | {"kind": kind})


def test_roleplay_and_sourced_lore_remain_separate():
    for model, data in [
        (SourcedLoreClaim, roleplay_data()),
        (GeneratedRoleplay, claim_data()),
        (GeneratedRoleplay, roleplay_data() | {"sources": [source_data()]}),
        (GeneratedRoleplay, roleplay_data() | {"statement": "An invented claim."}),
        (SourcedLoreClaim, claim_data() | {"content": "Invented roleplay."}),
    ]:
        with pytest.raises(ValidationError):
            model.model_validate(data)


def test_domain_contracts_do_not_change_health_or_openapi():
    from pensieve_api.main import app

    with TestClient(app) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok", "service": "pensieve-api"}
        schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/api/v1/health"}
    assert set(schema["components"]["schemas"]) == {"HealthResponse"}

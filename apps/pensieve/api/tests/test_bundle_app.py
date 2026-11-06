"""Explicit file startup with original synthetic data and no live server binding."""

from copy import deepcopy
import io
import json
import os
from pathlib import Path, PurePath
import subprocess
import sys
import textwrap
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from pensieve_api import bundle_app
from pensieve_api.domain.passage_bundle import PassageBundle
from pensieve_api.main import app as default_app


EXAMPLE = Path(__file__).parents[1] / "examples/synthetic_passage_bundle.v1.json"
URL = "/api/v1/claims/passages/lookup"


@pytest.fixture
def data():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


@pytest.fixture
def bundle_file(tmp_path, data):
    path = tmp_path / "lantern café bundle.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def claim(data):
    a = deepcopy(data["passages"][0]["reference"])
    b = a | {"locator": {"kind": "chapter", "reference": "B"}}
    return {"kind": "sourced_lore", "statement": "An original fictional observation.", "sources": [a, b, a]}


def assert_lookup(application, data):
    request = claim(data)
    with TestClient(application) as client:
        response = client.post(URL, json=request)
    assert response.status_code == 200
    expected = {"statement": request["statement"], "references": [
        {"reference": ref, "status": "REGISTRY_MATCH", "passages": passages}
        for ref, passages in zip(request["sources"], [data["passages"], [], data["passages"]])],
        "all_references_registered": True, "all_references_have_passages": False}
    assert response.json() == expected
    assert [len(r["passages"]) for r in response.json()["references"]] == [2, 0, 2]
    return response.json()


@pytest.mark.parametrize("as_string", [False, True])
@pytest.mark.parametrize("relative", [False, True])
@pytest.mark.parametrize("bom", [False, True])
def test_path_forms_unicode_and_utf8_bom(bundle_file, data, monkeypatch, as_string, relative, bom):
    if bom:
        bundle_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8-sig")
    monkeypatch.chdir(bundle_file.parent)
    path = Path(bundle_file.name) if relative else bundle_file
    application = bundle_app.create_app_from_bundle_file(str(path) if as_string else path)
    assert isinstance(application, FastAPI)
    assert_lookup(application, data)


@pytest.mark.parametrize(("path", "error"), [
    (None, TypeError), (b"bundle.json", TypeError), (True, TypeError), (1, TypeError),
    (1.5, TypeError), ({}, TypeError), ([], TypeError), (io.StringIO("{}"), TypeError),
    (PurePath("bundle.json"), TypeError), ("", ValueError), (" \t\n", ValueError),
])
def test_invalid_paths_fail_before_io(monkeypatch, path, error):
    read = Mock(side_effect=AssertionError("Unexpected file read"))
    monkeypatch.setattr(Path, "read_text", read)
    with pytest.raises(error):
        bundle_app.create_app_from_bundle_file(path)
    read.assert_not_called()


@pytest.mark.parametrize("literal", [" bundle.json ", "$BUNDLE.json", "%BUNDLE%.json", "~/bundle.json",
                                     "https://example.invalid/bundle.json"])
def test_literal_paths_are_passed_without_expansion(monkeypatch, data, literal):
    monkeypatch.setenv("BUNDLE", "some-other-file")
    seen = []
    def read(path, *, encoding):
        seen.append((path, encoding))
        return json.dumps(data)
    monkeypatch.setattr(Path, "read_text", read)
    assert_lookup(bundle_app.create_app_from_bundle_file(literal), data)
    assert seen == [(Path(literal), "utf-8-sig")]


def test_missing_directory_and_unreadable_propagate(tmp_path, monkeypatch):
    with pytest.raises(FileNotFoundError):
        bundle_app.create_app_from_bundle_file(tmp_path / "missing.json")
    with pytest.raises(OSError):
        bundle_app.create_app_from_bundle_file(tmp_path)
    denied = PermissionError("Synthetic access denied")
    read = Mock(side_effect=denied)
    monkeypatch.setattr(Path, "read_text", read)
    with pytest.raises(PermissionError) as caught:
        bundle_app.create_app_from_bundle_file(tmp_path / "denied.json")
    assert caught.value is denied
    read.assert_called_once_with(encoding="utf-8-sig")


BAD_DOCUMENTS = [b"\xff", b"", b" \n", b'{"unfinished":', b"null", b"[]", b"{}"]


@pytest.mark.parametrize("content", BAD_DOCUMENTS)
def test_invalid_files_propagate_without_composition_or_server(tmp_path, monkeypatch, content):
    path = tmp_path / "bad.json"
    path.write_bytes(content)
    compose, run = Mock(), Mock()
    monkeypatch.setattr(bundle_app, "create_app", compose)
    monkeypatch.setattr(bundle_app.uvicorn, "run", run)
    with pytest.raises(UnicodeDecodeError if content == b"\xff" else ValidationError):
        bundle_app.create_app_from_bundle_file(path)
    compose.assert_not_called()
    run.assert_not_called()


@pytest.mark.parametrize("change", ["extra", "version", "nested_extra", "duplicate", "unknown", "proposal", "mismatch", "locator"])
def test_invalid_document_and_store_contracts(bundle_file, data, monkeypatch, change):
    if change == "extra":
        data["verified"] = True
    elif change == "version":
        data["schema_version"] = True
    elif change == "nested_extra":
        data["passages"][1]["reference"]["verified"] = True
    elif change == "duplicate":
        data["passages"][1]["passage_id"] = " arrival "
    elif change in {"unknown", "proposal"}:
        data["passages"][1]["reference"]["source_id"] = "missing" if change == "unknown" else "synthetic-film"
    elif change == "mismatch":
        data["passages"][1]["reference"]["title"] = "Changed title"
    else:
        data["passages"][1]["reference"]["locator"]["reference"] = "Z"
    bundle_file.write_text(json.dumps(data), encoding="utf-8")
    compose = Mock(side_effect=AssertionError("Unexpected app construction"))
    monkeypatch.setattr(bundle_app, "create_app", compose)
    with pytest.raises(ValidationError if change in {"extra", "version", "nested_extra"} else ValueError):
        bundle_app.create_app_from_bundle_file(bundle_file)
    compose.assert_not_called()


def test_single_read_and_public_delegation_order(monkeypatch, bundle_file, data):
    events = []
    original_read = Path.read_text
    original_parse = PassageBundle.model_validate_json
    original_build = PassageBundle.build_store
    original_compose = bundle_app.create_app
    def read(path, *, encoding):
        events.append(("read", path, encoding))
        return original_read(path, encoding=encoding)
    def parse(text):
        events.append(("parse", text))
        return original_parse(text)
    def build(bundle):
        events.append(("build", bundle))
        return original_build(bundle)
    def compose(*, passage_store):
        events.append(("compose", passage_store))
        return original_compose(passage_store=passage_store)
    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(PassageBundle, "model_validate_json", parse)
    monkeypatch.setattr(PassageBundle, "build_store", build)
    monkeypatch.setattr(bundle_app, "create_app", compose)
    application = bundle_app.create_app_from_bundle_file(bundle_file)
    assert [e[0] for e in events] == ["read", "parse", "build", "compose"]
    assert events[0] == ("read", bundle_file, "utf-8-sig")
    assert json.loads(events[1][1]) == data
    assert events[2][1].model_dump(mode="json") == data
    assert_lookup(application, data)
    assert_lookup(application, data)
    assert len(events) == 4


def test_app_snapshots_file_changes_deletion_and_default_independence(bundle_file, data):
    first = bundle_app.create_app_from_bundle_file(bundle_file)
    saved = assert_lookup(first, data)
    saved["references"][0]["passages"][0]["text"] = "Client edit."
    saved["references"][0]["reference"]["title"] = "Client title"
    changed = deepcopy(data)
    changed["passages"][0]["text"] = "An explicitly edited original sentence."
    bundle_file.write_text(json.dumps(changed), encoding="utf-8")
    second = bundle_app.create_app_from_bundle_file(bundle_file)
    assert first is not second
    assert_lookup(first, data)
    assert_lookup(second, changed)
    bundle_file.write_text("{}", encoding="utf-8")
    with pytest.raises(ValidationError):
        bundle_app.create_app_from_bundle_file(bundle_file)
    bundle_file.unlink()
    with pytest.raises(FileNotFoundError):
        bundle_app.create_app_from_bundle_file(bundle_file)
    assert_lookup(first, data)
    assert_lookup(second, changed)
    with TestClient(default_app) as client:
        response = client.post(URL, json=claim(data))
        assert response.status_code == 503
        assert response.json() == {"detail": "Passage lookup is not configured"}


def test_existing_statuses_health_docs_and_entire_openapi(bundle_file, data):
    application = bundle_app.create_app_from_bundle_file(bundle_file)
    a = claim(data)["sources"][0]
    proposal = data["catalog"]["entries"][1]["source"]
    refs = [a | {"source_id": "missing"}, a | {"title": "Wrong"},
            a | {"locator": {"kind": "chapter", "reference": "Z"}},
            {k: proposal[k] for k in ["source_id", "title", "canon_tier"]} | {"locator": proposal["locators"][0]}]
    with TestClient(application) as client, TestClient(default_app) as default:
        response = client.post(URL, json=claim(data) | {"sources": refs})
        assert response.status_code == 200
        assert [r["status"] for r in response.json()["references"]] == [
            "SOURCE_NOT_REGISTERED", "SOURCE_METADATA_MISMATCH", "LOCATOR_NOT_REGISTERED", "SOURCE_NOT_REGISTERED"]
        assert all(r["passages"] == [] for r in response.json()["references"])
        assert response.json()["all_references_registered"] is False
        assert response.json()["all_references_have_passages"] is False
        for path in ["/api/v1/health", "/docs", "/redoc", "/openapi.json"]:
            actual, baseline = client.get(path), default.get(path)
            assert actual.status_code == baseline.status_code == 200
            assert actual.content == baseline.content
        schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/api/v1/health", URL}
    assert not {"PassageBundle", "SourceCatalog", "CatalogEntry"} & set(schema["components"]["schemas"])


@pytest.mark.parametrize("args", [[], ["--port", "8000"], ["--bundle"], ["--bun", "x"],
    ["--bundle", "x", "--host", "0.0.0.0"], ["--bundle", "x", "--reload"],
    *[["--bundle", "x", "--port", port] for port in ["0", "65536", "-1", "1.5", "abc", ""]]])
def test_cli_argument_errors_before_loading(monkeypatch, capsys, args):
    load, run = Mock(), Mock()
    monkeypatch.setattr(bundle_app, "create_app_from_bundle_file", load)
    monkeypatch.setattr(bundle_app.uvicorn, "run", run)
    with pytest.raises(SystemExit) as caught:
        bundle_app.main(args)
    assert caught.value.code == 2
    assert "error:" in capsys.readouterr().err
    load.assert_not_called()
    run.assert_not_called()


def test_cli_help_without_loading(monkeypatch, capsys):
    read, run = Mock(), Mock()
    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(bundle_app.uvicorn, "run", run)
    with pytest.raises(SystemExit) as caught:
        bundle_app.main(["--help"])
    assert caught.value.code == 0
    assert "--bundle PATH" in capsys.readouterr().out
    read.assert_not_called()
    run.assert_not_called()


@pytest.mark.parametrize("port", [None, 1, 65535, 8104])
def test_cli_real_composition_and_runner_boundary(monkeypatch, bundle_file, data, port):
    run = Mock()
    # Only the server runner is replaced; captured apps use real file/domain operations.
    monkeypatch.setattr(bundle_app.uvicorn, "run", run)
    args = ["--bundle", str(bundle_file)] + ([] if port is None else ["--port", str(port)])
    assert bundle_app.main(args) == 0
    run.assert_called_once()
    assert run.call_args.kwargs == {"host": "127.0.0.1", "port": 8000 if port is None else port,
                                    "reload": False, "workers": 1}
    assert_lookup(run.call_args.args[0], data)


@pytest.mark.parametrize("failure", ["missing", "directory", "utf8", "json", "schema", "duplicate", "incompatible", "blank"])
def test_cli_expected_errors_do_not_leak_text(monkeypatch, bundle_file, data, capsys, failure):
    secret_text = "ORIGINAL_SYNTHETIC_TEXT_MUST_NOT_APPEAR"
    data["passages"][0]["text"] = secret_text
    path = str(bundle_file)
    if failure == "missing":
        path = str(bundle_file.parent / "missing")
    elif failure == "directory":
        path = str(bundle_file.parent)
    elif failure == "blank":
        path = " "
    elif failure == "utf8":
        bundle_file.write_bytes(b"\xff" + secret_text.encode())
    elif failure == "json":
        bundle_file.write_text('{"text": "' + secret_text, encoding="utf-8")
    else:
        if failure == "schema":
            data["passages"][1]["text"] = {"secret": secret_text}
        elif failure == "duplicate":
            data["passages"][1]["passage_id"] = " arrival "
        else:
            data["passages"][1]["reference"]["source_id"] = "missing"
        bundle_file.write_text(json.dumps(data), encoding="utf-8")
    run = Mock()
    monkeypatch.setattr(bundle_app.uvicorn, "run", run)
    assert bundle_app.main(["--bundle", path]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "Unable to load bundle:" in output.err
    assert secret_text not in output.err and '"passages"' not in output.err
    run.assert_not_called()


def test_unexpected_factory_and_runner_errors_propagate(monkeypatch, bundle_file):
    error = RuntimeError("Synthetic programming error")
    build = Mock(side_effect=error)
    run = Mock()
    monkeypatch.setattr(PassageBundle, "build_store", build)
    monkeypatch.setattr(bundle_app.uvicorn, "run", run)
    with pytest.raises(RuntimeError) as caught:
        bundle_app.create_app_from_bundle_file(bundle_file)
    assert caught.value is error
    with pytest.raises(RuntimeError) as caught:
        bundle_app.main(["--bundle", str(bundle_file)])
    assert caught.value is error
    run.assert_not_called()
    monkeypatch.undo()
    monkeypatch.setattr(bundle_app.uvicorn, "run", Mock(side_effect=OSError("Synthetic server failure")))
    with pytest.raises(OSError, match="Synthetic server failure"):
        bundle_app.main(["--bundle", str(bundle_file)])


def test_real_module_help_and_successful_entrypoint(tmp_path, bundle_file):
    environment = {"SystemRoot": os.environ["SystemRoot"]} if "SystemRoot" in os.environ else {}
    help_result = subprocess.run([sys.executable, "-I", "-B", "-m", "pensieve_api.bundle_app", "--help"],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30)
    assert help_result.returncode == 0, help_result.stderr
    assert "--bundle PATH" in help_result.stdout and "--port PORT" in help_result.stdout
    code = textwrap.dedent('''
        import runpy
        import sys
        import uvicorn
        from fastapi.testclient import TestClient

        calls = []
        def run(app, **kwargs):
            calls.append(kwargs)
            assert kwargs == dict(host="127.0.0.1", port=8123, reload=False, workers=1)
            with TestClient(app) as client:
                assert client.get("/api/v1/health").status_code == 200
        uvicorn.run = run
        sys.argv = ["pensieve_api.bundle_app", "--bundle", sys.argv[1], "--port", "8123"]
        try:
            runpy.run_module("pensieve_api.bundle_app", run_name="__main__")
        except SystemExit as result:
            assert result.code == 0
        else:
            raise AssertionError("Module did not exit through main")
        assert len(calls) == 1
    ''')
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(bundle_file)],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_fresh_import_and_only_selected_data_read_then_io_free_requests(tmp_path, bundle_file):
    code = textwrap.dedent('''
        import asyncio
        import os
        from pathlib import Path
        import sys
        import pydantic
        import uvicorn
        from fastapi.testclient import TestClient

        class FrameworkWarmup(pydantic.BaseModel):
            pass

        loop = asyncio.new_event_loop()  # Windows creates framework sockets here.
        selected = os.path.normcase(os.path.abspath(sys.argv[1]))
        reads = []
        allow_selected = False
        def reject_external_io(event, args):
            if event in {"socket.connect", "socket.getaddrinfo", "socket.bind", "sqlite3.connect",
                         "os.mkdir", "os.remove", "os.rename", "subprocess.Popen"}:
                raise AssertionError(f"Unexpected external I/O: {event}")
            if event == "open":
                path, mode, flags = args
                if (mode and any(c in mode for c in "wax+")) or flags & (
                    os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
                ):
                    raise AssertionError("Unexpected filesystem write")
                if str(path).endswith((".py", ".pyc", ".pyd", ".so")):
                    return
                if allow_selected and os.path.normcase(os.path.abspath(path)) == selected:
                    reads.append(path)
                    return
                raise AssertionError(f"Unexpected data read: {path}")

        def no_server(*args, **kwargs):
            raise AssertionError("Unexpected server startup")
        uvicorn.run = no_server
        sys.addaudithook(reject_external_io)
        from pensieve_api.bundle_app import create_app_from_bundle_file
        assert reads == []
        allow_selected = True
        application = create_app_from_bundle_file(Path(sys.argv[1]))
        allow_selected = False
        assert len(reads) == 1
        with TestClient(application, backend_options={"loop_factory": lambda: loop}) as client:
            ref = {"source_id": "synthetic-atlas", "title": "The Folded Lantern Atlas",
                   "canon_tier": "book", "locator": {"kind": "chapter", "reference": "A"}}
            for _ in range(2):
                response = client.post("/api/v1/claims/passages/lookup", json={
                    "kind": "sourced_lore", "statement": "Original observation.", "sources": [ref]})
                assert response.status_code == 200
                assert len(response.json()["references"][0]["passages"]) == 2
                assert client.get("/api/v1/health").status_code == 200
        assert len(reads) == 1
    ''')
    # Audit hooks are regression checks, not an OS sandbox.
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(bundle_file)],
        cwd=tmp_path, env={"SystemRoot": os.environ["SystemRoot"]} if "SystemRoot" in os.environ else {},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr

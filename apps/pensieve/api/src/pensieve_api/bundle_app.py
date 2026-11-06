"""Explicit local bundle composition and loopback startup; no import-time loading."""

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from fastapi import FastAPI
from pydantic import ValidationError
import uvicorn

from pensieve_api.domain.passage_bundle import PassageBundle
from pensieve_api.main import create_app


def create_app_from_bundle_file(path: str | Path) -> FastAPI:
    """Read one literal local path and build an independent application snapshot.

    File, decoding, validation and store construction errors propagate. This uses
    direct bundle construction, without guarded catalog revision adoption.
    """
    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a str or pathlib.Path")
    if isinstance(path, str) and not path.strip():
        raise ValueError("path must not be blank")
    text = Path(path).read_text(encoding="utf-8-sig")
    bundle = PassageBundle.model_validate_json(text)
    store = bundle.build_store()
    return create_app(passage_store=store)


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("port must be an integer from 1 through 65535") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be an integer from 1 through 65535")
    return port


def main(argv: Sequence[str] | None = None) -> int:
    """Validate local startup arguments, load once, then run the configured app."""
    parser = argparse.ArgumentParser(description="Serve an explicitly selected local passage bundle.",
                                     allow_abbrev=False)
    parser.add_argument("--bundle", required=True, metavar="PATH", help="local PassageBundle JSON file")
    parser.add_argument("--port", type=_port, default=8000, metavar="PORT",
                        help="loopback port, 1 through 65535 (default: 8000)")
    args = parser.parse_args(argv)
    try:
        application = create_app_from_bundle_file(args.bundle)
    except OSError:
        print("Unable to load bundle: local file could not be read.", file=sys.stderr)
        return 1
    except UnicodeError:
        print("Unable to load bundle: file must contain UTF-8 text.", file=sys.stderr)
        return 1
    except ValidationError:
        print("Unable to load bundle: invalid JSON or bundle structure.", file=sys.stderr)
        return 1
    except ValueError:
        print("Unable to load bundle: blank path or incompatible passage records.", file=sys.stderr)
        return 1
    uvicorn.run(application, host="127.0.0.1", port=args.port, reload=False, workers=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

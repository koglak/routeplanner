"""Command line for the museum DB.

    python -m museumdb.cli get <slug>           # stored JSON; exit 1 if unknown
    python -m museumdb.cli stale <slug>         # stale fields as JSON
    python -m museumdb.cli save <slug> < draft.json
    python -m museumdb.cli table <slug>
    python -m museumdb.cli serve [--port 8765]  # local read-only web UI
    python -m museumdb.cli status <slug>        # {"state": missing|fresh|stale, "stale_fields": [...]}

Network (Wikidata / OpenStreetMap):
    python -m museumdb.cli resolve <city name>  # candidate cities with slug and country code
    python -m museumdb.cli candidates <city QID>
    python -m museumdb.cli lookup <museum name>
    python -m museumdb.cli scaffold <slug> <city QID> <museum QID>...   # draft skeleton
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from museumdb import wikidata
from museumdb.scaffold import build_draft
from museumdb.store import DEFAULT_MAX_AGE_DAYS, CityNotFound, JsonStore
from museumdb.table import render_table
from museumdb.validation import ValidationError, check_slug, parse_city
from museumdb.wikidata import QID_RE, FetchError

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_INVALID = 2
EXIT_NETWORK = 3


def main(argv: list[str] | None = None, fetch: wikidata.Fetch = wikidata.http_fetch) -> int:
    args = _parser().parse_args(argv)
    args.fetch = fetch
    store = JsonStore(args.root)
    try:
        if "slug" in args:
            check_slug(args.slug)
        for qid in [getattr(args, "city_qid", None), *getattr(args, "museum_qids", [])]:
            if qid is not None and not QID_RE.fullmatch(qid):
                raise ValidationError(f"invalid Wikidata id {qid!r}: expected e.g. 'Q220'")
        return _COMMANDS[args.command](store, args)
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INVALID
    except FetchError as e:
        print(f"error: network: {e}", file=sys.stderr)
        return EXIT_NETWORK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="museumdb")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("MUSEUMDB_ROOT", "data")),
        help="data directory (default: $MUSEUMDB_ROOT or ./data)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("get", "print the stored city JSON"),
        ("stale", "list planning/volatile fields that need refreshing"),
        ("save", "validate, merge and store a draft read from stdin"),
        ("table", "print a summary table"),
        ("status", "missing / fresh / stale, with the stale fields"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("slug")
        if name in ("stale", "status"):
            command.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    sub.add_parser("resolve", help="find a city on Wikidata").add_argument("name")
    sub.add_parser("candidates", help="museums in a city, by Wikipedia sitelinks").add_argument("city_qid")
    sub.add_parser("lookup", help="find a museum on Wikidata by name").add_argument("name")
    scaffold = sub.add_parser("scaffold", help="draft with identity fields for museums in popularity order")
    scaffold.add_argument("slug")
    scaffold.add_argument("city_qid")
    scaffold.add_argument("museum_qids", nargs="+")
    serve = sub.add_parser("serve", help="run the local read-only web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def _get(store: JsonStore, args: argparse.Namespace) -> int:
    city = store.get_city(args.slug)
    if city is None:
        return _not_found(args.slug)
    _print_json(city.to_dict())
    return EXIT_OK


def _stale(store: JsonStore, args: argparse.Namespace) -> int:
    try:
        fields = store.stale_fields(args.slug, args.max_age_days)
    except CityNotFound:
        return _not_found(args.slug)
    _print_json([{"museum_id": museum_id, "field": field} for museum_id, field in fields])
    return EXIT_OK


def _save(store: JsonStore, args: argparse.Namespace) -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        raise ValidationError(f"draft is not valid JSON: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("city"), dict):
        raise ValidationError("draft must be a JSON object with a 'city' object")
    draft_slug = data["city"].setdefault("slug", args.slug)
    if draft_slug != args.slug:
        raise ValidationError(f"draft slug {draft_slug!r} does not match {args.slug!r}")
    store.save_city(parse_city(data))
    saved = store.get_city(args.slug)
    print(f"saved {args.slug}: {len(saved.museums)} museums")
    return EXIT_OK


def _table(store: JsonStore, args: argparse.Namespace) -> int:
    city = store.get_city(args.slug)
    if city is None:
        return _not_found(args.slug)
    print(render_table(city))
    return EXIT_OK


def _serve(store: JsonStore, args: argparse.Namespace) -> int:
    from museumdb.web import make_server

    server = make_server(store, args.host, args.port)
    print(f"museumdb UI: http://{args.host}:{server.server_address[1]}  (data: {args.root})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return EXIT_OK


def _status(store: JsonStore, args: argparse.Namespace) -> int:
    try:
        fields = store.stale_fields(args.slug, args.max_age_days)
    except CityNotFound:
        _print_json({"state": "missing", "stale_fields": []})
        return EXIT_OK
    stale = [{"museum_id": museum_id, "field": field} for museum_id, field in fields]
    _print_json({"state": "stale" if stale else "fresh", "stale_fields": stale})
    return EXIT_OK


def _resolve(store: JsonStore, args: argparse.Namespace) -> int:
    _print_json(wikidata.resolve_city(args.name, args.fetch))
    return EXIT_OK


def _candidates(store: JsonStore, args: argparse.Namespace) -> int:
    _print_json(wikidata.museum_candidates(args.city_qid, args.fetch))
    return EXIT_OK


def _lookup(store: JsonStore, args: argparse.Namespace) -> int:
    _print_json(wikidata.lookup_museum(args.name, args.fetch))
    return EXIT_OK


def _scaffold(store: JsonStore, args: argparse.Namespace) -> int:
    try:
        city = wikidata.city_details(args.city_qid, args.fetch)
    except LookupError as e:
        raise ValidationError(str(e)) from e
    museums = wikidata.museum_details(args.museum_qids, args.fetch)
    missing = [q for q in args.museum_qids if q not in {m["id"] for m in museums}]
    if missing:
        raise ValidationError(f"no Wikidata item for {', '.join(missing)}")
    try:
        hours = wikidata.osm_hours(museums, args.fetch)
    except FetchError as e:
        print(f"warning: OSM opening hours skipped: {e}", file=sys.stderr)
        hours = {}
    _print_json(build_draft(args.slug, city, museums, hours, date.today()))
    return EXIT_OK


def _not_found(slug: str) -> int:
    print(f"error: no record for {slug!r}", file=sys.stderr)
    return EXIT_NOT_FOUND


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


_COMMANDS = {
    "get": _get, "stale": _stale, "save": _save, "table": _table, "serve": _serve, "status": _status,
    "resolve": _resolve, "candidates": _candidates, "lookup": _lookup, "scaffold": _scaffold,
}

if __name__ == "__main__":
    sys.exit(main())

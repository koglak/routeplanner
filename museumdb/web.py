"""Read-only local web UI for the museum DB (stdlib only).

    python -m museumdb.cli serve [--port 8765]

GET /api/cities         -> index entries
GET /api/cities/<slug>  -> stored city JSON
GET /<file>             -> static files from museumdb/web_static
"""
from __future__ import annotations

import json
import mimetypes
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from museumdb.store import Store
from museumdb.validation import ValidationError

STATIC_DIR = Path(__file__).parent / "web_static"
CITY_PREFIX = "/api/cities/"


def make_server(store: Store, host: str, port: int) -> ThreadingHTTPServer:
    class Handler(_Handler):
        pass

    Handler.store = store
    return ThreadingHTTPServer((host, port), Handler)


class _Handler(BaseHTTPRequestHandler):
    store: Store

    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path == "/api/cities":
            self._json(HTTPStatus.OK, [asdict(e) for e in self.store.list_cities()])
        elif path.startswith(CITY_PREFIX):
            self._city(path[len(CITY_PREFIX):])
        else:
            self._static(path)

    def _city(self, slug: str) -> None:
        try:
            city = self.store.get_city(slug)
        except ValidationError as e:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
            return
        if city is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": f"no record for {slug!r}"})
        else:
            self._json(HTTPStatus.OK, city.to_dict())

    def _static(self, path: str) -> None:
        name = "index.html" if path == "/" else path.lstrip("/")
        target = (STATIC_DIR / name).resolve()
        if target.parent != STATIC_DIR.resolve() or not target.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send(HTTPStatus.OK, f"{ctype}; charset=utf-8", target.read_bytes())

    def _json(self, status: HTTPStatus, data: object) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(status, "application/json; charset=utf-8", body)

    def _send(self, status: HTTPStatus, ctype: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass

import json
import threading
import urllib.error
import urllib.request

import pytest

from museumdb.store import JsonStore
from museumdb.validation import parse_city
from museumdb.web import make_server


@pytest.fixture
def base_url(tmp_path, rome_dict):
    store = JsonStore(tmp_path)
    store.save_city(parse_city(rome_dict))
    server = make_server(store, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def fetch(url):
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, resp.headers.get("Content-Type"), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()


def test_lists_cities(base_url):
    status, ctype, body = fetch(f"{base_url}/api/cities")
    assert status == 200 and ctype.startswith("application/json")
    assert [c["slug"] for c in json.loads(body)] == ["rome"]


def test_gets_city(base_url, rome_dict):
    status, _, body = fetch(f"{base_url}/api/cities/rome")
    assert status == 200 and json.loads(body) == rome_dict


def test_unknown_city_is_404(base_url):
    status, _, body = fetch(f"{base_url}/api/cities/paris")
    assert status == 404 and "paris" in json.loads(body)["error"]


def test_invalid_slug_is_400(base_url):
    status, _, _ = fetch(f"{base_url}/api/cities/..%2Findex")
    assert status == 400


def test_serves_app_shell(base_url):
    status, ctype, body = fetch(f"{base_url}/")
    assert status == 200 and ctype.startswith("text/html") and b"app.js" in body
    status, ctype, _ = fetch(f"{base_url}/app.js")
    assert status == 200 and "javascript" in ctype


def test_static_traversal_is_404(base_url):
    status, _, _ = fetch(f"{base_url}/..%2Fstore.py")
    assert status == 404

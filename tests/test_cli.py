import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from museumdb.cli import main

REPO = Path(__file__).resolve().parents[1]
FIELDS = ("planning.busiest", "planning.queue_min", "planning.advance_ticket", "volatile.price", "volatile.hours")


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    def _run(*argv, stdin=""):
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
        code = main(["--root", str(tmp_path), *argv])
        out, err = capsys.readouterr()
        return code, out, err

    return _run


def test_get_unknown_city_exits_1(run):
    code, out, err = run("get", "rome")
    assert code == 1 and out == "" and "rome" in err


def test_save_then_get(run, rome_dict):
    code, out, _ = run("save", "rome", stdin=json.dumps(rome_dict))
    assert code == 0 and out.strip() == "saved rome: 2 museums"
    code, out, _ = run("get", "rome")
    assert code == 0 and json.loads(out) == rome_dict


def test_save_fills_missing_slug(run, rome_dict):
    del rome_dict["city"]["slug"]
    assert run("save", "rome", stdin=json.dumps(rome_dict))[0] == 0
    assert json.loads(run("get", "rome")[1])["city"]["slug"] == "rome"


def test_save_rejects_slug_mismatch(run, rome_dict, tmp_path):
    code, _, err = run("save", "paris", stdin=json.dumps(rome_dict))
    assert code == 2 and "does not match" in err
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("stdin", ["", "{oops", "[]", '{"city": "rome"}'])
def test_save_rejects_malformed_input(run, tmp_path, stdin):
    code, _, err = run("save", "rome", stdin=stdin)
    assert code == 2 and err.startswith("error:")
    assert list(tmp_path.iterdir()) == []


def test_save_rejects_schema_violation(run, rome_dict, tmp_path):
    rome_dict["museums"][0]["duration"]["signals"][0]["source"] = "yelp"
    code, _, err = run("save", "rome", stdin=json.dumps(rome_dict))
    assert code == 2 and "yelp" in err
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("command", ["get", "stale", "save", "table"])
def test_bad_slug_exits_2(run, tmp_path, command):
    code, _, err = run(command, "../etc")
    assert code == 2 and "invalid slug" in err
    assert list(tmp_path.iterdir()) == []


def test_stale_lists_never_checked_fields(run, rome_dict):
    run("save", "rome", stdin=json.dumps(rome_dict))
    code, out, _ = run("stale", "rome", "--max-age-days", "100000")
    assert code == 0
    assert json.loads(out) == [{"museum_id": "Q999001", "field": f} for f in FIELDS]


def test_stale_unknown_city_exits_1(run):
    assert run("stale", "rome")[0] == 1


def test_table(run, rome_dict):
    run("save", "rome", stdin=json.dumps(rome_dict))
    code, out, _ = run("table", "rome")
    assert code == 0
    assert out.splitlines()[0] == "Rome — 2 müze (1 yüksek, 1 orta, 0 düşük güven)"


def test_table_unknown_city_exits_1(run):
    assert run("table", "rome")[0] == 1


def test_corrupt_record_exits_2(run, tmp_path):
    (tmp_path / "cities").mkdir()
    (tmp_path / "cities" / "rome.json").write_text("{not json", encoding="utf-8")
    code, _, err = run("get", "rome")
    assert code == 2 and "invalid JSON" in err


def test_module_entry_point(tmp_path, rome_dict):
    env = {**os.environ, "PYTHONUTF8": "1"}
    base = [sys.executable, "-m", "museumdb.cli", "--root", str(tmp_path)]
    saved = subprocess.run([*base, "save", "rome"], input=json.dumps(rome_dict), capture_output=True,
                           text=True, encoding="utf-8", cwd=REPO, env=env)
    assert saved.returncode == 0, saved.stderr
    table = subprocess.run([*base, "table", "rome"], capture_output=True, text=True, encoding="utf-8",
                           cwd=REPO, env=env)
    assert table.returncode == 0 and "Vatican Museums" in table.stdout


class NetFetch:
    """Fake network: Wikidata search, SPARQL and Overpass answers keyed by host."""

    def __init__(self, fail=False):
        self.fail = fail

    def __call__(self, url):
        from museumdb.wikidata import FetchError

        if self.fail:
            raise FetchError("connection refused")
        if "overpass-api.de" in url:
            return {"elements": []}
        if "www.wikidata.org" in url and "Museum" in url:
            return {"search": [{"id": "Q182955", "label": "Vatican Museums", "description": "art museum"}]}
        if "www.wikidata.org" in url:
            return {"search": [{"id": "Q220", "label": "Rome", "description": "capital city of Italy"}]}
        if "%3Fitem" in url:
            rows = [{"item": {"value": "http://www.wikidata.org/entity/Q220"}, "itemLabel": {"value": "Rome"},
                     "iso": {"value": "IT"}, "settlement": {"value": "true"}}]
        else:
            rows = [{"m": {"value": "http://www.wikidata.org/entity/Q182955"},
                     "mLabel": {"value": "Vatican Museums"}, "coord": {"value": "Point(12.45 41.9)"},
                     "sitelinks": {"value": "80"}}]
        return {"results": {"bindings": rows}}


@pytest.fixture
def net(tmp_path, capsys):
    def _run(*argv, fail=False):
        code = main(["--root", str(tmp_path), *argv], fetch=NetFetch(fail))
        out, err = capsys.readouterr()
        return code, out, err

    return _run


def test_resolve(net):
    code, out, _ = net("resolve", "Rome")
    assert code == 0
    assert json.loads(out) == [{"qid": "Q220", "name": "Rome", "description": "capital city of Italy",
                                "slug": "rome", "country": "IT"}]


def test_candidates(net):
    code, out, _ = net("candidates", "Q220")
    assert code == 0 and json.loads(out)[0]["coords"] == [41.9, 12.45]


def test_lookup(net):
    code, out, _ = net("lookup", "Vatican Museums")
    assert code == 0 and json.loads(out)[0]["id"] == "Q182955"


def test_scaffold_output_can_be_saved(net, run):
    code, out, _ = net("scaffold", "rome", "Q220", "Q182955")
    assert code == 0
    assert json.loads(out)["museums"][0]["id"] == "Q182955"
    assert run("save", "rome", stdin=out)[0] == 0


def test_scaffold_rejects_unknown_museum_id(net):
    code, _, err = net("scaffold", "rome", "Q220", "Q182955", "Q404")
    assert code == 2 and "Q404" in err


@pytest.mark.parametrize("argv", [("candidates", "rome"), ("scaffold", "rome", "Q220", "osm:way/1")])
def test_bad_qid_exits_2(net, argv):
    code, _, err = net(*argv)
    assert code == 2 and "invalid Wikidata id" in err


def test_network_failure_exits_3(net):
    code, _, err = net("resolve", "Rome", fail=True)
    assert code == 3 and "connection refused" in err


def test_status_missing(run):
    code, out, _ = run("status", "rome")
    assert code == 0 and json.loads(out) == {"state": "missing", "stale_fields": []}


def test_status_fresh(run, rome_dict):
    rome_dict["museums"].pop()
    run("save", "rome", stdin=json.dumps(rome_dict))
    code, out, _ = run("status", "rome", "--max-age-days", "100000")
    assert code == 0 and json.loads(out) == {"state": "fresh", "stale_fields": []}


def test_status_stale_lists_fields(run, rome_dict):
    run("save", "rome", stdin=json.dumps(rome_dict))
    code, out, _ = run("status", "rome", "--max-age-days", "100000")
    assert code == 0
    assert json.loads(out) == {"state": "stale",
                               "stale_fields": [{"museum_id": "Q999001", "field": f} for f in FIELDS]}

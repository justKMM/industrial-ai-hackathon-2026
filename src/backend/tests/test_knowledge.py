import os
import threading
import time

from ai_agent import store
from regcomp import corpus

from backend import knowledge as knowledge_module
from backend import settings
from backend.knowledge import KnowledgeIndex
from conftest import SMALL_REGULATIONS


class CountingParser:
    """Stands for the real parse function and counts the real parses."""

    def __init__(self, real, delay=0.0):
        self.real, self.calls, self.delay = real, [], delay

    def __call__(self):
        return self.parse

    def parse(self, path, grids=True):
        self.calls.append((path.parent.parent.name, grids))
        time.sleep(self.delay)
        return self.real()(path, grids=grids)


def counting(monkeypatch, delay=0.0) -> CountingParser:
    counter = CountingParser(knowledge_module._ORIGINAL_PARSER, delay)
    monkeypatch.setattr(knowledge_module, "_ORIGINAL_PARSER", counter)
    return counter


def build(index: KnowledgeIndex, force=False):
    assert index.start_build(force=force)
    assert index._done.wait(120)
    return index.status()


def test_the_first_build_parses_every_regulation_once_and_leaves_a_ready_index(tmp_path, small_data, monkeypatch):
    counter = counting(monkeypatch)
    index = KnowledgeIndex(small_data, tmp_path / "index")
    index.install()
    assert index.status()["state"] == "missing" and index.status()["total"] == len(SMALL_REGULATIONS)
    status = build(index)
    assert status["state"] == "ready" and status["regulations"] == 2 and status["problems"] == [] and status["builtAt"]
    assert sorted(name for name, grids in counter.calls) == sorted(corpus.slug(r) for r in SMALL_REGULATIONS)
    assert (tmp_path / "index" / "manifest.json").is_file()
    assert len(list(index.parsed_dir.glob("*.pkl"))) == 2
    assert len(list((tmp_path / "index" / "cards").glob("cards-*.json"))) == 1


def test_the_index_survives_a_restart_and_nothing_is_parsed_again(tmp_path, small_data, monkeypatch):
    build(KnowledgeIndex(small_data, tmp_path / "index"))
    counter = counting(monkeypatch)
    again = KnowledgeIndex(small_data, tmp_path / "index")  # a new process, as far as the files are concerned
    again.install()
    assert again.status()["state"] == "ready"
    again.ensure_started(auto_build=True)  # there is an index: leave it alone
    assert again.status()["state"] == "ready"
    assert len(again.catalog().cards) == 2
    graph = store.RegGraph("UN R42")  # the pipeline's own entry point
    assert len(graph.nodes) > 50
    assert counter.calls == []


def test_ensure_started_builds_only_when_there_is_no_index(tmp_path, small_data):
    index = KnowledgeIndex(small_data, tmp_path / "index")
    index.install()
    index.ensure_started(auto_build=False)
    assert index.status()["state"] == "missing"
    index.ensure_started(auto_build=True)
    assert index._done.wait(120) and index.status()["state"] == "ready"


def test_regraph_reads_the_cache_and_each_run_gets_its_own_object(tmp_path, small_data, monkeypatch):
    counter = counting(monkeypatch)
    index = KnowledgeIndex(small_data, tmp_path / "index")
    index.install()
    first = store.RegGraph("UN R42")
    second = store.RegGraph("UN R42")
    assert counter.calls == [("UN_R42", True)]  # parsed once, with grids, by the first graph
    assert first.doc is not second.doc and first.nodes[5] is not second.nodes[5]
    first.nodes[5].text.append("changed by one run")
    assert second.nodes[5].text != first.nodes[5].text


def test_a_forced_rebuild_parses_everything_again_and_a_normal_one_does_not(tmp_path, small_data, monkeypatch):
    index = KnowledgeIndex(small_data, tmp_path / "index")
    index.install()
    build(index)
    counter = counting(monkeypatch)
    build(index, force=False)
    assert counter.calls == []
    status = build(index, force=True)
    assert len(counter.calls) == 2 and status["state"] == "ready"


def test_a_changed_pdf_makes_the_index_stale_and_a_rebuild_makes_it_ready_again(tmp_path, small_data):
    index = KnowledgeIndex(small_data, tmp_path / "index")
    index.install()
    build(index)
    pdf = corpus.pdf_path(corpus.entry_for("UN R42"), "base")
    stat = pdf.stat()
    os.utime(pdf, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000_000))
    status = index.status()
    assert status["state"] == "stale" and "UN R42" in status["staleReasons"][0]
    assert build(index)["state"] == "ready"


def test_a_new_regulation_makes_the_index_stale_and_a_changed_parser_does_too(tmp_path, small_data, monkeypatch):
    index = KnowledgeIndex(small_data, tmp_path / "index")
    index.install()
    build(index)
    # a third PDF appears on disk
    real = settings.resolve_data_dir()
    entry = corpus.entry_for("UN R43")
    name = entry["versions"][0]["files"][0]["name"]
    (small_data / "UN_R43" / "base").mkdir(parents=True)
    (small_data / "UN_R43" / "base" / name).write_bytes((real / "UN_R43" / "base" / name).read_bytes())
    assert "UN R43" in index.status()["staleReasons"][0]
    monkeypatch.setattr(knowledge_module, "parser_fingerprint", lambda: ("rules", "deadbeef"))
    other = KnowledgeIndex(small_data, tmp_path / "index")
    assert any("parser changed" in reason for reason in other.status()["staleReasons"])


def test_a_parser_change_never_reads_the_old_files_and_a_build_removes_them(tmp_path, small_data, monkeypatch):
    first = KnowledgeIndex(small_data, tmp_path / "index")
    build(first)
    assert first.parsed_dir.is_dir()
    monkeypatch.setattr(knowledge_module, "parser_fingerprint", lambda: ("rules", "deadbeef"))
    other = KnowledgeIndex(small_data, tmp_path / "index")
    assert other.parsed_dir != first.parsed_dir
    counter = counting(monkeypatch)
    other.install()
    store.RegGraph("UN R42")
    assert counter.calls == [("UN_R42", True)]  # the files of the other parser were not used
    assert build(other)["state"] == "ready"
    assert not first.parsed_dir.exists() and other.parsed_dir.is_dir()


def test_old_parser_files_are_deleted_after_a_build(tmp_path, small_data):
    index = KnowledgeIndex(small_data, tmp_path / "index")
    old = index.parsed_dir.parent / "rules-00000000"
    old.mkdir(parents=True)
    (old / "x.pkl").write_bytes(b"x")
    stale_cards = index.cards_dir / "cards-00000000.json"
    stale_cards.parent.mkdir(parents=True)
    stale_cards.write_text("{}")
    build(index)
    assert not old.exists() and not stale_cards.exists()


def test_a_corrupt_cache_file_is_a_miss_not_an_error(tmp_path, small_data, monkeypatch):
    index = KnowledgeIndex(small_data, tmp_path / "index")
    index.install()
    store.RegGraph("UN R42")
    (file,) = index.parsed_dir.glob("*.pkl")
    file.write_bytes(b"not a pickle")
    counter = counting(monkeypatch)
    assert len(store.RegGraph("UN R42").nodes) > 50
    assert counter.calls == [("UN_R42", True)]


def test_two_threads_asking_for_the_same_document_parse_it_once(tmp_path, small_data, monkeypatch):
    counter = counting(monkeypatch, delay=0.3)
    index = KnowledgeIndex(small_data, tmp_path / "index")
    index.install()
    pdf = corpus.pdf_path(corpus.entry_for("UN R42"), "base")
    results = []
    threads = [threading.Thread(target=lambda: results.append(index.parse(pdf))) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(counter.calls) == 1 and len(results) == 4


def test_a_build_without_pdfs_fails_with_a_message_that_says_what_to_do(tmp_path):
    empty = tmp_path / "nothing"
    empty.mkdir()
    index = KnowledgeIndex(empty, tmp_path / "index")
    index.install()
    assert index.status()["state"] == "missing" and "tools/fetch_regulations.py" in index.status()["error"]
    assert index.start_build()
    assert index._done.wait(30)
    status = index.status()
    assert status["state"] == "failed" and "No regulation PDFs" in status["error"]


def test_only_one_build_runs_at_a_time(tmp_path, small_data, monkeypatch):
    release = threading.Event()
    counter = CountingParser(knowledge_module._ORIGINAL_PARSER)
    original = counter.parse

    def slow(path, grids=True):
        release.wait(30)
        return original(path, grids=grids)

    counter.parse = slow  # type: ignore[method-assign]
    monkeypatch.setattr(knowledge_module, "_ORIGINAL_PARSER", counter)
    index = KnowledgeIndex(small_data, tmp_path / "index")
    index.install()
    assert index.start_build()
    assert not index.start_build()  # refused while the first one runs
    assert index.status()["state"] == "building"
    release.set()
    assert index._done.wait(60) and index.status()["state"] == "ready"


def test_the_breadcrumb_of_a_paragraph_names_its_section(tmp_path, small_data):
    index = KnowledgeIndex(small_data, tmp_path / "index")
    index.install()
    paths = index.breadcrumbs("UN R42")
    assert paths and all(" › " in p or p for p in paths.values())
    assert index.breadcrumbs("UN R99999") == {}
    assert index.breadcrumbs("UN R10") == {}  # not in this folder

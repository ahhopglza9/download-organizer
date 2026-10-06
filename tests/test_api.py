from main import Api
from matcher import Result
from memory import Memory


class FakeWindow:
    def __init__(self):
        self.calls = []

    def show(self):
        self.calls.append("show")

    def hide(self):
        self.calls.append("hide")

    def run_js(self, code):
        self.calls.append("js")


class FakeMatcher:
    def search(self, query, top_n=5):
        return [Result(path=r"C:\docs\회계", name="회계", location="docs", score=0.9)]


def make_api(memory=None, chosen=None):
    missing = []
    api = Api(FakeMatcher(), on_folder_missing=lambda: missing.append(True),
              memory=memory, choose_folder=lambda window: chosen)
    window = FakeWindow()
    api.bind_window(window)
    return api, window, missing


def touch(tmp_path, name):
    p = tmp_path / name
    p.write_text("x", encoding="utf-8")
    return str(p)


def test_first_file_shows_window(tmp_path):
    api, window, _ = make_api()
    api.enqueue(touch(tmp_path, "a.pdf"))
    assert api.state() == {"file": "a.pdf", "pending": 0, "id": 1, "settings_open": False}
    assert window.calls == ["js", "show"]


def test_second_file_waits_in_queue(tmp_path):
    api, window, _ = make_api()
    api.enqueue(touch(tmp_path, "a.pdf"))
    api.enqueue(touch(tmp_path, "b.pdf"))
    assert api.state()["file"] == "a.pdf"
    assert api.state()["pending"] == 1
    assert window.calls.count("show") == 1


def test_same_path_is_queued_once(tmp_path):
    api, _, _ = make_api()
    a = touch(tmp_path, "a.pdf")
    api.enqueue(a)
    api.enqueue(a)
    assert api.state()["pending"] == 0


def test_next_file_advances_then_hides(tmp_path):
    api, window, _ = make_api()
    api.enqueue(touch(tmp_path, "a.pdf"))
    api.enqueue(touch(tmp_path, "b.pdf"))
    api.next_file()
    assert api.state() == {"file": "b.pdf", "pending": 0, "id": 2, "settings_open": False}
    api.next_file()
    assert api.state()["file"] is None
    assert window.calls[-1] == "hide"


def test_next_file_skips_deleted_files(tmp_path):
    api, window, _ = make_api()
    api.enqueue(touch(tmp_path, "a.pdf"))
    api.enqueue(touch(tmp_path, "b.pdf"))
    (tmp_path / "b.pdf").unlink()
    api.next_file()
    assert api.state()["file"] is None
    assert window.calls[-1] == "hide"


def test_search_returns_plain_dicts(tmp_path):
    api, _, _ = make_api()
    assert api.search("세금") == [
        {"path": r"C:\docs\회계", "name": "회계", "location": "docs", "score": 0.9, "remembered": False}
    ]


def test_move_success(tmp_path):
    api, _, _ = make_api()
    src = touch(tmp_path, "a.pdf")
    dest = tmp_path / "회계"
    dest.mkdir()
    api.enqueue(src)
    assert api.move(str(dest)) == {"ok": True, "folder": "회계"}
    assert (dest / "a.pdf").exists()


def test_second_move_is_rejected(tmp_path):
    api, _, _ = make_api()
    dest = tmp_path / "회계"
    dest.mkdir()
    api.enqueue(touch(tmp_path, "a.pdf"))
    api.move(str(dest))
    result = api.move(str(dest))
    assert result["ok"] is False
    assert list(dest.iterdir()) == [dest / "a.pdf"]


def test_move_to_missing_folder_reports_and_refreshes(tmp_path):
    api, _, missing = make_api()
    api.enqueue(touch(tmp_path, "a.pdf"))
    result = api.move(str(tmp_path / "없는 폴더"))
    assert result["ok"] is False and result["gone"] is False
    assert "폴더" in result["error"]
    assert missing == [True]
    assert api.state()["file"] == "a.pdf"


def test_move_when_download_disappeared(tmp_path):
    api, _, _ = make_api()
    dest = tmp_path / "회계"
    dest.mkdir()
    api.enqueue(touch(tmp_path, "a.pdf"))
    (tmp_path / "a.pdf").unlink()
    result = api.move(str(dest))
    assert result["ok"] is False and result["gone"] is True


def test_closing_handler_does_not_block_gui_thread():
    import threading
    import time

    from main import make_closing_handler

    release = threading.Event()
    called = threading.Event()

    class SlowApi:
        def is_quitting(self):
            return False

        def is_settings_open(self):
            return False

        def next_file(self, expected_id=None):
            called.set()
            release.wait(2)  # 실제 run_js처럼 GUI 스레드를 기다리는 상황

    start = time.time()
    assert make_closing_handler(SlowApi())() is False
    assert time.time() - start < 0.5
    assert called.wait(1)
    release.set()


def test_stale_next_file_does_not_skip_newly_shown_file(tmp_path):
    api, _, _ = make_api()
    dest = tmp_path / "회계"
    dest.mkdir()
    api.enqueue(touch(tmp_path, "a.pdf"))
    shown_id = api.state()["id"]
    api.move(str(dest))
    api.enqueue(touch(tmp_path, "c.pdf"))  # 옮긴 직후 900ms 사이에 새 다운로드
    api.next_file(shown_id)               # 화면의 늦은 타이머
    assert api.state()["file"] == "c.pdf"


def test_concurrent_enqueue_shows_every_file(tmp_path):
    import threading

    api, _, _ = make_api()
    paths = [touch(tmp_path, f"{i}.pdf") for i in range(20)]
    barrier = threading.Barrier(len(paths))

    def enqueue_together(p):
        barrier.wait()  # 여러 다운로드가 동시에 끝난 상황
        api.enqueue(p)

    threads = [threading.Thread(target=enqueue_together, args=(p,)) for p in paths]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    seen = []
    while api.state()["file"]:
        seen.append(api.state()["file"])
        api.next_file()
    assert sorted(seen) == sorted(f"{i}.pdf" for i in range(20))


def test_new_file_brings_window_to_front_after_showing(tmp_path):
    window = FakeWindow()
    api = Api(FakeMatcher(), bring_front=lambda w: w.calls.append("front"))
    api.bind_window(window)
    api.enqueue(touch(tmp_path, "a.pdf"))
    api.enqueue(touch(tmp_path, "b.pdf"))
    api.next_file()
    assert window.calls == ["js", "show", "front", "js", "js", "show", "front"]


def test_move_remembers_query(tmp_path):
    memory = Memory(str(tmp_path / "memory.json"))
    api, _, _ = make_api(memory=memory)
    dest = tmp_path / "컴퓨터프로그래밍I"
    dest.mkdir()
    api.enqueue(touch(tmp_path, "a.pdf"))
    assert api.move(str(dest), "코딩")["ok"] is True
    assert memory.lookup("코딩") == [(str(dest), 1.0)]


def test_move_without_query_is_not_remembered(tmp_path):
    memory = Memory(str(tmp_path / "memory.json"))
    api, _, _ = make_api(memory=memory)
    dest = tmp_path / "회계"
    dest.mkdir()
    api.enqueue(touch(tmp_path, "a.pdf"))
    api.move(str(dest), "  ")
    assert not (tmp_path / "memory.json").exists()


def test_failed_move_is_not_remembered(tmp_path):
    memory = Memory(str(tmp_path / "memory.json"))
    api, _, _ = make_api(memory=memory)
    api.enqueue(touch(tmp_path, "a.pdf"))
    api.move(str(tmp_path / "없는 폴더"), "코딩")
    assert memory.lookup("코딩") == []


def test_pick_folder_moves_and_remembers(tmp_path):
    memory = Memory(str(tmp_path / "memory.json"))
    dest = tmp_path / "D드라이브 사진"
    dest.mkdir()
    api, _, _ = make_api(memory=memory, chosen=str(dest))
    api.enqueue(touch(tmp_path, "a.jpg"))
    assert api.pick_folder("여행 사진") == {"ok": True, "folder": "D드라이브 사진"}
    assert (dest / "a.jpg").exists()
    assert memory.lookup("여행 사진") == [(str(dest), 1.0)]


def test_pick_folder_cancelled_does_nothing(tmp_path):
    api, _, _ = make_api(chosen=None)
    src = touch(tmp_path, "a.pdf")
    api.enqueue(src)
    assert api.pick_folder("코딩") == {"ok": False, "cancelled": True}
    assert api.state()["file"] == "a.pdf"


def test_closing_is_allowed_when_quitting():
    from main import make_closing_handler

    class QuittingApi:
        def is_quitting(self):
            return True

        def next_file(self, expected_id=None):
            raise AssertionError("끄는 중에는 다음 파일로 넘어가면 안 됩니다")

    assert make_closing_handler(QuittingApi())() is True


def test_quit_marks_api_as_quitting():
    api, _, _ = make_api()
    assert api.is_quitting() is False
    api.quit()
    assert api.is_quitting() is True


def test_logging_goes_to_file_without_console(tmp_path, monkeypatch):
    import sys

    from main import setup_logging

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    log = tmp_path / "app.log"
    setup_logging(str(log))
    print("안녕")
    sys.stdout.flush()
    assert "안녕" in log.read_text(encoding="utf-8")


def make_settings_api(tmp_path, first_run=False, chosen=None):
    saved = []
    root = tmp_path / "문서"
    root.mkdir(parents=True)
    provider = lambda: {"roots": [{"path": str(root), "label": "문서", "checked": True}],
                        "autostart": False, "first_run": first_run}
    memory = Memory(str(tmp_path / "memory.json"))
    api = Api(FakeMatcher(), memory=memory, choose_folder=lambda window: chosen,
              settings_provider=provider, settings_saver=lambda roots, auto: saved.append((roots, auto)))
    window = FakeWindow()
    api.bind_window(window)
    return api, window, saved, str(root), memory


def test_get_settings_includes_memory_count(tmp_path):
    api, _, _, root, memory = make_settings_api(tmp_path)
    memory.remember("코딩", root, now=1)
    data = api.get_settings()
    assert data["memory_count"] == 1
    assert data["roots"][0]["path"] == root


def test_add_root_returns_label_or_none(tmp_path):
    api, _, _, _, _ = make_settings_api(tmp_path, chosen=r"E:\사진 보관")
    assert api.add_root() == {"path": r"E:\사진 보관", "label": "사진 보관"}
    api2, _, _, _, _ = make_settings_api(tmp_path / "2", chosen=None)
    assert api2.add_root() is None


def test_save_settings_requires_a_folder(tmp_path):
    api, _, saved, _, _ = make_settings_api(tmp_path)
    for roots in ([], [str(tmp_path / "없는 폴더")]):
        result = api.save_settings(roots, True)
        assert result["ok"] is False
        assert "폴더" in result["error"]
    assert saved == []


def test_save_settings_saves_and_hides_when_no_file(tmp_path):
    api, window, saved, root, _ = make_settings_api(tmp_path)
    api.open_settings()
    assert api.is_settings_open()
    assert api.save_settings([root], True) == {"ok": True, "has_file": False}
    assert saved == [([root], True)]
    assert window.calls[-1] == "hide"
    assert not api.is_settings_open()


def test_save_settings_returns_to_waiting_file(tmp_path):
    api, window, _, root, _ = make_settings_api(tmp_path)
    api.enqueue(touch(tmp_path, "a.pdf"))
    api.open_settings()
    assert api.save_settings([root], False) == {"ok": True, "has_file": True}
    assert window.calls[-1] != "hide"


def test_window_stays_while_settings_open(tmp_path):
    api, window, _, _, _ = make_settings_api(tmp_path)
    api.enqueue(touch(tmp_path, "a.pdf"))
    api.open_settings()
    api.next_file()  # 대기 중인 파일이 없어져도
    assert "hide" not in window.calls


def test_closing_first_run_settings_starts_with_checked_folders(tmp_path):
    import threading

    from main import make_closing_handler

    api, _, saved, root, _ = make_settings_api(tmp_path, first_run=True)
    api.open_settings()
    done = threading.Event()
    original = api.dismiss_settings

    def dismiss_and_signal():
        original()
        done.set()

    api.dismiss_settings = dismiss_and_signal
    assert make_closing_handler(api)() is False
    assert done.wait(2)
    assert saved == [([root], False)]


def test_state_tells_page_to_show_settings(tmp_path):
    api, _, _, _, _ = make_settings_api(tmp_path)
    assert api.state()["settings_open"] is False
    api.open_settings()
    assert api.state()["settings_open"] is True


def test_clear_memory(tmp_path):
    api, _, _, root, memory = make_settings_api(tmp_path)
    memory.remember("코딩", root, now=1)
    assert api.clear_memory() == 0
    assert memory.count() == 0

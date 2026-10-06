from watchdog.events import FileCreatedEvent, FileMovedEvent

from watcher import DownloadHandler, should_ignore_file, wait_until_download_complete


def test_should_ignore_file():
    assert should_ignore_file(r"C:\d\a.pdf.crdownload")
    assert should_ignore_file(r"C:\d\A.TMP")
    assert should_ignore_file(r"C:\d\desktop.ini")
    assert should_ignore_file(r"C:\d\~$보고서.docx")
    assert not should_ignore_file(r"C:\d\보고서.docx")


def test_wait_returns_true_for_finished_file(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"data")
    assert wait_until_download_complete(str(f), interval=0.01, timeout=1)


def test_wait_returns_false_for_missing_file(tmp_path):
    assert not wait_until_download_complete(str(tmp_path / "x.pdf"), interval=0.01, timeout=1)


def test_wait_returns_false_for_firefox_placeholder(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"")
    (tmp_path / "a.pdf.part").write_bytes(b"partial")
    assert not wait_until_download_complete(str(f), interval=0.01, timeout=1)


def make_handler(ready):
    return DownloadHandler(ready.append, wait_fn=lambda p: True, spawn=lambda fn: fn())


def test_created_file_is_reported(tmp_path):
    ready = []
    make_handler(ready).on_created(FileCreatedEvent(str(tmp_path / "a.pdf")))
    assert ready == [str(tmp_path / "a.pdf")]


def test_renamed_temp_file_is_reported_by_final_name(tmp_path):
    ready = []
    make_handler(ready).on_moved(FileMovedEvent(str(tmp_path / "a.pdf.crdownload"), str(tmp_path / "a.pdf")))
    assert ready == [str(tmp_path / "a.pdf")]


def test_temp_files_are_not_reported(tmp_path):
    ready = []
    make_handler(ready).on_created(FileCreatedEvent(str(tmp_path / "a.pdf.crdownload")))
    assert ready == []


def test_duplicate_events_are_ignored(tmp_path):
    ready = []
    handler = make_handler(ready)
    target = str(tmp_path / "a.pdf")
    handler.on_created(FileCreatedEvent(target))
    handler.on_moved(FileMovedEvent(str(tmp_path / "a.pdf.tmp"), target))
    assert ready == [target]


def test_incomplete_download_is_not_reported(tmp_path):
    ready = []
    handler = DownloadHandler(ready.append, wait_fn=lambda p: False, spawn=lambda fn: fn())
    handler.on_created(FileCreatedEvent(str(tmp_path / "a.pdf")))
    assert ready == []


def test_firefox_rename_after_failed_placeholder_wait_is_reported(tmp_path):
    ready = []
    results = iter([False, True])  # 빈 자리표시자 대기 실패 → 이름 변경 후 성공
    handler = DownloadHandler(ready.append, wait_fn=lambda p: next(results), spawn=lambda fn: fn())
    target = str(tmp_path / "a.pdf")
    handler.on_created(FileCreatedEvent(target))
    handler.on_moved(FileMovedEvent(target + ".part", target))
    assert ready == [target]

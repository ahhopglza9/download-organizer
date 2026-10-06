import os

from known_folders import detect_search_roots, known_folder


def mk(path):
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def test_detects_known_and_cloud_folders(tmp_path):
    docs = mk(tmp_path / "Documents")
    desk = mk(tmp_path / "Desktop")
    od = mk(tmp_path / "OneDrive")
    g = mk(tmp_path / "G" / "내 드라이브")
    roots = detect_search_roots(
        {"documents": docs, "desktop": desk}, {"OneDrive": od},
        [str(tmp_path / "G") + os.sep], str(tmp_path / "home"),
    )
    assert roots == [("문서", docs), ("바탕화면", desk), ("OneDrive", od), ("구글 드라이브", g)]


def test_missing_folders_are_skipped(tmp_path):
    docs = mk(tmp_path / "Documents")
    roots = detect_search_roots({"documents": docs, "desktop": None}, {"OneDrive": str(tmp_path / "없음")},
                                [], str(tmp_path / "home"))
    assert roots == [("문서", docs)]


def test_folder_inside_another_is_merged(tmp_path):
    od = mk(tmp_path / "OneDrive")
    desk = mk(tmp_path / "OneDrive" / "Desktop")
    roots = detect_search_roots({"documents": None, "desktop": desk}, {"OneDrive": od}, [], str(tmp_path))
    assert roots == [("OneDrive", od)]


def test_same_folder_is_listed_once(tmp_path):
    od = mk(tmp_path / "OneDrive")
    roots = detect_search_roots({}, {"OneDrive": od, "OneDriveConsumer": od}, [], str(tmp_path / "home"))
    assert roots == [("OneDrive", od)]


def test_google_drive_in_home(tmp_path):
    g = mk(tmp_path / "home" / "Google Drive")
    assert detect_search_roots({}, {}, [], str(tmp_path / "home")) == [("구글 드라이브", g)]


def test_real_known_folders_exist():
    for name in ("documents", "desktop", "downloads"):
        path = known_folder(name)
        assert path and os.path.isdir(path)

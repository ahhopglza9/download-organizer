import os

from paths import app_home, data_dir, is_inside, migrate_legacy_file


def test_app_home_uses_override():
    assert app_home({"DOWNLOAD_ORGANIZER_HOME": r"C:\x"}) == r"C:\x"


def test_app_home_defaults_to_localappdata():
    assert app_home({"LOCALAPPDATA": r"C:\L"}) == r"C:\L\DownloadOrganizer"


def test_data_dir_is_created(tmp_path):
    d = data_dir({"DOWNLOAD_ORGANIZER_HOME": str(tmp_path)})
    assert d == str(tmp_path / "data")
    assert os.path.isdir(d)


def test_migrate_copies_only_when_new_file_is_missing(tmp_path):
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    old.write_text("첫 기억", encoding="utf-8")
    assert migrate_legacy_file(str(old), str(new)) is True
    assert new.read_text(encoding="utf-8") == "첫 기억"
    old.write_text("나중 내용", encoding="utf-8")
    assert migrate_legacy_file(str(old), str(new)) is False
    assert new.read_text(encoding="utf-8") == "첫 기억"


def test_migrate_without_old_file(tmp_path):
    assert migrate_legacy_file(str(tmp_path / "없음.json"), str(tmp_path / "new.json")) is False


def test_is_inside():
    assert is_inside(r"C:\H\app\main.py", r"C:\H")
    assert is_inside(r"C:\H", r"c:\h")
    assert not is_inside(r"C:\Home", r"C:\H")

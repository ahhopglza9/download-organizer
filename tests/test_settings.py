import json

from settings import Settings, load_settings, save_settings, settings_view


def test_load_missing_file_gives_defaults(tmp_path):
    assert load_settings(str(tmp_path / "settings.json")) == Settings()


def test_save_and_load_roundtrip(tmp_path):
    path = str(tmp_path / "settings.json")
    s = Settings(search_roots=[r"C:\문서"], autostart=True, setup_done=True)
    save_settings(path, s)
    assert load_settings(path) == s


def test_load_settings_broken_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{망가짐", encoding="utf-8")
    assert load_settings(str(path)) == Settings()


def test_load_settings_fills_missing_keys(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"search_roots": ["C:\a", 3]}), encoding="utf-8")
    assert load_settings(str(path)) == Settings(search_roots=["C:\a"], autostart=False, setup_done=False)


def test_existing_roots_skips_missing_folders(tmp_path):
    (tmp_path / "있음").mkdir()
    s = Settings(search_roots=[str(tmp_path / "있음"), str(tmp_path / "USB")])
    assert s.existing_roots() == [str(tmp_path / "있음")]


def test_first_run_checks_all_detected_folders():
    view = settings_view(Settings(), [("문서", r"C:\D"), ("바탕화면", r"C:\B")])
    assert view == {
        "roots": [{"path": r"C:\D", "label": "문서", "checked": True},
                  {"path": r"C:\B", "label": "바탕화면", "checked": True}],
        "autostart": False, "first_run": True,
    }


def test_after_setup_only_saved_folders_are_checked_and_custom_ones_are_added():
    s = Settings(search_roots=[r"C:\D", r"E:\사진 보관"], autostart=True, setup_done=True)
    view = settings_view(s, [("문서", r"C:\D"), ("바탕화면", r"C:\B")])
    assert view["roots"] == [
        {"path": r"C:\D", "label": "문서", "checked": True},
        {"path": r"C:\B", "label": "바탕화면", "checked": False},
        {"path": r"E:\사진 보관", "label": "사진 보관", "checked": True},
    ]
    assert view["first_run"] is False and view["autostart"] is True

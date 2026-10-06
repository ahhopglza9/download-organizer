import pytest

from release import check_new_version, set_version


def test_new_version_must_be_plain_and_bigger():
    check_new_version("1.1.0", "1.0.0")
    for bad in ("v1.1.0", "1.1", "다음"):
        with pytest.raises(ValueError):
            check_new_version(bad, "1.0.0")
    with pytest.raises(ValueError):
        check_new_version("1.0.0", "1.0.0")
    with pytest.raises(ValueError):
        check_new_version("0.9.9", "1.0.0")


def test_set_version_changes_only_project_version():
    text = '[project]\nname = "download-organizer"\nversion = "0.1.0"\n\n[tool.uv]\npackage = false\n'
    assert set_version(text, "1.0.0") == text.replace('"0.1.0"', '"1.0.0"')
    with pytest.raises(ValueError):
        set_version("[project]\nname = 'x'\n", "1.0.0")


def test_uv_must_match_version_pinned_for_installs():
    from release import check_uv_version, pinned_uv_version

    text = "$UvVersion = '0.12.23'\n"
    assert pinned_uv_version(text) == "0.12.23"
    check_uv_version("uv 0.12.23 (46b84fd0b 2026-10-03 x86_64-pc-windows-msvc)", "0.12.23")
    with pytest.raises(ValueError):
        check_uv_version("uv 0.13.0 (abc 2026-11-01)", "0.12.23")

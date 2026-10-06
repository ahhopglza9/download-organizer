import os

from folders import is_inside, list_folders


def make_dirs(root, *names):
    for name in names:
        (root / name).mkdir(parents=True, exist_ok=True)


def test_is_inside():
    assert is_inside(r"C:\a\b", r"C:\a")
    assert is_inside(r"C:\A\b", r"c:\a")
    assert is_inside(r"C:\a", r"C:\a")
    assert not is_inside(r"C:\ab", r"C:\a")


def test_lists_root_and_subfolders(tmp_path):
    make_dirs(tmp_path, "회계", "회계/2024", "여행")
    result = list_folders([str(tmp_path)], exclude_dirs=[])
    assert result == sorted([
        str(tmp_path), str(tmp_path / "회계"), str(tmp_path / "회계" / "2024"), str(tmp_path / "여행"),
    ])


def test_ignored_and_hidden_folders_are_pruned(tmp_path):
    make_dirs(tmp_path, ".git/objects", "node_modules/pkg", "src")
    result = list_folders([str(tmp_path)], exclude_dirs=[])
    assert str(tmp_path / "src") in result
    assert not any(".git" in p or "node_modules" in p for p in result)


def test_download_named_folders_are_not_destinations(tmp_path):
    make_dirs(tmp_path, "다운로드", "Downloads", "자료")
    result = list_folders([str(tmp_path)], exclude_dirs=[])
    names = {os.path.basename(p) for p in result}
    assert "자료" in names
    assert "다운로드" not in names
    assert "Downloads" not in names


def test_excluded_dirs_and_children_are_skipped(tmp_path):
    make_dirs(tmp_path, "다운로드 자동화/ui", "다운로드 자동화/tests", "회사")
    result = list_folders([str(tmp_path)], exclude_dirs=[str(tmp_path / "다운로드 자동화")])
    assert result == sorted([str(tmp_path), str(tmp_path / "회사")])


def test_missing_root_is_skipped(tmp_path):
    assert list_folders([str(tmp_path / "없음")], exclude_dirs=[]) == []

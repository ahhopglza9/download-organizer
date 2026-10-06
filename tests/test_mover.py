import pytest

from mover import FolderMissingError, move_file


def test_moves_file_into_folder(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("x", encoding="utf-8")
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    result = move_file(str(src), str(dest_dir))

    assert result == str(dest_dir / "a.txt")
    assert (dest_dir / "a.txt").read_text(encoding="utf-8") == "x"
    assert not src.exists()


def test_adds_number_when_name_is_taken(tmp_path):
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    (dest_dir / "a.txt").write_text("old", encoding="utf-8")
    (dest_dir / "a (1).txt").write_text("old1", encoding="utf-8")
    src = tmp_path / "a.txt"
    src.write_text("new", encoding="utf-8")

    result = move_file(str(src), str(dest_dir))

    assert result == str(dest_dir / "a (2).txt")
    assert (dest_dir / "a.txt").read_text(encoding="utf-8") == "old"
    assert (dest_dir / "a (2).txt").read_text(encoding="utf-8") == "new"


def test_missing_source_raises_file_not_found(tmp_path):
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        move_file(str(tmp_path / "nope.txt"), str(dest_dir))


def test_missing_folder_raises_folder_missing(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("x", encoding="utf-8")
    with pytest.raises(FolderMissingError):
        move_file(str(src), str(tmp_path / "gone"))
    assert src.exists()

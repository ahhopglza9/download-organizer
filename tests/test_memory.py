import json

from memory import Memory, normalize


def test_normalize_ignores_case_and_extra_spaces():
    assert normalize("  Coding   과제 ") == "coding 과제"


def test_remembered_folder_is_found_for_same_query(tmp_path):
    m = Memory(str(tmp_path / "memory.json"))
    m.remember("코딩", r"C:\docs\컴퓨터프로그래밍I", now=1)
    assert m.lookup("코딩") == [(r"C:\docs\컴퓨터프로그래밍I", 1.0)]
    assert m.lookup(" 코딩 ") == [(r"C:\docs\컴퓨터프로그래밍I", 1.0)]


def test_query_containing_all_remembered_words_gets_partial_score(tmp_path):
    m = Memory(str(tmp_path / "memory.json"))
    m.remember("코딩", r"C:\docs\컴프", now=1)
    assert m.lookup("코딩 과제") == [(r"C:\docs\컴프", 0.9)]
    assert m.lookup("과제") == []


def test_more_often_chosen_folder_comes_first_then_most_recent(tmp_path):
    m = Memory(str(tmp_path / "memory.json"))
    m.remember("과제", "A", now=1)
    m.remember("과제", "B", now=2)
    m.remember("과제", "A", now=3)
    assert [f for f, _ in m.lookup("과제")] == ["A", "B"]
    m.remember("과제", "B", now=4)  # 횟수가 같아지면 최근 것이 먼저
    assert [f for f, _ in m.lookup("과제")] == ["B", "A"]


def test_memory_survives_restart(tmp_path):
    path = str(tmp_path / "memory.json")
    Memory(path).remember("코딩", "C", now=1)
    assert Memory(path).lookup("코딩") == [("C", 1.0)]


def test_empty_query_is_not_remembered(tmp_path):
    path = tmp_path / "memory.json"
    Memory(str(path)).remember("   ", "C", now=1)
    assert not path.exists()


def test_broken_memory_file_starts_empty(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text("{망가진 파일", encoding="utf-8")
    m = Memory(str(path))
    assert m.lookup("코딩") == []
    m.remember("코딩", "C", now=1)
    assert json.loads(path.read_text(encoding="utf-8"))["코딩"]["C"]["count"] == 1


def test_count_and_clear(tmp_path):
    path = tmp_path / "memory.json"
    m = Memory(str(path))
    assert m.count() == 0
    m.remember("코딩", "A", now=1)
    m.remember("코딩", "B", now=2)
    m.remember("과제", "C", now=3)
    assert m.count() == 2
    m.clear()
    assert m.count() == 0
    assert m.lookup("코딩") == []
    assert Memory(str(path)).count() == 0

import os

from matcher import Matcher, describe_location, folder_label, text_score
from memory import Memory

ROOT = os.path.abspath(os.sep + "docs")


def path(*parts):
    return os.path.join(ROOT, *parts)


def test_folder_label_uses_last_two_parts():
    assert folder_label(path("회사", "2024")) == "회사/2024"


def test_text_score():
    assert text_score("제주", "2025 제주 여행") == 1.0
    assert text_score("제주 맛집", "2025 제주 여행") == 0.5
    assert text_score("요리", "회계") == 0.0


def test_describe_location():
    assert describe_location(path("회사", "회계"), [ROOT]) == "docs › 회사"
    assert describe_location(path("회계"), [ROOT]) == "docs"


def test_empty_query_returns_nothing():
    m = Matcher(roots=[ROOT])
    m.set_folders([path("회계")])
    assert m.search("   ") == []


def test_matching_name_comes_first_and_unrelated_is_hidden():
    m = Matcher(roots=[ROOT])
    m.set_folders([path("회계"), path("2025 제주 여행")])
    results = m.search("제주")
    assert [r.name for r in results] == ["2025 제주 여행"]
    assert results[0].location == "docs"
    assert results[0].remembered is False


def test_numbers_only_query_matches_by_text():
    m = Matcher(roots=[ROOT])
    m.set_folders([path("2024"), path("요리")])
    assert [r.name for r in m.search("2024")] == ["2024"]


def test_top_n_limits_results():
    m = Matcher(roots=[ROOT])
    m.set_folders([path(f"제주 {i}") for i in range(8)])
    assert len(m.search("제주", top_n=5)) == 5


def test_abbreviation_matches_in_both_directions():
    assert text_score("공학수학2", "2-2 공수2") == 0.9
    assert text_score("공수2", "2-2 공학수학2") == 0.9


def test_abbreviation_requires_same_numbers():
    assert text_score("공학수학2", "2-2 공수1") <= 0.5


def test_single_syllable_is_not_an_abbreviation():
    assert text_score("공학", "자료 공") <= 0.5


def test_spaced_query_matches_abbreviation():
    assert text_score("공학수학 2", "2-2 공수2") == 0.9


def test_abbreviation_ranks_above_different_number():
    m = Matcher(roots=[ROOT])
    m.set_folders([path("공학수학1"), path("공수2")])
    results = m.search("공학수학2")
    assert results[0].name == "공수2"
    assert results[0].score == 0.9


def test_spaced_number_binds_to_previous_word():
    # "2"가 학기 폴더 "2-1"의 2와 맞더라도, 이름에 붙은 숫자가 1이면 공학수학2가 아닙니다.
    assert text_score("공학수학 2", "2-1 공학수학1") == 0.5
    assert text_score("공학수학 1", "2-1 공학수학1") == 1.0


def test_spaced_year_still_matches_separate_number():
    assert text_score("제주 2025", "2025 제주 여행") == 1.0


def test_spaced_query_ranks_abbreviation_with_same_number_first():
    m = Matcher(roots=[ROOT])
    m.set_folders([path("2-1", "공학수학1"), path("2-2", "공수2")])
    assert m.search("공학수학 2")[0].name == "공수2"


def make_dirs(tmp_path, *names):
    for name in names:
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    return [str(tmp_path / n) for n in names]


def test_remembered_folder_ranks_first_without_name_match(tmp_path):
    folders = make_dirs(tmp_path, "컴퓨터프로그래밍I", "코딩 동아리")
    memory = Memory(str(tmp_path / "memory.json"))
    memory.remember("코딩", folders[0], now=1)
    m = Matcher(roots=[str(tmp_path)], memory=memory)
    m.set_folders(folders)
    results = m.search("코딩")
    assert [r.name for r in results] == ["컴퓨터프로그래밍I", "코딩 동아리"]
    assert results[0].remembered is True
    assert results[0].score == 1.0
    assert results[1].remembered is False


def test_remembered_folder_outside_search_roots_is_shown(tmp_path):
    outside = make_dirs(tmp_path, "D드라이브 사진")[0]
    memory = Memory(str(tmp_path / "memory.json"))
    memory.remember("여행 사진", outside, now=1)
    m = Matcher(roots=[str(tmp_path / "docs")], memory=memory)
    m.set_folders([])
    assert [r.path for r in m.search("여행 사진")] == [outside]


def test_deleted_remembered_folder_is_skipped(tmp_path):
    memory = Memory(str(tmp_path / "memory.json"))
    memory.remember("코딩", str(tmp_path / "지워진 폴더"), now=1)
    m = Matcher(roots=[str(tmp_path)], memory=memory)
    m.set_folders([])
    assert m.search("코딩") == []


def test_remembered_folder_also_matching_by_name_appears_once(tmp_path):
    folders = make_dirs(tmp_path, "과제")
    memory = Memory(str(tmp_path / "memory.json"))
    memory.remember("과제", folders[0], now=1)
    m = Matcher(roots=[str(tmp_path)], memory=memory)
    m.set_folders(folders)
    results = m.search("과제")
    assert len(results) == 1
    assert results[0].remembered is True


def test_set_roots_changes_location_text():
    other = os.path.abspath(os.sep + "other")
    m = Matcher(roots=[ROOT])
    m.set_roots([other])
    m.set_folders([os.path.join(other, "회사", "회계")])
    assert m.search("회계")[0].location == "other › 회사"

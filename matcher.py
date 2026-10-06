# -*- coding: utf-8 -*-
"""입력한 검색어와 폴더 이름을 비교해서 점수를 매기고 상위 폴더를 고릅니다.
- 글자 점수: 이름에 그대로 들어 있는지, 줄임말인지("공학수학2" ↔ "공수2"), 글자가 얼마나 비슷한지
- 기억: 같은 검색어로 전에 고른 폴더는 맨 위에 나옵니다 (memory.py)"""

import difflib
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import config
from folders import is_inside


@dataclass(frozen=True)
class Result:
    path: str
    name: str
    location: str
    score: float
    remembered: bool = False  # 전에 이 검색어로 고른 폴더인지


@dataclass(frozen=True)
class _Folder:
    path: str
    name: str
    location: str
    text: str  # 글자 비교용 (예: "회사 2024")


def folder_label(folder: str) -> str:
    """경로의 마지막 두 단계 (예: "회사/2024"). "2024"처럼 이름만으로 뜻을 알기 어려운 폴더를 보완합니다."""
    parts = [p for p in Path(folder).parts if not p.endswith(("\\", "/", ":"))]
    return "/".join(parts[-2:])


def is_abbreviation(short: str, full: str) -> bool:
    """short가 full의 줄임말인지 봅니다 (예: "공수2"는 "공학수학2"의 줄임말).
    - 한글 부분: 두 글자 이상, 첫 글자가 같고, full의 한글에 같은 순서로 띄엄띄엄 들어 있으며 더 짧아야 합니다.
    - 숫자·영문 부분: 정확히 같아야 합니다 ("공수1"은 "공학수학2"의 줄임말이 아님)."""
    short_hangul = re.sub(r"[^가-힣]", "", short)
    full_hangul = re.sub(r"[^가-힣]", "", full)
    if len(short_hangul) < 2 or len(short_hangul) >= len(full_hangul) or short_hangul[0] != full_hangul[0]:
        return False
    if short_hangul in full_hangul:
        return False  # "제주"와 "제주맛집"처럼 그대로 이어져 있으면 줄임말이 아니라 일부분입니다.
    if re.findall(r"[0-9a-z]+", short.lower()) != re.findall(r"[0-9a-z]+", full.lower()):
        return False
    rest = iter(full_hangul)
    return all(ch in rest for ch in short_hangul)


def _query_units(words):
    """띄어 쓴 숫자를 앞 단어에 묶습니다. ["공학수학", "2"] -> [("공학수학", "2")]"""
    units = []
    for w in words:
        if w.isdigit() and units and units[-1][1] is None and not units[-1][0].isdigit():
            units[-1] = (units[-1][0], w)
        else:
            units.append((w, None))
    return units


def _unit_credit(word: str, number, text: str, target: str) -> float:
    """입력 한 단위(단어 + 띄어 쓴 숫자)가 폴더 이름과 맞는 정도.
    폴더 이름에서 그 단어 바로 뒤에 다른 숫자가 붙어 있으면(공학수학1 ↔ 입력 "공학수학 2") 절반만 줍니다.
    숫자가 붙어 있지 않으면 따로 떨어진 같은 숫자만 있어도 맞는 것으로 봅니다(입력 "제주 2025" ↔ "2025 제주 여행")."""
    if word not in target:
        return 0.0
    if number is None:
        return 1.0
    attached = re.search(re.escape(word) + r"\s*(\d+)", text)
    if attached:
        return 1.0 if attached.group(1) == number else 0.5
    return 1.0 if number in re.findall(r"\d+", text) else 0.5


def strong_text_score(query: str, text: str) -> float:
    """확실한 글자 일치 점수. 입력 단어가 폴더 이름에 그대로 들어 있는 비율과,
    줄임말로 맞으면 ABBREVIATION_SCORE 중 큰 값. 둘 다 아니면 0."""
    words = query.lower().split()
    target = text.lower().replace(" ", "")
    if not words or not target:
        return 0.0
    units = _query_units(words)
    score = sum(_unit_credit(w, n, text.lower(), target) for w, n in units) / len(units)
    # 띄어 쓴 입력("공학수학 2")은 붙여 쓴 형태로도 비교합니다.
    forms = set(words) | {"".join(words)}
    tokens = [t for t in re.split(r"[\s\-_.,()\[\]]+", text.lower()) if t]
    if any(is_abbreviation(a, b) or is_abbreviation(b, a) for a in forms for b in tokens):
        score = max(score, config.ABBREVIATION_SCORE)
    return score


def text_score(query: str, text: str) -> float:
    """글자 점수. 확실한 일치(그대로 들어 있음, 줄임말)가 없으면 글자 유사도의 절반."""
    strong = strong_text_score(query, text)
    if strong:
        return strong
    words = query.lower().split()
    target = text.lower().replace(" ", "")
    if not words or not target:
        return 0.0
    return difflib.SequenceMatcher(None, "".join(words), target).ratio() * 0.5


def describe_location(path: str, roots) -> str:
    """폴더가 있는 위치를 "Documents › 회사"처럼 보여줍니다."""
    for root in roots:
        if is_inside(path, root) and os.path.normcase(os.path.abspath(path)) != os.path.normcase(os.path.abspath(root)):
            rel = os.path.relpath(os.path.dirname(path), root)
            parts = [os.path.basename(os.path.abspath(root))]
            if rel != ".":
                parts += rel.split(os.sep)
            return " › ".join(parts)
    return os.path.dirname(path)


class Matcher:
    def __init__(self, roots, memory=None):
        self._roots = list(roots)
        self._memory = memory
        self._lock = threading.Lock()
        self._folders = []

    def _describe(self, path: str) -> _Folder:
        return _Folder(
            path=path,
            name=os.path.basename(path) or path,
            location=describe_location(path, self._roots),
            text=folder_label(path).replace("/", " "),
        )

    def set_roots(self, roots):
        """설정에서 검색 위치가 바뀌면 부릅니다. 위치 표시("문서 › 회사")에 씁니다."""
        with self._lock:
            self._roots = list(roots)

    def set_folders(self, paths):
        folders = [self._describe(p) for p in paths]
        with self._lock:
            self._folders = folders

    def search(self, query: str, top_n: int = config.TOP_N) -> list:
        query = query.strip()
        if not query:
            return []
        with self._lock:
            folders = self._folders

        results = {}
        for f in folders:
            score = text_score(query, f.text)
            if score >= config.MIN_SCORE:
                results[os.path.normcase(f.path)] = Result(f.path, f.name, f.location, round(score, 4))

        # 기억된 폴더: 이름이 안 맞아도, 검색 위치 밖이어도 보여줍니다. 지워진 폴더는 뺍니다.
        memory_rank = {}
        remembered = self._memory.lookup(query) if self._memory else []
        for rank, (path, score) in enumerate(remembered):
            if not os.path.isdir(path):
                continue
            key = os.path.normcase(path)
            existing = results.get(key)
            if existing is None or score >= existing.score:
                d = self._describe(path)
                results[key] = Result(path, d.name, d.location, score, remembered=True)
                memory_rank[key] = rank

        ordered = sorted(
            results.items(),
            key=lambda kv: (-kv[1].score, memory_rank.get(kv[0], len(remembered)), kv[1].path),
        )
        return [r for _, r in ordered[:top_n]]

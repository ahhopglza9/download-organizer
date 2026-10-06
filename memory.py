# -*- coding: utf-8 -*-
"""검색어마다 사용자가 고른 폴더를 기억합니다.
"코딩"으로 검색해서 "컴퓨터프로그래밍I"를 한 번 고르면, 다음부터 "코딩"에 그 폴더가 맨 위에 나옵니다."""

import json
import os
import threading
import time

import config


def normalize(query: str) -> str:
    """대소문자와 띄어쓰기 개수를 무시하도록 검색어를 정리합니다."""
    return " ".join(query.lower().split())


class Memory:
    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._entries = self._load()  # {검색어: {폴더 경로: {"count": 고른 횟수, "last": 마지막으로 고른 시각}}}

    def _load(self) -> dict:
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        entries = {}
        for query, folders in data.items():
            if not isinstance(folders, dict):
                continue
            entries[query] = {
                folder: {"count": int(e.get("count", 0)), "last": float(e.get("last", 0))}
                for folder, e in folders.items() if isinstance(e, dict)
            }
        return entries

    def _save_locked(self):
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self._path)
        except OSError as e:
            print(f"[알림] 고른 폴더를 저장하지 못했어요: {e}")

    def remember(self, query: str, folder: str, now: float = None):
        q = normalize(query)
        if not q:
            return
        with self._lock:
            entry = self._entries.setdefault(q, {}).setdefault(folder, {"count": 0, "last": 0.0})
            entry["count"] += 1
            entry["last"] = time.time() if now is None else now
            self._save_locked()

    def count(self) -> int:
        """기억하고 있는 검색어 수."""
        with self._lock:
            return len(self._entries)

    def clear(self):
        with self._lock:
            self._entries = {}
            self._save_locked()

    def lookup(self, query: str) -> list:
        """기억된 (폴더 경로, 점수) 목록. 같은 검색어면 1.0, 기억된 단어가 입력에 모두 들어 있으면
        MEMORY_PARTIAL_SCORE. 점수 → 고른 횟수 → 최근에 고른 순서로 정렬합니다."""
        q = normalize(query)
        if not q:
            return []
        words = set(q.split())
        best = {}  # 폴더 -> (점수, 횟수, 마지막 시각)
        with self._lock:
            for key, folders in self._entries.items():
                if key == q:
                    score = 1.0
                elif set(key.split()) <= words:
                    score = config.MEMORY_PARTIAL_SCORE
                else:
                    continue
                for folder, e in folders.items():
                    candidate = (score, e["count"], e["last"])
                    if folder not in best or candidate > best[folder]:
                        best[folder] = candidate
        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
        return [(folder, rank[0]) for folder, rank in ranked]

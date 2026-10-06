# -*- coding: utf-8 -*-
"""사용자 설정(data\\settings.json): 검색할 폴더, Windows 시작 시 자동 실행, 첫 설정을 마쳤는지."""

import json
import os
from dataclasses import asdict, dataclass, field


@dataclass
class Settings:
    search_roots: list = field(default_factory=list)
    autostart: bool = False
    setup_done: bool = False

    def existing_roots(self) -> list:
        """지금 있는 폴더만. USB를 뺐거나 폴더를 지운 경우 그 폴더만 건너뜁니다."""
        return [r for r in self.search_roots if os.path.isdir(r)]


def load_settings(path: str) -> Settings:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    roots = data.get("search_roots")
    roots = [r for r in roots if isinstance(r, str)] if isinstance(roots, list) else []
    return Settings(search_roots=roots, autostart=data.get("autostart") is True,
                    setup_done=data.get("setup_done") is True)


def save_settings(path: str, settings: Settings):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(asdict(settings), f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def settings_view(settings: Settings, detected) -> dict:
    """설정 화면에 보여줄 내용. 첫 실행이면 자동으로 찾은 폴더를 모두 체크해 둡니다.
    사용자가 직접 추가한 폴더는 자동으로 찾은 폴더 뒤에 붙입니다."""
    first_run = not settings.setup_done
    saved = {os.path.normcase(r) for r in settings.search_roots}
    rows, seen = [], set()
    for label, path in detected:
        key = os.path.normcase(path)
        seen.add(key)
        rows.append({"path": path, "label": label, "checked": first_run or key in saved})
    for path in settings.search_roots:
        key = os.path.normcase(path)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"path": path, "label": os.path.basename(path.rstrip("\\/")) or path, "checked": True})
    return {"roots": rows, "autostart": settings.autostart, "first_run": first_run}

# -*- coding: utf-8 -*-
"""프로그램과 사용자 데이터가 놓이는 위치.
설치 버전: %LOCALAPPDATA%\\DownloadOrganizer\\app (코드), ...\\data (설정·기억·기록).
저장소 폴더에서 개발용으로 실행해도 같은 data 폴더를 씁니다."""

import os
import shutil

APP_NAME = "DownloadOrganizer"


def app_home(env=os.environ) -> str:
    override = env.get("DOWNLOAD_ORGANIZER_HOME")
    if override:
        return override
    local = env.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    return os.path.join(local, APP_NAME)


def data_dir(env=os.environ) -> str:
    path = os.path.join(app_home(env), "data")
    os.makedirs(path, exist_ok=True)
    return path


def is_inside(path: str, parent: str) -> bool:
    p = os.path.normcase(os.path.abspath(path))
    q = os.path.normcase(os.path.abspath(parent))
    return p == q or p.startswith(q.rstrip(os.sep) + os.sep)


def migrate_legacy_file(old: str, new: str) -> bool:
    """예전 위치의 파일을 새 위치에 한 번만 복사합니다. 새 위치에 이미 있으면 건드리지 않습니다."""
    if os.path.exists(old) and not os.path.exists(new):
        shutil.copy2(old, new)
        return True
    return False

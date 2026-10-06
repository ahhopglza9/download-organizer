# -*- coding: utf-8 -*-
"""검색 위치 아래에서 파일을 옮길 수 있는 후보 폴더를 모읍니다."""

import os

import config


def is_inside(path: str, parent: str) -> bool:
    """path가 parent 자신이거나 그 하위 폴더인지 확인합니다 (Windows 대소문자 무시)."""
    path = os.path.normcase(os.path.abspath(path))
    parent = os.path.normcase(os.path.abspath(parent))
    return path == parent or path.startswith(parent + os.sep)


def list_folders(roots, exclude_dirs) -> list:
    """roots 아래의 모든 후보 폴더(루트 자신 포함)를 정렬해서 반환합니다.
    - IGNORE_FOLDER_NAMES와 "."으로 시작하는 폴더는 하위까지 건너뜁니다.
    - exclude_dirs(다운로드 폴더, 이 프로그램 폴더)도 하위까지 건너뜁니다.
    - EXCLUDE_AS_DESTINATION_NAMES 이름의 폴더는 후보에서 빼지만 하위는 계속 봅니다."""
    excluded_names = {n.lower() for n in config.EXCLUDE_AS_DESTINATION_NAMES}
    result = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, _ in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d not in config.IGNORE_FOLDER_NAMES
                and not d.startswith(".")
                and not any(is_inside(os.path.join(dirpath, d), ex) for ex in exclude_dirs)
            ]
            if os.path.basename(dirpath).lower() not in excluded_names:
                result.append(os.path.abspath(dirpath))
    return sorted(result)

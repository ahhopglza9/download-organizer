# -*- coding: utf-8 -*-
"""다운로드한 파일을 고른 폴더로 옮깁니다. 같은 이름이 있으면 번호를 붙이고, 덮어쓰지 않습니다."""

import os
import shutil


class FolderMissingError(Exception):
    """옮길 폴더가 없을 때 (추천 후 폴더가 삭제되거나 이름이 바뀐 경우)."""


def _unique_destination(folder: str, filename: str) -> str:
    stem, ext = os.path.splitext(filename)
    candidate = os.path.join(folder, filename)
    n = 1
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{stem} ({n}){ext}")
        n += 1
    return candidate


def move_file(src: str, folder: str) -> str:
    """src 파일을 folder 안으로 옮기고 최종 경로를 반환합니다."""
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    if not os.path.isdir(folder):
        raise FolderMissingError(folder)
    dest = _unique_destination(folder, os.path.basename(src))
    shutil.move(src, dest)
    return dest

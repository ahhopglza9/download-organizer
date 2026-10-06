# -*- coding: utf-8 -*-
"""Windows가 알고 있는 사용자 폴더(문서, 바탕화면, 다운로드)의 실제 위치와,
검색 위치로 쓸 만한 폴더(OneDrive, 구글 드라이브)를 찾습니다."""

import ctypes
import os
import string
import uuid
from ctypes import wintypes
from pathlib import Path

_FOLDER_IDS = {
    "documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
    "desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
    "downloads": "374DE290-123F-4565-9164-39C4925E467B",
}


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


def _guid(text: str) -> _GUID:
    u = uuid.UUID(text)
    g = _GUID()
    g.Data1, g.Data2, g.Data3 = u.time_low, u.time_mid, u.time_hi_version
    g.Data4[:] = list(u.bytes[8:])
    return g


def known_folder(name: str):
    """사용자가 폴더를 옮겼거나 OneDrive로 백업 중이어도 실제 위치를 돌려줍니다. 실패하면 None."""
    path = ctypes.c_wchar_p()
    guid = _guid(_FOLDER_IDS[name])
    hr = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path))
    try:
        return path.value if hr == 0 else None
    finally:
        ctypes.windll.ole32.CoTaskMemFree(path)


def _key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _strictly_inside(path: str, parent: str) -> bool:
    p, q = _key(path), _key(parent)
    return p != q and p.startswith(q.rstrip(os.sep) + os.sep)


def detect_search_roots(known, env, drive_roots, home, isdir=os.path.isdir):
    """검색 위치 후보를 (라벨, 경로)로 돌려줍니다. 없는 폴더는 빼고, 같은 폴더는 한 번만,
    다른 후보 안에 들어 있는 폴더는 바깥 폴더로 합칩니다."""
    candidates = [("문서", known.get("documents")), ("바탕화면", known.get("desktop"))]
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        candidates.append(("OneDrive", env.get(var)))
    for drive in drive_roots:
        for name in ("내 드라이브", "My Drive"):
            candidates.append(("구글 드라이브", os.path.join(drive, name)))
    for name in ("내 드라이브", "Google Drive"):
        candidates.append(("구글 드라이브", os.path.join(home, name)))

    found, seen = [], set()
    for label, path in candidates:
        if not path or not isdir(path):
            continue
        path = os.path.abspath(path)
        if _key(path) in seen:
            continue
        seen.add(_key(path))
        found.append((label, path))
    return [(label, path) for label, path in found
            if not any(_strictly_inside(path, other) for _, other in found)]


def _drive_roots():
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return [f"{c}:\\" for i, c in enumerate(string.ascii_uppercase) if mask >> i & 1 and c not in "AB"]


def default_search_roots():
    known = {name: known_folder(name) for name in ("documents", "desktop")}
    return detect_search_roots(known, os.environ, _drive_roots(), str(Path.home()))

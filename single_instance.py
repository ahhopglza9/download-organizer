# -*- coding: utf-8 -*-
"""프로그램이 두 번 켜지지 않게 합니다. 두 개가 동시에 돌면 다운로드마다 입력창이 두 번 뜨기 때문입니다.
Windows의 이름 붙은 뮤텍스를 씁니다. 프로그램이 꺼지면(비정상 종료 포함) Windows가 자동으로 풀어 줍니다."""

import ctypes
import time

_ERROR_ALREADY_EXISTS = 183
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.restype = ctypes.c_void_p
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
_kernel32.CloseHandle.argtypes = [ctypes.c_void_p]


def _try_acquire(name: str):
    handle = _kernel32.CreateMutexW(None, False, name)
    if not handle:
        return None
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return None
    return handle


def acquire(name: str, wait: float = 0.0):
    """처음 실행이면 핸들을, 이미 실행 중이면 None을 돌려줍니다.
    wait초 동안은 앞 프로그램이 꺼지기를 기다립니다 (업데이트 후 다시 시작할 때)."""
    deadline = time.monotonic() + wait
    while True:
        handle = _try_acquire(name)
        if handle is not None or time.monotonic() >= deadline:
            return handle
        time.sleep(0.2)


def release(handle):
    _kernel32.CloseHandle(handle)

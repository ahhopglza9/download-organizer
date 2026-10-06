# -*- coding: utf-8 -*-
"""Windows를 켤 때 자동으로 실행되게 등록하거나 해제합니다 (사용자 레지스트리, 관리자 권한 불필요)."""

import os
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "DownloadOrganizer"


def set_autostart(enabled: bool, command: str, key_path: str = RUN_KEY):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass


def is_autostart_enabled(key_path: str = RUN_KEY) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except FileNotFoundError:
        return False


def autostart_command(program_dir: str, home: str, pythonw: str) -> str:
    """설치 버전이면 launcher.py(업데이트 확인 포함)를, 개발용 복사본이면 main.py를 바로 실행합니다."""
    if os.path.normcase(os.path.abspath(program_dir)) == os.path.normcase(os.path.join(home, "app")):
        venv_pythonw = os.path.join(home, ".venv", "Scripts", "pythonw.exe")
        return f'"{venv_pythonw}" "{os.path.join(home, "launcher.py")}" --autostart'
    return f'"{pythonw}" "{os.path.join(program_dir, "main.py")}" --autostart'

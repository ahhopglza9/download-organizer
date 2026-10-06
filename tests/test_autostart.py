import winreg

import pytest

from autostart import VALUE_NAME, autostart_command, is_autostart_enabled, set_autostart

TEST_PARENT = r"Software\DownloadOrganizerTest"
TEST_KEY = TEST_PARENT + r"\Run"


@pytest.fixture(autouse=True)
def cleanup_registry():
    yield
    for key in (TEST_KEY, TEST_PARENT):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except FileNotFoundError:
            pass


def test_enable_and_disable():
    set_autostart(True, r'"C:\py\pythonw.exe" "C:\H\launcher.py" --autostart', key_path=TEST_KEY)
    assert is_autostart_enabled(TEST_KEY)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, TEST_KEY) as key:
        assert winreg.QueryValueEx(key, VALUE_NAME)[0].endswith("--autostart")
    set_autostart(False, "", key_path=TEST_KEY)
    assert not is_autostart_enabled(TEST_KEY)
    set_autostart(False, "", key_path=TEST_KEY)  # 이미 꺼져 있어도 오류 없음


def test_command_for_installed_program():
    assert autostart_command(r"C:\H\app", r"C:\H", r"C:\py\pythonw.exe") == \
        r'"C:\H\.venv\Scripts\pythonw.exe" "C:\H\launcher.py" --autostart'


def test_command_for_development_copy():
    assert autostart_command(r"C:\dev", r"C:\H", r"C:\py\pythonw.exe") == \
        r'"C:\py\pythonw.exe" "C:\dev\main.py" --autostart'

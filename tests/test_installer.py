import re
from pathlib import Path

INSTALLER = Path("installer")


def test_install_script_pins_uv_with_hash():
    text = (INSTALLER / "install.ps1").read_text(encoding="utf-8-sig")
    assert re.search(r"\$UvVersion = '\d+\.\d+\.\d+'", text)
    assert re.search(r"\$UvSha256 = '[0-9a-f]{64}'", text)


def test_powershell_scripts_have_utf8_bom():
    for name in ("install.ps1", "uninstall.ps1"):
        assert (INSTALLER / name).read_bytes().startswith(b"\xef\xbb\xbf"), name


def test_cmd_files_are_ascii_only():
    for name in ("DownloadOrganizer-Setup.cmd", "uninstall.cmd"):
        (INSTALLER / name).read_bytes().decode("ascii")


def test_setup_downloads_latest_install_script():
    text = (INSTALLER / "DownloadOrganizer-Setup.cmd").read_text(encoding="ascii")
    assert "https://github.com/ahhopglza9/download-organizer/releases/latest/download/install.ps1" in text


def test_pyproject_pins_python_and_platform():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = "==3.14.*"' in text
    assert "sys_platform == 'win32'" in text
    assert Path("uv.lock").exists()


def run_uninstall(root):
    import subprocess

    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(INSTALLER / "uninstall.ps1"), "-Root", str(root), "-Force"],
        capture_output=True, timeout=120,
    )


def test_uninstall_refuses_folder_that_is_not_an_install(tmp_path):
    desktop = tmp_path / "바탕화면"
    desktop.mkdir()
    (desktop / "소중한 파일.txt").write_text("지우면 안 됨", encoding="utf-8")
    (desktop / "제거.cmd").write_text("@echo off", encoding="ascii")
    result = run_uninstall(desktop)
    assert result.returncode != 0
    assert (desktop / "소중한 파일.txt").exists()


def test_uninstall_removes_real_install_folder(tmp_path):
    root = tmp_path / "DownloadOrganizer"
    (root / "app").mkdir(parents=True)
    (root / ".venv").mkdir()
    for name in ("launcher.py", "uv.exe"):
        (root / name).write_text("x", encoding="ascii")
    (root / "app" / "main.py").write_text("x", encoding="ascii")
    result = run_uninstall(root)
    assert result.returncode == 0, result.stdout.decode("utf-8", "replace")
    assert not root.exists()


def test_install_extracts_app_inside_install_folder():
    text = (INSTALLER / "install.ps1").read_text(encoding="utf-8-sig")
    assert "$staging = Join-Path $Root 'app.staging'" in text
    assert "Expand-Archive -Path $appZip -DestinationPath $staging" in text

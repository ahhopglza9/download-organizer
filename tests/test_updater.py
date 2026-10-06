import io
import json
import os
import urllib.error
import zipfile

import updater
from updater import (apply_update, check_for_update, deps_changed, extract_release_zip, is_newer,
                     latest_release_tag, launch, parse_version, read_version)

LOCK = 'version = 1\n[[package]]\nname = "download-organizer"\nversion = "{v}"\n[[package]]\nname = "watchdog"\nversion = "{w}"\n'


def write_app(folder, version, lock_watchdog="6.0.0", launcher="old"):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "pyproject.toml"), "w", encoding="utf-8") as f:
        f.write(f'[project]\nname = "download-organizer"\nversion = "{version}"\n')
    with open(os.path.join(folder, "uv.lock"), "w", encoding="utf-8") as f:
        f.write(LOCK.format(v=version, w=lock_watchdog))
    with open(os.path.join(folder, "launcher.py"), "w", encoding="utf-8") as f:
        f.write(launcher)


def make_home(tmp_path):
    home = str(tmp_path)
    write_app(os.path.join(home, "app"), "1.0.0")
    with open(os.path.join(home, "launcher.py"), "w", encoding="utf-8") as f:
        f.write("old")
    return home


def test_parse_and_compare_versions():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("1.2") is None
    assert parse_version(None) is None
    assert is_newer("v1.10.0", "1.9.9")
    assert not is_newer("v1.0.0", "1.0.0")
    assert not is_newer("최신", "1.0.0")


def test_read_version(tmp_path):
    write_app(str(tmp_path), "2.3.4")
    assert read_version(str(tmp_path)) == "2.3.4"
    assert read_version(str(tmp_path / "없음")) == "0.0.0"


def test_latest_release_tag():
    opener = lambda req, timeout: io.BytesIO(json.dumps({"tag_name": "v1.2.0"}).encode())
    assert latest_release_tag(opener=opener) == "v1.2.0"


def test_latest_release_tag_handles_errors():
    def rate_limited(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "rate limit", {}, None)

    def offline(req, timeout):
        raise urllib.error.URLError("no network")

    assert latest_release_tag(opener=rate_limited) is None
    assert latest_release_tag(opener=offline) is None
    assert latest_release_tag(opener=lambda r, timeout: io.BytesIO(b"[]")) is None
    assert latest_release_tag(opener=lambda r, timeout: io.BytesIO(b'{"tag_name": "nightly"}')) is None


def test_check_for_update(tmp_path):
    write_app(str(tmp_path), "1.0.0")
    assert check_for_update(str(tmp_path), latest=lambda: "v1.1.0") == "v1.1.0"
    assert check_for_update(str(tmp_path), latest=lambda: "v1.0.0") is None
    assert check_for_update(str(tmp_path), latest=lambda: None) is None


def test_extract_release_zip_strips_top_folder(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("download-organizer-1.1.0/main.py", "print(1)")
        z.writestr("download-organizer-1.1.0/ui/app.js", "//")
    extract_release_zip(buf.getvalue(), str(tmp_path / "out"))
    assert (tmp_path / "out" / "main.py").read_text() == "print(1)"
    assert (tmp_path / "out" / "ui" / "app.js").exists()


def test_deps_changed_ignores_own_version():
    assert not deps_changed(LOCK.format(v="1.0.0", w="6.0.0"), LOCK.format(v="1.1.0", w="6.0.0"))
    assert deps_changed(LOCK.format(v="1.0.0", w="6.0.0"), LOCK.format(v="1.1.0", w="6.1.0"))


def test_apply_update_swaps_app_and_launcher(tmp_path):
    home = make_home(tmp_path)
    synced = []
    ok = apply_update(home, "v1.1.0", download=lambda tag, dest: write_app(dest, "1.1.0", launcher="new"),
                      sync=lambda h, project: synced.append(project))
    assert ok is True
    assert read_version(os.path.join(home, "app")) == "1.1.0"
    assert open(os.path.join(home, "launcher.py"), encoding="utf-8").read() == "new"
    assert not os.path.exists(os.path.join(home, "app.new"))
    assert not os.path.exists(os.path.join(home, "app.old"))
    assert synced == []


def test_apply_update_installs_changed_libraries_first(tmp_path):
    home = make_home(tmp_path)
    order = []

    def sync(h, project):
        order.append(("sync", read_version(os.path.join(h, "app"))))

    assert apply_update(home, "v1.1.0", download=lambda tag, dest: write_app(dest, "1.1.0", lock_watchdog="6.1.0"),
                        sync=sync)
    assert order == [("sync", "1.0.0")]  # 바꿔 끼우기 전에 라이브러리 설치


def test_failed_download_keeps_current_version(tmp_path):
    home = make_home(tmp_path)

    def broken(tag, dest):
        os.makedirs(dest)
        raise OSError("연결 끊김")

    assert apply_update(home, "v1.1.0", download=broken, sync=lambda h, p: None) is False
    assert read_version(os.path.join(home, "app")) == "1.0.0"
    assert not os.path.exists(os.path.join(home, "app.new"))
    assert "업데이트에 실패" in open(os.path.join(home, "data", "app.log"), encoding="utf-8").read()


def test_failed_library_install_keeps_current_version(tmp_path):
    home = make_home(tmp_path)

    def failing_sync(h, project):
        raise RuntimeError("uv 실패")

    assert apply_update(home, "v1.1.0", download=lambda tag, dest: write_app(dest, "1.1.0", lock_watchdog="7.0.0"),
                        sync=failing_sync) is False
    assert read_version(os.path.join(home, "app")) == "1.0.0"


def test_leftovers_from_crash_are_recovered(tmp_path):
    home = make_home(tmp_path)
    os.rename(os.path.join(home, "app"), os.path.join(home, "app.old"))  # 교체 도중 꺼진 상황
    write_app(os.path.join(home, "app.new"), "9.9.9")
    assert apply_update(home, "v1.1.0", download=lambda tag, dest: write_app(dest, "1.1.0"), sync=lambda h, p: None)
    assert read_version(os.path.join(home, "app")) == "1.1.0"


def test_launch_updates_then_starts_program(tmp_path):
    home = make_home(tmp_path)
    updated, started = [], []
    command = launch(home, ["--autostart"], popen=lambda cmd, cwd: started.append((cmd, cwd)),
                     latest=lambda: "v1.1.0", update=lambda h, tag: updated.append(tag),
                     running=lambda wait: False, update_lock=lambda: "lock", release_lock=lambda lock: None)
    assert updated == ["v1.1.0"]
    assert command == [os.path.join(home, ".venv", "Scripts", "pythonw.exe"),
                       os.path.join(home, "app", "main.py"), "--autostart"]
    assert started == [(command, os.path.join(home, "app"))]


def test_launch_starts_even_when_update_check_fails(tmp_path):
    home = make_home(tmp_path)
    started = []

    def broken_latest():
        raise RuntimeError("예상 못 한 오류")

    launch(home, [], popen=lambda cmd, cwd: started.append(cmd), latest=broken_latest,
           update=lambda h, tag: None, running=lambda wait: False, update_lock=lambda: "lock",
           release_lock=lambda lock: None)
    assert len(started) == 1


def test_launch_dry_run_does_not_start(tmp_path, capsys):
    home = make_home(tmp_path)
    launch(home, ["--dry-run"], popen=lambda cmd, cwd: (_ for _ in ()).throw(AssertionError("실행하면 안 됨")),
           latest=lambda: None, update=lambda h, tag: None, running=lambda wait: False,
           update_lock=lambda: "lock", release_lock=lambda lock: None)
    assert "main.py" in capsys.readouterr().out


def test_uv_env_keeps_everything_inside_home():
    env = updater.uv_env(r"C:\H")
    assert env["UV_PYTHON_INSTALL_DIR"] == r"C:\H\python"
    assert env["UV_CACHE_DIR"] == r"C:\H\cache"
    assert env["UV_PROJECT_ENVIRONMENT"] == r"C:\H\.venv"
    assert env["UV_PYTHON_PREFERENCE"] == "only-managed"


def test_launch_skips_update_while_program_is_running(tmp_path):
    home = make_home(tmp_path)
    updated, started, waits = [], [], []

    def running(wait):
        waits.append(wait)
        return True

    launch(home, [], popen=lambda cmd, cwd: started.append(cmd), latest=lambda: "v1.1.0",
           update=lambda h, tag: updated.append(tag), running=running)
    assert updated == []
    assert len(started) == 1
    launch(home, ["--restarted"], popen=lambda cmd, cwd: None, latest=lambda: "v1.1.0",
           update=lambda h, tag: None, running=running)
    assert waits == [0, 10]  # 다시 시작할 때는 이전 프로그램이 꺼지기를 기다림


def test_launch_skips_update_when_another_launcher_is_updating(tmp_path):
    home = make_home(tmp_path)
    updated = []
    launch(home, [], popen=lambda cmd, cwd: None, latest=lambda: "v1.1.0",
           update=lambda h, tag: updated.append(tag), running=lambda wait: False,
           update_lock=lambda: None)
    assert updated == []


def test_instance_name_matches_program():
    import config

    assert updater.INSTANCE_NAME == config.INSTANCE_NAME


def test_rename_retries_briefly_locked_folder(tmp_path, monkeypatch):
    home = make_home(tmp_path)
    real_rename = os.rename
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError("백신이 잠깐 잡고 있음")
        real_rename(src, dst)

    monkeypatch.setattr(updater.os, "rename", flaky)
    monkeypatch.setattr(updater, "RENAME_RETRY_DELAY", 0.01)
    assert apply_update(home, "v1.1.0", download=lambda tag, dest: write_app(dest, "1.1.0"), sync=lambda h, p: None)
    assert read_version(os.path.join(home, "app")) == "1.1.0"


def test_launcher_recovers_app_folder_left_by_interrupted_update(tmp_path):
    import shutil
    import subprocess
    import sys

    home = tmp_path / "home"
    (home / "app.old").mkdir(parents=True)
    shutil.copy("launcher.py", home / "launcher.py")
    (home / "app.old" / "updater.py").write_text(
        "def launch(home, args):\n    open(home + '/started.txt', 'w').write('ok')\n", encoding="utf-8")
    subprocess.run([sys.executable, str(home / "launcher.py")], check=True, timeout=30)
    assert (home / "app" / "updater.py").exists()
    assert (home / "started.txt").read_text() == "ok"

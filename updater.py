# -*- coding: utf-8 -*-
"""새 배포 버전을 확인하고 받아서 바꿔 끼웁니다. launcher.py와 main.py가 함께 씁니다.
라이브러리가 깨졌을 때도 동작하도록 표준 라이브러리만 씁니다.
어느 단계에서 실패하든 지금 버전을 그대로 둡니다."""

import io
import json
import os
import re
import shutil
import subprocess
import time
import tomllib
import urllib.request
import zipfile

REPO = "ahhopglza9/download-organizer"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ZIP_URL = "https://github.com/{repo}/archive/refs/tags/{tag}.zip"
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "download-organizer"}
CREATE_NO_WINDOW = 0x08000000
# 프로그램 실행 중 잠금 이름 (config.INSTANCE_NAME과 같아야 함), 업데이트 중 잠금 이름
INSTANCE_NAME = r"Local\DownloadOrganizer"
UPDATE_LOCK_NAME = r"Local\DownloadOrganizerUpdate"
# 백신·검색 색인이 막 만든 폴더를 잠깐 잡고 있을 때를 대비해 이름 바꾸기를 몇 번 다시 시도합니다.
RENAME_RETRIES = 5
RENAME_RETRY_DELAY = 0.5


def parse_version(text):
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def is_newer(latest, current) -> bool:
    a, b = parse_version(latest), parse_version(current)
    return a is not None and b is not None and a > b


def read_version(app_dir: str) -> str:
    try:
        with open(os.path.join(app_dir, "pyproject.toml"), "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "0.0.0"


def latest_release_tag(timeout: float = 3.0, opener=urllib.request.urlopen):
    """최신 배포 버전 태그. 인터넷이 안 되거나, 요청 제한에 걸리거나, 이상한 응답이면 None."""
    request = urllib.request.Request(LATEST_URL, headers=HEADERS)
    try:
        with opener(request, timeout=timeout) as response:
            tag = json.load(response).get("tag_name")
    except (OSError, ValueError, AttributeError):
        return None
    return tag if parse_version(tag) else None


def check_for_update(app_dir: str, latest=latest_release_tag):
    tag = latest()
    return tag if tag and is_newer(tag, read_version(app_dir)) else None


def log(home: str, message: str):
    try:
        os.makedirs(os.path.join(home, "data"), exist_ok=True)
        with open(os.path.join(home, "data", "app.log"), "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except OSError:
        pass


def extract_release_zip(data: bytes, dest: str):
    """GitHub 소스 zip은 맨 위에 "저장소-버전/" 폴더가 있어서, 그 아래 내용만 dest에 풉니다."""
    root = os.path.abspath(dest)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            parts = info.filename.split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue
            target = os.path.abspath(os.path.join(root, *parts[1].split("/")))
            if not target.startswith(root + os.sep):
                raise ValueError(f"zip 안에 잘못된 경로가 있어요: {info.filename}")
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def download_release(tag: str, dest: str, opener=urllib.request.urlopen, timeout: float = 60):
    request = urllib.request.Request(ZIP_URL.format(repo=REPO, tag=tag), headers=HEADERS)
    with opener(request, timeout=timeout) as response:
        data = response.read()
    extract_release_zip(data, dest)


def uv_env(home: str) -> dict:
    """uv가 쓰는 Python·임시 파일·라이브러리를 모두 설치 폴더 안에 둡니다 (제거할 때 남지 않게)."""
    env = dict(os.environ)
    env.update(
        UV_PYTHON_INSTALL_DIR=os.path.join(home, "python"),
        UV_CACHE_DIR=os.path.join(home, "cache"),
        UV_PROJECT_ENVIRONMENT=os.path.join(home, ".venv"),
        UV_PYTHON_PREFERENCE="only-managed",
    )
    return env


def uv_sync(home: str, project: str):
    subprocess.run(
        [os.path.join(home, "uv.exe"), "sync", "--frozen", "--no-dev", "--project", project],
        env=uv_env(home), check=True, timeout=900, capture_output=True, creationflags=CREATE_NO_WINDOW,
    )


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def deps_changed(old_lock: str, new_lock: str) -> bool:
    """라이브러리 목록이 바뀌었는지. 이 프로그램 자신의 버전 숫자만 바뀐 건 무시합니다."""
    own = re.compile(r'(name = "download-organizer"\r?\nversion = )"[^"]*"')
    return own.sub(r'\1""', old_lock) != own.sub(r'\1""', new_lock)


def _rename(src: str, dst: str):
    for attempt in range(RENAME_RETRIES):
        try:
            os.rename(src, dst)
            return
        except PermissionError:
            if attempt == RENAME_RETRIES - 1:
                raise
            time.sleep(RENAME_RETRY_DELAY)


def instance_running(wait: float = 0.0) -> bool:
    """프로그램이 켜져 있는지. wait초 동안은 꺼지기를 기다립니다 (업데이트 후 다시 시작할 때)."""
    import single_instance

    handle = single_instance.acquire(INSTANCE_NAME, wait=wait)
    if handle is None:
        return True
    single_instance.release(handle)
    return False


def acquire_update_lock():
    """다른 launcher가 업데이트 중이면 None."""
    import single_instance

    return single_instance.acquire(UPDATE_LOCK_NAME)


def release_update_lock(handle):
    import single_instance

    single_instance.release(handle)


def apply_update(home: str, tag: str, download=download_release, sync=uv_sync) -> bool:
    app, new, old = (os.path.join(home, name) for name in ("app", "app.new", "app.old"))
    # 지난번 교체 도중 꺼졌다면 먼저 되살립니다.
    if not os.path.isdir(app) and os.path.isdir(old):
        _rename(old, app)
    for leftover in (new, old):
        shutil.rmtree(leftover, ignore_errors=True)
    try:
        download(tag, new)
        if deps_changed(_read(os.path.join(app, "uv.lock")), _read(os.path.join(new, "uv.lock"))):
            sync(home, new)
        _rename(app, old)
        try:
            _rename(new, app)
        except OSError:
            _rename(old, app)
            raise
        shutil.rmtree(old, ignore_errors=True)
        shutil.copy2(os.path.join(app, "launcher.py"), os.path.join(home, "launcher.py"))
        log(home, f"{tag}(으)로 업데이트했어요.")
        return True
    except Exception as e:
        shutil.rmtree(new, ignore_errors=True)
        log(home, f"{tag} 업데이트에 실패해서 지금 버전을 그대로 써요: {e}")
        return False


def launch(home: str, args, popen=subprocess.Popen, latest=latest_release_tag, update=apply_update,
           running=instance_running, update_lock=acquire_update_lock, release_lock=release_update_lock):
    """새 버전이 있으면 바꿔 끼운 뒤 프로그램을 켭니다. --dry-run이면 켜지 않고 실행할 명령만 보여줍니다.
    프로그램이 켜져 있거나 다른 launcher가 업데이트 중이면 업데이트는 건너뜁니다
    (켜져 있는 프로그램이 쓰는 파일은 바꿀 수 없고, 둘이 동시에 바꾸면 설치가 망가지므로)."""
    app = os.path.join(home, "app")
    try:
        if running(10 if "--restarted" in args else 0):
            log(home, "프로그램이 켜져 있어서 업데이트는 다음에 켤 때 할게요.")
        else:
            lock = update_lock()
            if lock is None:
                log(home, "다른 창에서 업데이트하는 중이라 이번에는 건너뛸게요.")
            else:
                try:
                    tag = latest()
                    if tag and is_newer(tag, read_version(app)):
                        update(home, tag)
                finally:
                    release_lock(lock)
    except Exception as e:
        log(home, f"업데이트를 확인하지 못했어요: {e}")
    command = [os.path.join(home, ".venv", "Scripts", "pythonw.exe"), os.path.join(app, "main.py"), *args]
    if "--dry-run" in args:
        print(" ".join(command))
        return command
    popen(command, cwd=app)
    return command

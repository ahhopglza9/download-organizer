# -*- coding: utf-8 -*-
"""다운로드 폴더를 감시하다가, 다운로드가 끝난 파일을 알려줍니다."""

import os
import threading
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import config


def should_ignore_file(path: str) -> bool:
    name = os.path.basename(path).lower()
    return (
        name.endswith(config.TEMP_DOWNLOAD_EXTENSIONS)
        or name in config.IGNORE_FILE_NAMES
        or name.startswith("~$")  # 오피스 문서를 열면 생기는 잠금 파일
    )


def wait_until_download_complete(path: str, interval: float = config.STABLE_CHECK_INTERVAL,
                                 timeout: float = config.STABLE_WAIT_TIMEOUT) -> bool:
    """크기가 0보다 크고 연속 두 번 같으면 다운로드가 끝난 것으로 봅니다.
    파일이 사라지거나, Firefox의 빈 자리표시자이거나, 시간 안에 안 끝나면 False."""
    deadline = time.time() + timeout
    last_size = -1
    while time.time() < deadline:
        time.sleep(interval)
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size == 0:
            # Firefox는 최종 이름의 빈 파일을 먼저 만들고 내용은 ".part"에 받습니다.
            # 다운로드가 끝나면 이름 변경 이벤트가 다시 오므로 여기서는 건너뜁니다.
            if os.path.exists(path + ".part"):
                return False
        elif size == last_size:
            return True
        last_size = size
    return False


def _spawn_thread(fn):
    threading.Thread(target=fn, daemon=True).start()


class DownloadHandler(FileSystemEventHandler):
    def __init__(self, on_ready, wait_fn=wait_until_download_complete, spawn=None):
        super().__init__()
        self._on_ready = on_ready
        self._wait_fn = wait_fn
        self._spawn = spawn or _spawn_thread
        self._lock = threading.Lock()
        self._recent = {}  # 정규화한 경로 -> 마지막으로 처리한 시각

    def on_created(self, event):
        if not event.is_directory:
            self._maybe_handle(event.src_path)

    def on_moved(self, event):
        # 브라우저가 임시 파일을 최종 이름으로 바꿀 때 들어옵니다.
        if not event.is_directory:
            self._maybe_handle(event.dest_path)

    def _claim(self, path: str) -> bool:
        """최근에 처리한 파일이면 False. 아니면 처리 시각을 기록하고 True."""
        key = os.path.normcase(os.path.abspath(path))
        now = time.time()
        with self._lock:
            self._recent = {k: t for k, t in self._recent.items() if now - t < config.DUPLICATE_EVENT_SECONDS}
            if key in self._recent:
                return False
            self._recent[key] = now
            return True

    def _release(self, path: str):
        with self._lock:
            self._recent.pop(os.path.normcase(os.path.abspath(path)), None)

    def _maybe_handle(self, path: str):
        if should_ignore_file(path) or not self._claim(path):
            return

        def work():
            if self._wait_fn(path):
                self._on_ready(path)
            else:
                # 아직 완성되지 않은 파일(예: Firefox의 빈 자리표시자)이면, 곧 올 이름 변경 이벤트를 받을 수 있게 풉니다.
                self._release(path)

        self._spawn(work)


def start(download_dir: str, on_ready) -> Observer:
    observer = Observer()
    observer.schedule(DownloadHandler(on_ready), download_dir, recursive=False)
    observer.daemon = True
    observer.start()
    return observer

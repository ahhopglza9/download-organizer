# -*- coding: utf-8 -*-
"""다운로드 정리 도구.

파일 다운로드가 끝나면 입력창이 뜹니다. 어디에 둘지 단어나 문장으로 입력하면
이름이 비슷한 폴더와 전에 같은 검색어로 고른 폴더를 추천하고, 폴더를 누르면 파일을 그곳으로 옮깁니다.

실행: python main.py
"""

import os
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import asdict

import webview

import config
import paths
import single_instance
import updater
import watcher
from autostart import autostart_command, set_autostart
from folders import list_folders
from known_folders import default_search_roots
from matcher import Matcher
from memory import Memory
from mover import FolderMissingError, move_file
from settings import Settings, load_settings, save_settings, settings_view
from tray import Tray, TrayStatus, is_watching


class Api:
    """화면(ui/app.js)에서 window.pywebview.api.* 로 부르는 기능과 다운로드 대기열."""

    def __init__(self, matcher, on_folder_missing=None, bring_front=None, memory=None, choose_folder=None,
                 settings_provider=None, settings_saver=None):
        self._matcher = matcher
        self._memory = memory
        self._choose_folder = choose_folder or (lambda window: None)  # 폴더 선택 창. 취소하면 None
        self._on_folder_missing = on_folder_missing or (lambda: None)
        self._bring_front = bring_front or (lambda window: None)
        self._window = None
        self._lock = threading.Lock()
        self._queue = deque()
        self._current = None
        self._shown_id = 0  # 화면에 새 파일을 보여줄 때마다 1씩 늘어나는 번호
        self._quitting = False
        self._settings_provider = settings_provider or (lambda: {"roots": [], "autostart": False, "first_run": False})
        self._settings_saver = settings_saver or (lambda roots, autostart: None)
        self._settings_open = False

    # ---- Python에서 부르는 메서드 ----

    def bind_window(self, window):
        self._window = window

    def open_settings(self):
        """알림 영역 아이콘의 "설정", 또는 첫 실행 때 설정 화면을 띄웁니다."""
        with self._lock:
            self._settings_open = True
        self._run_js("window.app && window.app.showSettings()")
        if self._window is not None:
            self._window.show()
            self._bring_front(self._window)

    def is_settings_open(self) -> bool:
        return self._settings_open

    def dismiss_settings(self):
        """설정 화면에서 창을 닫았을 때. 첫 실행이면 체크된 폴더로 시작하고, 아니면 바꾸지 않고 닫습니다."""
        data = self._settings_provider()
        if data.get("first_run"):
            roots = [r["path"] for r in data.get("roots", []) if r.get("checked")]
            self.save_settings(roots, False)
        else:
            self._close_settings()

    def quit(self):
        """프로그램을 끄는 중이라고 표시합니다. 이때는 창 닫기를 막지 않습니다."""
        self._quitting = True

    def is_quitting(self) -> bool:
        return self._quitting

    def enqueue(self, path: str):
        with self._lock:
            if path == self._current or path in self._queue:
                return
            self._queue.append(path)
            # 비어 있는지 확인과 다음 파일 고르기를 한 번에 해야, 동시에 끝난 두 다운로드 중 하나가 사라지지 않습니다.
            was_idle = self._current is None
            has_file = self._pick_next_locked() if was_idle else True
        if was_idle:
            self._show_current(has_file)
        else:
            self._refresh_ui()

    # ---- 화면에서 부르는 메서드 ----

    def state(self) -> dict:
        with self._lock:
            return {
                "file": os.path.basename(self._current) if self._current else None,
                "pending": len(self._queue),
                "id": self._shown_id,
                "settings_open": self._settings_open,
            }

    def search(self, query: str) -> list:
        return [asdict(r) for r in self._matcher.search(query, config.TOP_N)]

    def move(self, folder: str, query: str = "") -> dict:
        """지금 파일을 folder로 옮기고, 성공하면 검색어(query)로 이 폴더를 골랐다고 기억합니다."""
        with self._lock:
            src = self._current
        if src is None:
            return {"ok": False, "gone": False, "error": "옮길 파일이 없어요."}
        try:
            move_file(src, folder)
        except FileNotFoundError:
            return {"ok": False, "gone": True, "error": "다운로드한 파일이 사라져서 옮길 수 없어요."}
        except FolderMissingError:
            self._on_folder_missing()
            return {"ok": False, "gone": False,
                    "error": "그 폴더가 없어졌어요. 폴더 목록을 새로 읽고 있으니 다른 폴더를 골라 주세요."}
        except OSError as e:
            return {"ok": False, "gone": False,
                    "error": f"옮기지 못했어요. 파일이 다른 프로그램에서 열려 있으면 닫고 다시 눌러 주세요. ({e.strerror or e})"}
        with self._lock:
            if self._current == src:
                self._current = None
        if self._memory is not None:
            self._memory.remember(query, folder)
        return {"ok": True, "folder": os.path.basename(folder.rstrip("\\/")) or folder}

    def get_settings(self) -> dict:
        data = dict(self._settings_provider())
        data["memory_count"] = self._memory.count() if self._memory is not None else 0
        return data

    def add_root(self):
        """폴더 선택 창으로 검색 위치를 하나 더합니다. 취소하면 None."""
        path = self._choose_folder(self._window)
        if not path:
            return None
        return {"path": path, "label": os.path.basename(path.rstrip("\\/")) or path}

    def save_settings(self, roots, autostart) -> dict:
        roots = [r for r in roots if os.path.isdir(r)]
        if not roots:
            return {"ok": False, "error": "찾아볼 폴더를 하나 이상 골라 주세요."}
        self._settings_saver(roots, bool(autostart))
        return self._close_settings()

    def close_settings(self) -> dict:
        return self._close_settings()

    def clear_memory(self) -> int:
        if self._memory is not None:
            self._memory.clear()
        return 0

    def pick_folder(self, query: str = "") -> dict:
        """폴더 선택 창을 띄워 직접 고른 폴더로 옮깁니다. 취소하면 아무것도 하지 않습니다."""
        folder = self._choose_folder(self._window)
        if not folder:
            return {"ok": False, "cancelled": True}
        return self.move(folder, query)

    def next_file(self, expected_id=None):
        """다음 파일로 넘어갑니다. expected_id가 지금 화면의 번호와 다르면(그사이 다른 파일이 떴으면) 무시합니다."""
        with self._lock:
            if expected_id is not None and expected_id != self._shown_id:
                return
            has_file = self._pick_next_locked()
        self._show_current(has_file)

    # ---- 내부 ----

    def _pick_next_locked(self) -> bool:
        """대기열에서 아직 있는 다음 파일을 고릅니다. self._lock을 잡은 채로 불러야 합니다."""
        self._current = None
        while self._queue:
            path = self._queue.popleft()
            if os.path.isfile(path):
                self._current = path
                break
        self._shown_id += 1
        return self._current is not None

    def _show_current(self, has_file: bool):
        if self._window is None:
            return
        if has_file:
            self._refresh_ui(new_file=True)
            self._window.show()
            self._bring_front(self._window)
        elif not self._settings_open:
            self._window.hide()

    def _run_js(self, code: str):
        if self._window is None:
            return
        try:
            self._window.run_js(code)
        except Exception:
            pass  # 화면이 아직 로딩 중이면 화면 쪽에서 준비될 때 직접 상태를 읽습니다.

    def _refresh_ui(self, new_file=False):
        """화면에 상태를 다시 읽으라고 알립니다. new_file이면 입력과 결과도 비웁니다."""
        self._run_js(f"window.app && window.app.refresh({'true' if new_file else 'false'})")

    def _close_settings(self) -> dict:
        with self._lock:
            self._settings_open = False
            has_file = self._current is not None
        self._run_js(f"window.app && window.app.closeSettings({'true' if has_file else 'false'})")
        if not has_file and self._window is not None:
            self._window.hide()
        return {"ok": True, "has_file": has_file}


def make_closing_handler(api):
    """창의 닫기 버튼 처리. 프로그램을 끄지 않고, 지금 파일은 다운로드 폴더에 둔 채 다음 파일로 넘어갑니다.
    pywebview는 이 함수가 끝날 때까지 화면 스레드를 멈추고 기다리므로, 화면을 다시 그리는
    일(run_js)은 다른 스레드에서 해야 프로그램이 멈추지 않습니다."""
    def on_closing():
        if api.is_quitting():
            return True  # 알림 영역 아이콘의 "끄기"로 끄는 중
        if api.is_settings_open():
            threading.Thread(target=api.dismiss_settings, daemon=True).start()
            return False
        threading.Thread(target=api.next_file, daemon=True).start()
        return False
    return on_closing


class _Tee:
    """콘솔과 로그 파일에 함께 씁니다."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, text):
        for s in self._streams:
            s.write(text)

    def flush(self):
        for s in self._streams:
            s.flush()


def setup_logging(path: str):
    """print로 남기는 안내와 오류를 로그 파일에 남깁니다. 콘솔 창이 없을 때(pythonw)는 파일에만 씁니다.
    파일이 1MB를 넘으면 이전 기록은 .old로 옮기고 새로 시작합니다."""
    try:
        if os.path.getsize(path) > 1_000_000:
            os.replace(path, path + ".old")
    except OSError:
        pass
    log = open(path, "a", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.stdout, log) if sys.stdout else log
    sys.stderr = _Tee(sys.stderr, log) if sys.stderr else log


def show_message(text: str):
    """콘솔 창이 없어도 보이도록 Windows 메시지 창을 띄웁니다."""
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, text, "다운로드 정리", 0x40)


def bring_to_front(window):
    """창을 맨 앞으로 가져와서 바로 입력할 수 있게 합니다.
    - Windows는 백그라운드 프로그램이 다른 창(브라우저 등)의 키보드 입력을 가져가는 걸 막습니다.
      Alt 키를 누른 상태에서는 사용자가 창을 바꾸는 중(Alt+Tab)으로 보고 허용합니다.
    - pywebview는 창을 처음 보여줄 때만 안쪽 화면(웹뷰)에 키보드 입력을 주므로, 매번 직접 줍니다."""
    import ctypes
    from System import Action

    user32 = ctypes.windll.user32
    VK_MENU, KEYEVENTF_KEYUP = 0x12, 0x2
    form = window.native

    def run():
        hwnd = form.Handle.ToInt32()
        user32.keybd_event(VK_MENU, 0, 0, 0)
        try:
            user32.SetForegroundWindow(hwnd)
        finally:
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        form.browser.webview.Focus()
        if user32.GetForegroundWindow() != hwnd:
            print("[알림] 입력창을 맨 앞으로 가져오지 못했어요. 창을 한 번 클릭해 주세요.")

    try:
        form.Invoke(Action(run))
        window.run_js("window.app && window.app.focusInput()")
    except Exception as e:
        print(f"[알림] 입력창에 포커스를 주지 못했어요: {e}")


UI_INDEX = os.path.join(config.PROGRAM_DIR, "ui", "index.html")


def choose_folder(window):
    """Windows 폴더 선택 창을 띄웁니다. 고른 폴더 경로를, 취소하면 None을 돌려줍니다."""
    result = window.create_file_dialog(webview.FileDialog.FOLDER, directory=config.PICK_FOLDER_START)
    return result[0] if result else None


def pythonw_path() -> str:
    """지금 실행 중인 Python과 같은 폴더의 pythonw.exe (콘솔 창 없이 실행)."""
    return os.path.join(os.path.dirname(sys.executable), "pythonw.exe")


def main():
    args = sys.argv[1:]
    setup_logging(config.LOG_FILE)
    instance = single_instance.acquire(config.INSTANCE_NAME, wait=10 if "--restarted" in args else 0)
    if instance is None:
        show_message("다운로드 정리가 이미 실행 중이에요.\n작업 표시줄 오른쪽 아래(시계 옆) 아이콘을 확인해 주세요.")
        return
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 다운로드 정리를 시작해요. ({' '.join(args) or '직접 실행'})")
    if paths.migrate_legacy_file(config.LEGACY_MEMORY_FILE, config.MEMORY_FILE):
        print(f"예전 기억 파일을 옮겼어요: {config.MEMORY_FILE}")
    if not os.path.isdir(config.DOWNLOAD_FOLDER):
        show_message(f"다운로드 폴더를 찾을 수 없어요:\n{config.DOWNLOAD_FOLDER}")
        return

    memory = Memory(config.MEMORY_FILE)
    state = {"settings": load_settings(config.SETTINGS_FILE), "observer": None}
    matcher = Matcher(state["settings"].existing_roots(), memory=memory)
    exclude = [config.DOWNLOAD_FOLDER, config.PROGRAM_DIR, config.APP_HOME]
    watch_lock = threading.Lock()

    def refresh_folders():
        roots = state["settings"].existing_roots()
        try:
            matcher.set_roots(roots)
            matcher.set_folders(list_folders(roots, exclude))
        except Exception as e:
            print(f"폴더 목록을 읽지 못했어요: {e}")

    def refresh_loop():
        while not api.is_quitting():
            refresh_folders()
            time.sleep(config.FOLDER_REFRESH_SECONDS)

    def refresh_now():
        threading.Thread(target=refresh_folders, daemon=True).start()

    def provide_settings():
        return settings_view(state["settings"], default_search_roots())

    def save(roots, autostart):
        settings = Settings(search_roots=list(roots), autostart=autostart, setup_done=True)
        save_settings(config.SETTINGS_FILE, settings)
        state["settings"] = settings
        try:
            set_autostart(autostart, autostart_command(config.PROGRAM_DIR, config.APP_HOME, pythonw_path()))
        except OSError as e:
            print(f"[알림] 자동 실행 설정을 바꾸지 못했어요: {e}")
        print(f"설정을 저장했어요. 검색 위치 {len(roots)}곳, 자동 실행 {'켬' if autostart else '끔'}")
        refresh_now()
        start_watching()

    api = Api(matcher, on_folder_missing=refresh_now, bring_front=bring_to_front,
              memory=memory, choose_folder=choose_folder,
              settings_provider=provide_settings, settings_saver=save)
    window = webview.create_window(
        "어디에 둘까요", UI_INDEX, js_api=api,
        width=config.WINDOW_WIDTH, height=config.WINDOW_HEIGHT,
        resizable=False, on_top=True, hidden=True,
    )
    api.bind_window(window)
    window.events.closing += make_closing_handler(api)

    status = TrayStatus()

    def quit_app():
        print(f"[{time.strftime('%H:%M:%S')}] 끄기를 눌러서 종료해요.")
        api.quit()
        tray.stop()
        window.destroy()

    def restart_for_update():
        print(f"[{time.strftime('%H:%M:%S')}] 업데이트하려고 다시 시작해요.")
        subprocess.Popen([pythonw_path(), os.path.join(config.APP_HOME, "launcher.py"), "--restarted"],
                         cwd=config.APP_HOME)
        quit_app()

    tray = Tray(status, on_settings=api.open_settings, on_update=restart_for_update, on_quit=quit_app)

    def on_download(path):
        print(f"[{time.strftime('%H:%M:%S')}] 다운로드 감지: {path}")
        status.detected(path)
        tray.refresh()
        api.enqueue(path)

    def health_loop(observer):
        # 감시가 멈추거나 다운로드 폴더가 사라지면 아이콘에 빨간 점을 띄웁니다.
        while not api.is_quitting():
            ok = is_watching(observer, config.DOWNLOAD_FOLDER)
            if status.alert == ok:
                print(f"[{time.strftime('%H:%M:%S')}] 감시 상태: {'정상' if ok else '멈춤'}")
            status.set_watching(ok)
            tray.refresh()
            time.sleep(config.HEALTH_CHECK_SECONDS)

    def start_watching():
        """첫 설정을 마친 뒤 한 번만 감시를 시작합니다."""
        with watch_lock:
            if state["observer"] is not None:
                return
            observer = watcher.start(config.DOWNLOAD_FOLDER, on_download)
            state["observer"] = observer
        threading.Thread(target=refresh_loop, daemon=True).start()
        threading.Thread(target=health_loop, args=(observer,), daemon=True).start()
        print(f"감시 폴더: {config.DOWNLOAD_FOLDER}")
        for r in state["settings"].existing_roots():
            print(f"검색 위치: {r}")

    def update_loop():
        time.sleep(60)
        while not api.is_quitting():
            tag = updater.check_for_update(config.PROGRAM_DIR)
            if tag and not status.update_available:
                print(f"[{time.strftime('%H:%M:%S')}] 새 버전이 있어요: {tag}")
                status.set_update_available(True)
                tray.refresh()
                tray.notify("새 버전이 있어요.\n아이콘 메뉴의 '업데이트하고 다시 시작'을 누르거나, 다음에 켤 때 적용돼요.")
            time.sleep(config.UPDATE_CHECK_SECONDS)

    def startup():
        tray.start()
        if config.IS_INSTALLED:
            threading.Thread(target=update_loop, daemon=True).start()
        if not state["settings"].setup_done:
            api.open_settings()
            return
        start_watching()
        if "--autostart" not in args and "--restarted" not in args:
            time.sleep(1)  # 아이콘이 자리 잡은 뒤에 알림을 띄웁니다
            tray.notify("다운로드 폴더를 지켜보고 있어요.\n파일을 받으면 어디에 둘지 물어볼게요.")

    webview.start(startup)
    single_instance.release(instance)


if __name__ == "__main__":
    main()

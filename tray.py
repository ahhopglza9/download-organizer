# -*- coding: utf-8 -*-
"""작업 표시줄 알림 영역(시계 옆) 아이콘.
콘솔 창 없이도 프로그램이 다운로드 폴더를 지켜보고 있는지 알 수 있게 합니다.
- 마우스를 올리면: 지켜보는 중인지, 마지막으로 감지한 파일
- 감시가 멈추면: 아이콘에 빨간 점
- 우클릭: 설정, (새 버전이 있으면) 업데이트하고 다시 시작, 끄기"""

import os
import threading
import time

from PIL import Image, ImageDraw

_TOOLTIP_LIMIT = 127  # Windows 알림 영역 툴팁 최대 글자 수

# 입력창(ui/style.css)과 같은 색인 카드 색
_PAPER = (250, 252, 255, 255)
_RULE = (120, 160, 210, 255)
_MARGIN = (224, 96, 90, 255)
_INK = (30, 42, 59, 255)
_ALERT = (220, 40, 35, 255)


def make_icon_image(alert: bool = False) -> Image.Image:
    """64×64 색인 카드 아이콘. 작게 줄어도 보이도록 굵은 선으로 그립니다. alert면 오른쪽 아래에 빨간 점."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 10, 60, 54), radius=6, fill=_PAPER, outline=_INK, width=3)
    for y in (24, 34, 44):
        d.line((10, y, 54, y), fill=_RULE, width=3)
    d.line((18, 13, 18, 51), fill=_MARGIN, width=3)
    if alert:
        d.ellipse((40, 40, 64, 64), fill=(255, 255, 255, 255))
        d.ellipse((43, 43, 61, 61), fill=_ALERT)
    return img


def _clock(hour: int, minute: int) -> str:
    half = "오전" if hour < 12 else "오후"
    return f"{half} {hour % 12 or 12}:{minute:02d}"


class TrayStatus:
    """아이콘에 보여줄 상태. 감시 스레드와 다운로드 감지 스레드에서 함께 바뀝니다."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last = None  # (시, 분, 파일 이름)
        self.alert = False
        self.update_available = False

    def detected(self, path: str, now=None):
        if now is None:
            t = time.localtime()
            now = (t.tm_hour, t.tm_min)
        with self._lock:
            self._last = (now[0], now[1], os.path.basename(path))

    def set_watching(self, ok: bool):
        self.alert = not ok

    def set_update_available(self, available: bool):
        self.update_available = available

    def tooltip(self) -> str:
        if self.alert:
            return "다운로드 정리 – 지켜보지 못하고 있어요\n프로그램을 다시 켜 주세요"
        head = "다운로드 정리 – 지켜보는 중\n마지막 감지: "
        with self._lock:
            last = self._last
        if last is None:
            return head + "아직 없음"
        prefix = head + _clock(last[0], last[1]) + " "
        name = last[2]
        room = _TOOLTIP_LIMIT - len(prefix)
        if len(name) > room:
            name = name[: room - 1] + "…"
        return prefix + name


def is_watching(observer, download_folder: str) -> bool:
    """다운로드 감시가 살아 있고, 다운로드 폴더가 그대로 있는지."""
    return observer.is_alive() and os.path.isdir(download_folder)


class Tray:
    def __init__(self, status: TrayStatus, on_settings, on_update, on_quit):
        import pystray

        self._status = status
        self._images = {False: make_icon_image(False), True: make_icon_image(True)}
        self._shown = (status.alert, status.tooltip(), status.update_available)
        self._lock = threading.Lock()
        menu = pystray.Menu(
            pystray.MenuItem("설정", lambda icon, item: on_settings()),
            pystray.MenuItem("업데이트하고 다시 시작", lambda icon, item: on_update(),
                             visible=lambda item: status.update_available),
            pystray.MenuItem("끄기", lambda icon, item: on_quit()),
        )
        self._icon = pystray.Icon("DownloadOrganizer", self._images[status.alert], status.tooltip(), menu)

    def start(self):
        self._icon.run_detached()

    def refresh(self):
        """상태가 바뀌었을 때만 아이콘·툴팁·메뉴를 다시 그립니다."""
        current = (self._status.alert, self._status.tooltip(), self._status.update_available)
        with self._lock:
            if current == self._shown:
                return
            previous, self._shown = self._shown, current
            self._icon.icon = self._images[current[0]]
            self._icon.title = current[1]
            if previous[2] != current[2]:
                self._icon.update_menu()

    def notify(self, message: str, title: str = "다운로드 정리"):
        try:
            self._icon.notify(message, title)
        except Exception as e:
            print(f"[알림] 알림을 띄우지 못했어요: {e}")

    def stop(self):
        self._icon.stop()

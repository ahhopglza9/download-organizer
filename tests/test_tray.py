import os

from tray import TrayStatus, is_watching, make_icon_image


def test_tooltip_before_any_download():
    s = TrayStatus()
    assert s.tooltip() == "다운로드 정리 – 지켜보는 중\n마지막 감지: 아직 없음"
    assert s.alert is False


def test_tooltip_shows_last_detected_file():
    s = TrayStatus()
    s.detected(r"C:\Users\x\Downloads\week3_과제.zip", now=(15, 42))
    assert s.tooltip() == "다운로드 정리 – 지켜보는 중\n마지막 감지: 오후 3:42 week3_과제.zip"


def test_morning_time_is_shown_as_am():
    s = TrayStatus()
    s.detected(r"C:\d\a.pdf", now=(0, 5))
    assert "오전 12:05 a.pdf" in s.tooltip()


def test_tooltip_is_short_enough_for_windows():
    s = TrayStatus()
    s.detected("C:/d/" + "아주긴파일이름" * 30 + ".pdf", now=(9, 0))
    assert len(s.tooltip()) <= 127


def test_alert_when_not_watching():
    s = TrayStatus()
    s.set_watching(False)
    assert s.alert is True
    assert s.tooltip() == "다운로드 정리 – 지켜보지 못하고 있어요\n프로그램을 다시 켜 주세요"
    s.set_watching(True)
    assert s.alert is False


class FakeObserver:
    def __init__(self, alive):
        self._alive = alive

    def is_alive(self):
        return self._alive


def test_is_watching(tmp_path):
    assert is_watching(FakeObserver(True), str(tmp_path))
    assert not is_watching(FakeObserver(False), str(tmp_path))
    assert not is_watching(FakeObserver(True), str(tmp_path / "없음"))


def test_icon_image_has_red_dot_only_when_alert():
    normal = make_icon_image(alert=False)
    alert = make_icon_image(alert=True)
    assert normal.size == (64, 64)
    dot = (52, 52)
    r, g, b, a = alert.getpixel(dot)
    assert a == 255 and r > 180 and g < 90 and b < 90
    assert normal.getpixel(dot) != alert.getpixel(dot)


def test_update_flag():
    s = TrayStatus()
    assert s.update_available is False
    s.set_update_available(True)
    assert s.update_available is True

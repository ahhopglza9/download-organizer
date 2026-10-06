# -*- coding: utf-8 -*-
"""다운로드 정리 도구 설정값. 검색할 폴더와 자동 실행은 설정 화면(data 폴더의 settings.json)에서 정합니다."""

import os
from pathlib import Path

import known_folders
import paths

# 이 프로그램이 있는 폴더 (추천 후보에서 제외합니다)
PROGRAM_DIR = os.path.dirname(os.path.abspath(__file__))

# 설치 위치와 사용자 데이터 폴더 (업데이트해도 data 폴더는 그대로 남습니다)
APP_HOME = paths.app_home()
DATA_DIR = paths.data_dir()
# 설치된 프로그램으로 실행 중인지 (개발용으로 저장소 폴더에서 실행하면 False)
IS_INSTALLED = os.path.normcase(PROGRAM_DIR) == os.path.normcase(os.path.join(APP_HOME, "app"))
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# 감시할 다운로드 폴더
DOWNLOAD_FOLDER = known_folders.known_folder("downloads") or str(Path.home() / "Downloads")

# 이 이름과 정확히 같은 폴더는 하위 폴더까지 전부 후보에서 제외합니다.
# 이름이 "."으로 시작하는 숨김 폴더(.git, .venv 등)도 모두 제외합니다.
IGNORE_FOLDER_NAMES = {
    "node_modules", "__pycache__", "venv", "site-packages", "dist-packages",
    "AppData", "$RECYCLE.BIN", "System Volume Information",
}

# 이 이름(대소문자 무시)의 폴더는 옮길 곳으로 추천하지 않습니다.
EXCLUDE_AS_DESTINATION_NAMES = {"다운로드", "downloads", "download"}

# 폴더 목록을 다시 훑는 간격(초). 새로 만든 폴더가 이 시간 안에 추천에 나타납니다.
FOLDER_REFRESH_SECONDS = 300

# 브라우저가 다운로드 중에 만드는 임시 파일 확장자
TEMP_DOWNLOAD_EXTENSIONS = (".crdownload", ".tmp", ".part", ".partial", ".download")
# 정리 대상이 아닌 시스템 파일 이름
IGNORE_FILE_NAMES = {"desktop.ini", "thumbs.db"}

# 다운로드 완료 판단: 이 간격(초)으로 크기를 확인하고, 이 시간(초) 안에 안 끝나면 건너뜁니다.
STABLE_CHECK_INTERVAL = 1.0
STABLE_WAIT_TIMEOUT = 600
# 같은 파일 이벤트가 이 시간(초) 안에 다시 오면 무시합니다.
DUPLICATE_EVENT_SECONDS = 3.0

# 입력이 폴더 이름의 줄임말이거나 그 반대일 때(예: "공학수학2" ↔ "공수2")의 글자 점수.
# 글자가 그대로 들어 있을 때(1.0)보다 조금 낮게 둡니다.
ABBREVIATION_SCORE = 0.9
# "다른 폴더 고르기" 창이 처음 여는 위치
PICK_FOLDER_START = known_folders.known_folder("documents") or str(Path.home() / "Documents")

# 검색어마다 고른 폴더를 기억하는 파일
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")
# 예전 버전이 쓰던 위치 (처음 한 번 새 위치로 복사합니다)
LEGACY_MEMORY_FILE = os.path.join(PROGRAM_DIR, "memory.json")
# 기억된 검색어의 단어가 입력에 모두 들어 있을 때의 점수 (같은 검색어면 1.0)
MEMORY_PARTIAL_SCORE = 0.9
# 이 점수 미만인 폴더는 추천하지 않습니다. 엉뚱한 추천이 많으면 올리고, 너무 안 나오면 내리세요.
MIN_SCORE = 0.2
# 보여줄 추천 폴더 수
TOP_N = 5

# 안내와 오류를 남기는 파일 (콘솔 창 없이 실행할 때 문제를 찾는 데 씁니다)
LOG_FILE = os.path.join(DATA_DIR, "app.log")
# 두 번 켜지지 않게 하는 이름
INSTANCE_NAME = r"Local\DownloadOrganizer"
# 다운로드 감시가 살아 있는지 확인하는 간격(초)
HEALTH_CHECK_SECONDS = 5
# 실행 중 새 배포 버전을 확인하는 간격(초) — 하루
UPDATE_CHECK_SECONDS = 24 * 60 * 60

# 입력창 크기
WINDOW_WIDTH = 520
WINDOW_HEIGHT = 520

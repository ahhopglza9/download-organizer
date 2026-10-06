# -*- coding: utf-8 -*-
"""바로가기와 자동 실행이 여는 파일. 새 배포 버전이 있으면 받은 뒤 프로그램을 켭니다.
설치 폴더 맨 위에 복사돼 있고, 업데이트할 때마다 새 것으로 바뀝니다."""

import os
import sys

HOME = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HOME, "app")
OLD = os.path.join(HOME, "app.old")

# 지난번 업데이트가 폴더를 바꿔 끼우는 도중에 멈췄다면 이전 버전을 되살립니다.
if not os.path.isdir(APP) and os.path.isdir(OLD):
    try:
        os.rename(OLD, APP)
    except OSError:
        pass
sys.path.insert(0, APP)

import updater  # noqa: E402

if __name__ == "__main__":
    updater.launch(HOME, sys.argv[1:])

# -*- coding: utf-8 -*-
"""새 버전을 배포합니다.

    python release.py 1.1.0

1. 커밋 안 한 변경이 없고 테스트가 모두 통과하는지 확인합니다.
2. pyproject.toml 버전을 바꾸고 uv.lock을 갱신해 커밋, v1.1.0 태그를 만듭니다.
3. GitHub에 올리고 배포 버전을 만들며 설치 파일을 첨부합니다.
그 순간부터 사용자 프로그램이 켤 때(또는 하루 안에) 새 버전을 받아 갑니다."""

import re
import subprocess
import sys

from updater import parse_version, read_version

PYPROJECT = "pyproject.toml"
ASSETS = ["installer/DownloadOrganizer-Setup.cmd", "installer/install.ps1"]
INSTALL_SCRIPT = "installer/install.ps1"


def check_new_version(new: str, current: str):
    if new.startswith("v") or parse_version(new) is None:
        raise ValueError("버전은 1.2.3 형식으로 적어 주세요 (앞에 v 없이).")
    if parse_version(new) <= parse_version(current):
        raise ValueError(f"새 버전({new})은 지금 버전({current})보다 커야 해요.")


def set_version(text: str, new: str) -> str:
    updated, count = re.subn(r'(?m)^version\s*=\s*"[^"]*"', f'version = "{new}"', text, count=1)
    if count != 1:
        raise ValueError("pyproject.toml에서 version 줄을 찾지 못했어요.")
    return updated


def pinned_uv_version(install_script: str) -> str:
    """사용자 컴퓨터에 설치되는 uv 버전 (install.ps1의 $UvVersion)."""
    m = re.search(r"\$UvVersion = '([^']+)'", install_script)
    if not m:
        raise ValueError("install.ps1에서 $UvVersion을 찾지 못했어요.")
    return m.group(1)


def check_uv_version(uv_version_output: str, pinned: str):
    """작성자 컴퓨터의 uv가 사용자에게 설치되는 uv와 같은 버전인지 확인합니다.
    다르면 uv.lock 형식이 달라져 사용자 컴퓨터의 업데이트가 실패할 수 있어요."""
    found = uv_version_output.split()[1] if len(uv_version_output.split()) > 1 else ""
    if found != pinned:
        raise ValueError(f"이 컴퓨터의 uv({found})가 사용자에게 설치되는 uv({pinned})와 달라요. "
                         f"python -m pip install uv=={pinned} 로 맞춘 뒤 다시 실행해 주세요.")


def run(*command):
    print("$", " ".join(command))
    subprocess.run(command, check=True)


def main(argv) -> int:
    if len(argv) != 2:
        print("사용법: python release.py 1.2.3")
        return 2
    new = argv[1]
    try:
        check_new_version(new, read_version("."))
    except ValueError as e:
        print(e)
        return 1
    try:
        with open(INSTALL_SCRIPT, encoding="utf-8-sig") as f:
            pinned = pinned_uv_version(f.read())
        uv = subprocess.run([sys.executable, "-m", "uv", "--version"], capture_output=True, text=True, check=True)
        check_uv_version(uv.stdout.strip(), pinned)
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        print(e)
        return 1
    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    if status.stdout.strip():
        print("커밋하지 않은 변경이 있어요. 먼저 커밋해 주세요.")
        return 1
    if subprocess.run([sys.executable, "-m", "pytest", "-q"]).returncode != 0:
        print("테스트가 실패해서 배포하지 않았어요.")
        return 1

    with open(PYPROJECT, encoding="utf-8") as f:
        text = f.read()
    with open(PYPROJECT, "w", encoding="utf-8") as f:
        f.write(set_version(text, new))
    run(sys.executable, "-m", "uv", "lock")
    run("git", "add", PYPROJECT, "uv.lock")
    run("git", "commit", "-m", f"v{new} 배포")
    run("git", "tag", f"v{new}")
    run("git", "push", "origin", "main", f"v{new}")
    run("gh", "release", "create", f"v{new}", *ASSETS, "--title", f"v{new}", "--generate-notes")
    print(f"v{new}을(를) 배포했어요. 사용자 프로그램이 다음에 켤 때(또는 하루 안에) 받아 가요.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

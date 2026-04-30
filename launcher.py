#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
카카오 이모티콘 다운로더 - 대화형 런처
모든 UI와 흐름을 Python에서 처리 (bat 인코딩 문제 완전 회피)
"""

import sys
import io
import os
import subprocess
import pathlib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = pathlib.Path(__file__).parent


def clear():
    os.system("cls")


def banner():
    print("=" * 50)
    print("  카카오 이모티콘 다운로더 v3.0")
    print("  Kakao Emoticon Downloader")
    print("=" * 50)
    print()


def ensure_package(package: str, import_name: str = None):
    """pip 자동 설치."""
    name = import_name or package
    try:
        __import__(name)
    except ImportError:
        print(f"  [{package}] 패키지 설치 중...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package, "-q"],
            check=True
        )
        print(f"  [{package}] 설치 완료")


def run_download(url: str, outdir: str) -> bool:
    """kakao_downloader.py 실행."""
    script = SCRIPT_DIR / "kakao_downloader.py"
    result = subprocess.run(
        [sys.executable, str(script), url, "--output", outdir],
        cwd=str(SCRIPT_DIR),
    )
    return result.returncode == 0


def run_convert(outdir: str):
    """convert.py 실행."""
    script = SCRIPT_DIR / "convert.py"
    subprocess.run(
        [sys.executable, str(script), outdir],
        cwd=str(SCRIPT_DIR),
    )


def ask_yn(prompt: str) -> bool:
    while True:
        try:
            ans = input(prompt).strip().upper()
            if ans in ("Y", "YES", ""):
                return True
            if ans in ("N", "NO"):
                return False
            print("  Y 또는 N을 입력하세요.")
        except (EOFError, KeyboardInterrupt):
            return False


def main():
    # 필수 패키지 확인
    ensure_package("httpx")

    while True:
        clear()
        banner()

        print("  지원 URL 형식:")
        print("    1) https://e.kakao.com/t/이모티콘-이름")
        print("    2) https://emoticon.kakao.com/items/XXXXX  (카톡 공유 링크)")
        print()

        # URL 입력
        url = ""
        while not url:
            try:
                url = input("  다운로드할 URL 입력: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  종료합니다.")
                return
            if not url:
                print("  URL을 입력해주세요.")

        # 출력 폴더
        try:
            outdir = input("  저장 폴더 (Enter = output): ").strip()
        except (EOFError, KeyboardInterrupt):
            outdir = ""
        if not outdir:
            outdir = "output"

        print()
        print("-" * 50)
        print("  다운로드 시작...")
        print(f"  URL: {url}")
        print(f"  폴더: {outdir}")
        print("-" * 50)
        print()

        # 다운로드 실행
        success = run_download(url, outdir)

        print()
        if not success:
            print("  [실패] 다운로드 중 오류가 발생했습니다.")
        else:
            print("  [완료] 다운로드 성공!")
            print()

            # 변환 (convert.py가 자동 감지 후 질문)
            ensure_package("Pillow", "PIL")
            print("-" * 50)
            print("  파일 분석 중...")
            print("-" * 50)
            run_convert(outdir)

        print()
        print("-" * 50)
        if not ask_yn("  다른 이모티콘을 다운로드하시겠습니까? (Y/N): "):
            break

    print()
    print("  프로그램을 종료합니다. 감사합니다!")
    input("  Enter 키를 누르면 닫힙니다...")


if __name__ == "__main__":
    main()

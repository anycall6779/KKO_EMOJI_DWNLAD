#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebP → GIF 변환기 (최고 품질)
================================
- 프레임별 독립 팔레트 (256색/프레임) → 최대 색상 보존
- Floyd-Steinberg 디더링 → 색 손실 최소화
- 원본 프레임 타이밍 완전 보존
- 반투명(RGBA) → 흰 배경 합성 후 변환

사용법:
  python webp_to_gif.py <폴더 또는 파일>
  python webp_to_gif.py output/pack-name
  python webp_to_gif.py output/pack-name/001.webp
"""

import sys
import io
import pathlib
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from PIL import Image, ImageSequence
except ImportError:
    print("[오류] Pillow 패키지가 필요합니다: pip install Pillow")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────
# 단일 WebP → GIF 변환
# ─────────────────────────────────────────────────────────────
def convert_one(webp: pathlib.Path, gif: pathlib.Path) -> bool:
    """
    animated WebP 1개를 GIF로 변환.
    프레임별 독립 팔레트 + 디더링으로 최고 품질 구현.
    """
    try:
        src = Image.open(webp)
    except Exception as e:
        print(f"  [FAIL] {webp.name}: 파일 열기 실패 - {e}", flush=True)
        return False

    frames = []
    durations = []

    try:
        for frame in ImageSequence.Iterator(src):
            f = frame.copy()

            # duration 먼저 읽기 (convert 전에)
            dur = f.info.get("duration", 100)
            if dur < 20:
                dur = 100  # 너무 짧으면 보정

            # RGBA로 통일 (WebP는 RGBA 또는 RGB)
            rgba = f.convert("RGBA")

            # 흰 배경과 합성 (GIF는 완전 투명만 지원, 반투명 불가)
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            bg.alpha_composite(rgba)
            rgb = bg.convert("RGB")

            # 프레임별 독립 팔레트 (256색) + Floyd-Steinberg 디더링
            quantized = rgb.quantize(
                colors=256,
                method=Image.Quantize.MEDIANCUT,   # 중간값 컷: 색 분포 최적화
                dither=Image.Dither.FLOYDSTEINBERG, # 디더링: 색 손실 최소화
            )

            frames.append(quantized)
            durations.append(dur)

    except EOFError:
        pass
    except Exception as e:
        print(f"  [FAIL] {webp.name}: 프레임 추출 오류 - {e}", flush=True)
        return False

    if not frames:
        print(f"  [FAIL] {webp.name}: 프레임 없음", flush=True)
        return False

    is_animated = len(frames) > 1
    frame_info = f"{len(frames)}프레임" if is_animated else "정지"

    try:
        gif.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(
            gif,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,           # 무한 반복
            optimize=False,   # 프레임 팔레트 독립성 보장 (optimize=True 시 팔레트 공유로 품질 저하)
            disposal=2,       # 이전 프레임 지우고 그리기 (겹침 방지)
        )
        size_kb = gif.stat().st_size // 1024
        print(f"  [OK] {gif.name}  ({frame_info}, {size_kb} KB)", flush=True)
        return True
    except Exception as e:
        print(f"  [FAIL] {gif.name}: 저장 오류 - {e}", flush=True)
        return False


# ─────────────────────────────────────────────────────────────
# 폴더 일괄 변환
# ─────────────────────────────────────────────────────────────
def convert_folder(folder: pathlib.Path, delete_webp: bool = False) -> tuple:
    webps = sorted(folder.glob("*.webp"))
    if not webps:
        print(f"  [!] WebP 파일 없음: {folder}", flush=True)
        return 0, 0

    print(f"\n[변환] {folder}  ({len(webps)}개)", flush=True)
    ok = 0
    for w in webps:
        g = w.with_suffix(".gif")
        if convert_one(w, g):
            ok += 1
            if delete_webp:
                w.unlink()

    print(f"  => {ok}/{len(webps)} 변환 완료", flush=True)
    return ok, len(webps)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="WebP -> GIF 변환기 (최고 품질)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python webp_to_gif.py output/genshin-impact-sumeru-themed-cafe
  python webp_to_gif.py output/genshin-impact-sumeru-themed-cafe/001.webp
  python webp_to_gif.py output/genshin-impact-sumeru-themed-cafe --delete-webp
        """,
    )
    parser.add_argument("path", help="변환할 WebP 파일 또는 폴더 경로")
    parser.add_argument(
        "--delete-webp", "-d", action="store_true",
        help="변환 완료 후 원본 WebP 파일 삭제"
    )
    args = parser.parse_args()

    target = pathlib.Path(args.path)

    if target.is_file():
        # 단일 파일
        if target.suffix.lower() != ".webp":
            print(f"[오류] WebP 파일이 아닙니다: {target}")
            sys.exit(1)
        gif = target.with_suffix(".gif")
        ok = convert_one(target, gif)
        if ok and args.delete_webp:
            target.unlink()
        sys.exit(0 if ok else 1)

    elif target.is_dir():
        # 폴더 안의 모든 WebP 변환
        # 하위 폴더도 재귀 탐색
        all_ok, all_total = 0, 0

        # 직접 포함된 webp가 있으면 처리
        if list(target.glob("*.webp")):
            ok, total = convert_folder(target, args.delete_webp)
            all_ok += ok
            all_total += total

        # 하위 폴더도 처리
        for sub in sorted(target.iterdir()):
            if sub.is_dir() and list(sub.glob("*.webp")):
                ok, total = convert_folder(sub, args.delete_webp)
                all_ok += ok
                all_total += total

        if all_total == 0:
            print(f"[!] 변환할 WebP 파일이 없습니다: {target}")
            sys.exit(1)

        print(f"\n[최종] 총 {all_ok}/{all_total} 변환 완료", flush=True)

    else:
        print(f"[오류] 존재하지 않는 경로: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()

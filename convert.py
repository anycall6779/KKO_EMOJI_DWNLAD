#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebP 자동 변환기 (애니메이션 감지 + 최고 품질 변환)
=====================================================
- animated WebP  → GIF  (프레임별 독립 팔레트 + Floyd-Steinberg 디더링)
- static  WebP   → PNG  (완전 무손실)
- 혼재 시 → 각각 자동 처리

사용법:
  python convert.py <폴더>          # 대화형으로 질문
  python convert.py <폴더> --yes    # 질문 없이 자동 변환
  python convert.py <파일.webp>     # 단일 파일
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
# 1. 애니메이션 감지
# ─────────────────────────────────────────────────────────────
def is_animated(path: pathlib.Path) -> bool:
    """WebP 파일이 애니메이션인지 확인 (n_frames > 1)."""
    try:
        img = Image.open(path)
        return getattr(img, "n_frames", 1) > 1
    except Exception:
        return False


def scan_folder(folder: pathlib.Path):
    """
    폴더의 WebP 파일을 애니메이션/정지로 분류.
    반환: (animated_list, static_list)
    """
    webps = sorted(folder.glob("*.webp"))
    animated, static = [], []
    for w in webps:
        if is_animated(w):
            animated.append(w)
        else:
            static.append(w)
    return animated, static


# ─────────────────────────────────────────────────────────────
# 2. WebP → GIF (애니메이션 전용)
# ─────────────────────────────────────────────────────────────
def webp_to_gif(webp: pathlib.Path) -> bool:
    """
    animated WebP → GIF
    프레임별 독립 팔레트(256색) + Floyd-Steinberg 디더링
    """
    gif = webp.with_suffix(".gif")
    try:
        src = Image.open(webp)
        frames, durations = [], []

        for frame in ImageSequence.Iterator(src):
            f = frame.copy()
            dur = f.info.get("duration", 100)
            if dur < 20:
                dur = 100

            rgba = f.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            bg.alpha_composite(rgba)
            rgb = bg.convert("RGB")

            quantized = rgb.quantize(
                colors=256,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
            frames.append(quantized)
            durations.append(dur)

        if not frames:
            print(f"  [FAIL] {webp.name}: 프레임 없음", flush=True)
            return False

        frames[0].save(
            gif,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            optimize=False,
            disposal=2,
        )
        n = len(frames)
        kb = gif.stat().st_size // 1024
        print(f"  [GIF] {gif.name}  ({n}프레임, {kb} KB)", flush=True)
        return True

    except Exception as e:
        print(f"  [FAIL] {webp.name} -> GIF: {e}", flush=True)
        return False


# ─────────────────────────────────────────────────────────────
# 3. WebP → PNG (정지 이미지 전용, 완전 무손실)
# ─────────────────────────────────────────────────────────────
def webp_to_png(webp: pathlib.Path) -> bool:
    """static WebP → PNG (완전 무손실)."""
    png = webp.with_suffix(".png")
    try:
        img = Image.open(webp)
        img.save(png, format="PNG", optimize=False)
        kb = png.stat().st_size // 1024
        print(f"  [PNG] {png.name}  ({kb} KB)", flush=True)
        return True
    except Exception as e:
        print(f"  [FAIL] {webp.name} -> PNG: {e}", flush=True)
        return False


# ─────────────────────────────────────────────────────────────
# 4. 폴더 처리 (감지 → 질문 → 변환)
# ─────────────────────────────────────────────────────────────
def ask(prompt: str) -> str:
    """Y/N/P/G 입력 받기 (대소문자 무시)."""
    try:
        ans = input(prompt).strip().upper()
        return ans
    except (EOFError, KeyboardInterrupt):
        return "N"


def process_folder(folder: pathlib.Path, auto_yes: bool = False, delete_webp: bool = False) -> None:
    animated, static = scan_folder(folder)
    total = len(animated) + len(static)

    if total == 0:
        print(f"  [!] WebP 파일 없음: {folder}", flush=True)
        return

    # ── 감지 결과 출력 ───────────────────────────────────────
    print(f"\n  경로  : {folder}", flush=True)
    print(f"  감지  : 애니메이션 {len(animated)}개 / 정지 {len(static)}개", flush=True)

    # ── 케이스 분기 ──────────────────────────────────────────
    if animated and static:
        # 혼재
        print(f"\n  [혼재] 애니메이션 WebP는 GIF로, 정지 WebP는 PNG로 변환합니다.", flush=True)
        if auto_yes:
            ans = "Y"
        else:
            ans = ask("  변환하시겠습니까? (Y=예 / N=건너뜀): ")
        if ans == "Y":
            _convert_list(animated, webp_to_gif, delete_webp)
            _convert_list(static,   webp_to_png, delete_webp)

    elif animated:
        # 전부 애니메이션 → GIF
        print(f"\n  [애니메이션] 전부 GIF로 변환할 수 있습니다.", flush=True)
        if auto_yes:
            ans = "Y"
        else:
            ans = ask("  GIF로 변환하시겠습니까? (Y=예 / N=건너뜀): ")
        if ans == "Y":
            _convert_list(animated, webp_to_gif, delete_webp)

    else:
        # 전부 정지 → PNG
        print(f"\n  [정지 이미지] 전부 PNG로 변환할 수 있습니다.", flush=True)
        if auto_yes:
            ans = "Y"
        else:
            ans = ask("  PNG로 변환하시겠습니까? (Y=예 / N=건너뜀): ")
        if ans == "Y":
            _convert_list(static, webp_to_png, delete_webp)


def _convert_list(files, converter, delete_webp):
    ok = 0
    for f in files:
        if converter(f):
            ok += 1
            if delete_webp:
                f.unlink()
    print(f"  => {ok}/{len(files)} 완료", flush=True)


# ─────────────────────────────────────────────────────────────
# 5. CLI
# ─────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="WebP 자동 변환기 (animated→GIF / static→PNG)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python convert.py output/genshin-impact-sumeru-themed-cafe
  python convert.py output/genshin-impact-sumeru-themed-cafe --yes
  python convert.py output/genshin-impact-sumeru-themed-cafe --delete-webp
  python convert.py output/pack/001.webp
        """,
    )
    parser.add_argument("path", help="변환할 폴더 또는 WebP 파일 경로")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="질문 없이 자동 변환")
    parser.add_argument("--delete-webp", "-d", action="store_true",
                        help="변환 완료 후 원본 WebP 삭제")
    args = parser.parse_args()

    target = pathlib.Path(args.path)

    # ── 단일 파일 ──────────────────────────────────────────
    if target.is_file():
        if target.suffix.lower() != ".webp":
            print(f"[오류] WebP 파일이 아닙니다: {target}")
            sys.exit(1)
        if is_animated(target):
            print(f"[감지] 애니메이션 WebP → GIF 변환", flush=True)
            ok = webp_to_gif(target)
        else:
            print(f"[감지] 정지 WebP → PNG 변환", flush=True)
            ok = webp_to_png(target)
        if ok and args.delete_webp:
            target.unlink()
        sys.exit(0 if ok else 1)

    # ── 폴더 ───────────────────────────────────────────────
    elif target.is_dir():
        # 직접 포함된 webp 처리
        has_direct = bool(list(target.glob("*.webp")))
        has_sub    = any(
            bool(list(sub.glob("*.webp")))
            for sub in target.iterdir() if sub.is_dir()
        )

        if has_direct:
            process_folder(target, args.yes, args.delete_webp)

        if has_sub:
            for sub in sorted(target.iterdir()):
                if sub.is_dir() and list(sub.glob("*.webp")):
                    process_folder(sub, args.yes, args.delete_webp)

        if not has_direct and not has_sub:
            print(f"[!] 변환할 WebP 파일이 없습니다: {target}")
            sys.exit(1)

    else:
        print(f"[오류] 존재하지 않는 경로: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
카카오 이모티콘 다운로더 v3.0
================================
지원 URL:
  - https://e.kakao.com/t/{slug}
  - https://emoticon.kakao.com/items/{hashedId}?...  (카카오톡 공유 링크)
  - slug 문자열 직접 입력

사용법:
  python kakao_downloader.py <URL>
  python kakao_downloader.py <URL> --output ./output
  python kakao_downloader.py <URL> --static-only       # animated 대신 PNG
  python kakao_downloader.py --creator JAG30H          # 크리에이터 전체 팩
"""

import sys, io
# Windows 콘솔 인코딩 문제 방지
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    print("[오류] httpx 패키지가 필요합니다: pip install httpx")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────
# 공통 헤더
# ─────────────────────────────────────────────────────────────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Referer": "https://e.kakao.com/",
}


# ─────────────────────────────────────────────────────────────
# URL → slug 변환
# ─────────────────────────────────────────────────────────────
def _slug_from_text(raw: str) -> Optional[str]:
    """HTTP 요청 없이 URL 또는 문자열에서 slug 추출."""
    s = raw.strip().rstrip("/").split("?")[0]
    if "kakao.com" in s:
        m = re.search(r"/t/([^/?#]+)", s)
        if m:
            return m.group(1)
        return None
    if re.fullmatch(r"[a-z0-9][-a-z0-9]*", s):
        return s
    return None


async def resolve_slug(raw: str) -> Optional[str]:
    """
    모든 URL 형식을 slug로 변환.
      - e.kakao.com/t/{slug}           → 직접 추출
      - emoticon.kakao.com/items/{id}  → 303 리다이렉트 추적
      - slug 문자열                    → 그대로 반환
    """
    # emoticon.kakao.com 공유 링크: 반드시 리다이렉트 먼저
    if "emoticon.kakao.com" in raw:
        print("[*] 카카오톡 공유 링크 → 리다이렉트 추적 중...", flush=True)
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(
                    raw,
                    headers={"User-Agent": _HEADERS["User-Agent"]},
                    follow_redirects=True,
                    timeout=15,
                )
                final = str(r.url)
                print(f"[*] 최종 URL: {final}", flush=True)
                return _slug_from_text(final)
        except Exception as e:
            print(f"[오류] 리다이렉트 실패: {e}", flush=True)
            return None

    return _slug_from_text(raw)


# ─────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────
async def fetch_pack_data(slug: str) -> Dict:
    """GET https://e.kakao.com/api/items/{slug}"""
    url = f"https://e.kakao.com/api/items/{slug}"
    print(f"[API] {url}", flush=True)
    async with httpx.AsyncClient() as c:
        r = await c.get(url, headers=_HEADERS, follow_redirects=True, timeout=20)
        r.raise_for_status()
        return r.json()


async def fetch_creator_slugs(creator_id: str) -> List[str]:
    """크리에이터의 팩 slug 목록 조회."""
    slugs = []
    endpoints = [
        f"https://e.kakao.com/api/creators/{creator_id}/items",
        f"https://e.kakao.com/api/creators/{creator_id}",
    ]
    async with httpx.AsyncClient() as c:
        for url in endpoints:
            try:
                r = await c.get(url, headers=_HEADERS, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    items = data.get("items") or data.get("data", {}).get("items") or []
                    s = [it.get("slug") or it.get("id") for it in items
                         if it.get("slug") or it.get("id")]
                    if s:
                        return s
            except Exception:
                pass
    return slugs


# ─────────────────────────────────────────────────────────────
# 데이터 파싱
# ─────────────────────────────────────────────────────────────
def parse_pack(data: Dict, static_only: bool = False) -> Dict:
    """
    API JSON에서 다운로드에 필요한 정보 추출.
    contents.items[i]:
      thumbnailUrl → 정적 PNG
      animatedUrl  → 애니메이션 WebP (복호화 불필요)
      soundUrl     → MP3 (있는 경우)
    """
    hero     = data.get("hero", {})
    contents = data.get("contents", {})
    creator  = data.get("creator", {})

    items_raw = contents.get("items", [])
    items = []
    for i, it in enumerate(items_raw, 1):
        anim  = it.get("animatedUrl")  if not static_only else None
        thumb = it.get("thumbnailUrl") or ""
        sound = it.get("soundUrl")
        items.append({
            "index":         i,
            "animated_url":  anim,
            "thumbnail_url": thumb,
            "sound_url":     sound,
        })

    return {
        "title":      hero.get("title", "unknown"),
        "author":     creator.get("name", ""),
        "creator_id": creator.get("detail", {}).get("id", ""),
        "is_sound":   contents.get("isSound", False),
        "items":      items,
    }


def build_targets(pack: Dict, out: Path, static_only: bool) -> List[Tuple[str, Path]]:
    """(url, dest_path) 목록 생성. animated 우선."""
    targets = []
    for it in pack["items"]:
        idx = str(it["index"]).zfill(3)
        anim  = it["animated_url"]
        thumb = it["thumbnail_url"]
        sound = it["sound_url"]

        if anim and not static_only:
            targets.append((anim,  out / f"{idx}.webp"))
        elif thumb:
            ext = Path(urlparse(thumb).path).suffix or ".png"
            targets.append((thumb, out / f"{idx}{ext}"))

        if sound:
            targets.append((sound, out / f"{idx}.mp3"))

    return targets


# ─────────────────────────────────────────────────────────────
# 다운로드
# ─────────────────────────────────────────────────────────────
async def _dl_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    url: str,
    dest: Path,
    retries: int = 3,
) -> bool:
    async with sem:
        for attempt in range(1, retries + 1):
            try:
                r = await client.get(url, follow_redirects=True, timeout=30)
                if r.status_code == 404:
                    return False
                r.raise_for_status()
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(r.content)
                print(f"  [OK] {dest.name}", flush=True)
                return True
            except Exception as e:
                if attempt == retries:
                    print(f"  [FAIL] {dest.name}: {e}", flush=True)
                    return False
                await asyncio.sleep(1.5 * attempt)
    return False


async def download_all(targets: List[Tuple[str, Path]], concurrency: int = 6) -> Tuple[int, int]:
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(headers=_HEADERS) as client:
        results = await asyncio.gather(
            *[_dl_one(client, sem, url, dest) for url, dest in targets]
        )
    ok = sum(bool(r) for r in results)
    return ok, len(targets)


# ─────────────────────────────────────────────────────────────
# 팩 단위 다운로드
# ─────────────────────────────────────────────────────────────
async def download_pack(
    slug: str,
    output_base: Path,
    static_only: bool = False,
    save_json: bool = False,
) -> None:
    try:
        data = await fetch_pack_data(slug)
    except httpx.HTTPStatusError as e:
        print(f"[오류] API 실패: {e}", flush=True)
        return

    pack = parse_pack(data, static_only)
    mode = "정적 PNG" if static_only else "animated WebP"

    print(f"\n{'='*52}", flush=True)
    print(f"  제목    : {pack['title']}", flush=True)
    print(f"  작가    : {pack['author']}", flush=True)
    print(f"  이모티콘: {len(pack['items'])}개", flush=True)
    print(f"  소리    : {'예' if pack['is_sound'] else '아니오'}", flush=True)
    print(f"  모드    : {mode}", flush=True)
    print(f"{'='*52}\n", flush=True)

    out = output_base / slug
    out.mkdir(parents=True, exist_ok=True)

    if save_json:
        (out / "api_response.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    targets = build_targets(pack, out, static_only)
    print(f"[다운로드] {len(targets)}개 → {out}", flush=True)
    ok, total = await download_all(targets)
    print(f"\n[완료] {ok}/{total} 성공\n", flush=True)


async def download_creator(
    creator_id: str,
    output_base: Path,
    static_only: bool = False,
    save_json: bool = False,
) -> None:
    print(f"[크리에이터] {creator_id} 팩 목록 조회 중...", flush=True)
    slugs = await fetch_creator_slugs(creator_id)
    if not slugs:
        print("[오류] 팩 목록을 가져오지 못했습니다.", flush=True)
        return
    print(f"[크리에이터] {len(slugs)}개 팩 발견", flush=True)
    for slug in slugs:
        await download_pack(slug, output_base, static_only, save_json)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="카카오 이모티콘 다운로더 v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python kakao_downloader.py https://e.kakao.com/t/genshin-impact-sumeru-themed-cafe
  python kakao_downloader.py https://emoticon.kakao.com/items/QlQ5RU...=?lang=ko
  python kakao_downloader.py genshin-impact-sumeru-themed-cafe
  python kakao_downloader.py https://e.kakao.com/t/... --static-only
  python kakao_downloader.py --creator JAG30H
        """,
    )
    parser.add_argument("url", nargs="?", default="",
                        help="이모티콘 URL 또는 slug")
    parser.add_argument("--creator", "-c", default=None,
                        help="크리에이터 ID (전체 팩 일괄 다운로드)")
    parser.add_argument("--output", "-o", default="output",
                        help="저장 폴더 (기본: output/)")
    parser.add_argument("--static-only", "-s", action="store_true",
                        help="animated 대신 정적 PNG 다운로드")
    parser.add_argument("--save-json", action="store_true",
                        help="API 응답을 api_response.json으로 저장")
    parser.add_argument("--concurrency", "-n", type=int, default=6,
                        help="동시 다운로드 수 (기본: 6)")
    args = parser.parse_args()

    if not args.url and not args.creator:
        parser.print_help()
        sys.exit(1)

    output_base = Path(args.output)

    if args.creator:
        asyncio.run(
            download_creator(
                creator_id=args.creator,
                output_base=output_base,
                static_only=args.static_only,
                save_json=args.save_json,
            )
        )
    else:
        async def _run():
            slug = await resolve_slug(args.url)
            if not slug:
                print(f"[오류] 유효하지 않은 URL: {args.url}", flush=True)
                sys.exit(1)
            await download_pack(
                slug=slug,
                output_base=output_base,
                static_only=args.static_only,
                save_json=args.save_json,
            )
        asyncio.run(_run())


if __name__ == "__main__":
    main()

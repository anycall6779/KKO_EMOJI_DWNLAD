# 카오 이모티콘 다운로더

카오 이모티콘 스토어에서 WebP 파일을 직접 다운로드하는 도구입니다.

## 사용 방법

### 간단하게 (추천)
`start.bat` 더블클릭 → URL 입력 → 다운로드

### 직접 실행
```bash
# e.kko.com 스토어 링크
python kko_downloader.py https://e.kko.com/t/

# 카카오톡 앱 공유 링크 (emoticon..com)
python kko_downloader.py ""

# 정적 PNG로 저장
python kko_downloader.py https://e.kko.com/t/... --static-only

# 크리에이터 전체 팩 일괄 다운로드
python kko_downloader.py --creator JAG30H
```

## 지원 URL

| URL 형식 | 예시 |
|----------|------|
| `https://e.kko.com/t/{slug}` | e.kko.com 스토어 페이지 |
| `https://emoticon..com/items/{id}` | 카카오톡 앱 공유 버튼 링크 |
| slug 직접 입력 | `genshin-impact-sumeru-themed-cafe` |

## 요구사항

- Python 3.8 이상
- httpx (`pip install httpx` 또는 start.bat이 자동 설치)

## 옵션

| 옵션 | 설명 |
|------|------|
| `--output <폴더>` | 저장 폴더 지정 (기본: `output/`) |
| `--static-only` | animated WebP 대신 정적 PNG 저장 |
| `--creator <ID>` | 크리에이터 전체 팩 일괄 다운로드 |
| `--save-json` | API 응답 JSON도 저장 |
| `--concurrency <N>` | 동시 다운로드 수 (기본: 6) |

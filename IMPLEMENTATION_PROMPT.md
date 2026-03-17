# Japan News Generator — 구현 프롬프트

이 문서를 읽은 AI는 아래 명세를 그대로 따라 `japan-news-generator` 프로젝트를 처음부터 완전히 재현할 수 있다.

---

## 프로젝트 목적

YouTube 일본어 뉴스 영상 URL을 입력받아:
1. 영상 메타데이터 + 자막(transcript)을 추출
2. AI가 일본어/한국어 대역 테이블 + 어휘 정리 마크다운을 생성
3. 마크다운 → PDF 변환 (QR 코드, 썸네일, 후리가나 포함)
4. Google Drive에 PDF 업로드 (공개 링크 생성)
5. Google Sheets에 결과 기록 (URL, 제목, 채널, 길이, 날짜, 상태, PDF 링크)

---

## 디렉토리 구조

```
japan-news-generator/
├── main.py                        # API 방식 단일 영상 처리 진입점
├── requirements.txt
├── .env                           # 환경변수 (gitignore)
├── .env.example
├── .gitignore
├── CLAUDE.md                      # Claude Code 지침
├── config/
│   ├── .gitkeep
│   ├── credentials.json           # Google 서비스 계정 키 (gitignore)
│   ├── oauth_client.json          # Google OAuth2 클라이언트 (gitignore)
│   └── oauth_token.pickle         # OAuth2 토큰 캐시 (gitignore)
├── output/                        # 생성된 PDF/MD 저장 (gitignore)
├── tools/
│   ├── __init__.py
│   ├── fetch_youtube.py           # YouTube 메타데이터 + 자막 추출
│   ├── text_to_markdown.py        # Claude API로 마크다운 생성
│   ├── markdown_to_pdf.py         # 마크다운 → PDF 변환
│   ├── google_sheets.py           # Google Sheets 연동
│   ├── drive_uploader.py          # Google Drive 업로드 (OAuth2)
│   └── batch_processor.py         # 배치 처리기
└── .claude/
    ├── settings.local.json        # Claude Code 설정
    └── commands/
        └── japannews.md           # /japannews 슬래시 커맨드
```

---

## 환경 설정

### .env.example
```
ANTHROPIC_API_KEY=your_api_key_here
DYLD_LIBRARY_PATH=/opt/homebrew/lib

GOOGLE_CREDENTIALS_PATH=config/credentials.json
GOOGLE_SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_DRIVE_FOLDER_ID=
GOOGLE_SHEET_NAME=시트1
```

### .gitignore
```
.env
config/credentials.json
config/*.json
output/
__pycache__/
*.pyc
*.pyo
.venv/
venv/
.DS_Store
```

### requirements.txt
```
anthropic>=0.84.0
python-dotenv>=1.0.0
yt-dlp>=2024.1.0
youtube-transcript-api>=0.6.0
weasyprint>=61.0
qrcode[pil]>=7.4.0
gspread>=6.0.0
google-auth>=2.0.0
google-auth-oauthlib>=1.0.0
google-api-python-client>=2.0.0
```

macOS에서 WeasyPrint 실행 시 반드시:
```bash
export DYLD_LIBRARY_PATH=/opt/homebrew/lib
brew install pango cairo libffi gdk-pixbuf
```

---

## 소스 코드

### tools/fetch_youtube.py
```python
"""
Tool 0: YouTube 콘텐츠 가져오기
- youtube-transcript-api: 자막(transcript) 추출
- yt-dlp: 영상 설명(description) 및 메타데이터 추출
"""

import re
import subprocess
import json
from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(url: str) -> str:
    match = re.search(r"v=([^&]+)", url)
    return match.group(1) if match else url


def fetch_youtube_content(url: str) -> dict:
    video_id = extract_video_id(url)

    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", url],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["ja", "ko", "en"])
        transcript_text = " ".join([item.text for item in fetched])
    except Exception as e:
        print(f"자막 가져오기 실패 (무시하고 계속): {e}")
        transcript_text = ""

    duration_sec = data.get("duration", 0) or 0
    minutes, seconds = divmod(int(duration_sec), 60)
    duration_str = f"{minutes}:{seconds:02d}"

    return {
        "title": data.get("title", ""),
        "channel": data.get("channel", ""),
        "upload_date": data.get("upload_date", ""),
        "duration": duration_str,
        "description": data.get("description", ""),
        "transcript": transcript_text,
    }
```

---

### tools/text_to_markdown.py
```python
"""
Tool 1: Text → Markdown 변환
Claude API를 호출해 일본어 학습 콘텐츠를 구조화된 마크다운으로 변환
"""

import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """당신은 일본어 학습 콘텐츠를 마크다운으로 변환하는 전문가입니다.
주어진 YouTube 영상 설명글을 분석하여 다음 규칙에 따라 마크다운을 생성하세요.

규칙:
1. 제목은 H1(#), 채널명과 날짜는 부제목으로 표기
2. 타임스탬프(00:00, 03:40 등)는 H2(##) 섹션으로 분리
3. 일본어 문장(뉴스 본문)은 아래 테이블 형식:
   | 일본어 문장 | 한국어 해석 |
   |---|---|
   | (일본어 원문) | (한국어 번역) |
4. 일본어 단어/어휘 목록은 아래 테이블 형식:
   | 단어 (읽기) | 한국어 뜻 |
   |---|---|
   | 단어 [읽기] | 뜻 |
5. 마크다운 형식만 출력하고, 다른 설명은 하지 마세요."""


def text_to_markdown(content: dict) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    user_message = f"""다음 YouTube 영상 설명글을 마크다운으로 변환해주세요.

제목: {content['title']}
채널: {content['channel']}
날짜: {content['upload_date']}

=== 설명글 ===
{content['description']}
"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text
```

---

### tools/markdown_to_pdf.py
```python
"""
Tool 2: Markdown → PDF 변환
- pandoc: markdown → HTML
- weasyprint: HTML → PDF (일본어 폰트 지원)
- 후리가나: 漢字(よみ) 패턴 → inline-block ruby
- QR 코드 + YouTube 썸네일을 H1 아래에 삽입
"""

import base64
import io
import os
import re
import subprocess
import tempfile
import urllib.request
import urllib.error

import qrcode
from weasyprint import HTML, CSS

CSS_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');

body {
    font-family: "Noto Sans JP", "Hiragino Sans", "Yu Gothic", "Meiryo", sans-serif;
    font-size: 13px;
    line-height: 1.9;
    margin: 0;
    padding: 40px;
    color: #2c2c2c;
    background: white;
}

.ruby-group {
    display: inline-block;
    text-align: center;
    vertical-align: baseline;
    margin: 0 1px;
}

.ruby-text {
    display: block;
    font-size: 0.5em;
    color: #555;
    line-height: 1;
    white-space: nowrap;
    min-height: 0.7em;
}

.ruby-base {
    display: block;
    line-height: 1;
}

h1 {
    font-size: 22px;
    color: #1a237e;
    border-bottom: 3px solid #1a237e;
    padding-bottom: 10px;
    margin-bottom: 6px;
}

h2 {
    font-size: 16px;
    color: #283593;
    background-color: #e8eaf6;
    padding: 6px 12px;
    border-left: 4px solid #3949ab;
    margin-top: 28px;
    margin-bottom: 12px;
    break-before: page;
    page-break-before: always;
}

h2:first-of-type {
    break-before: auto;
    page-break-before: auto;
}

tr {
    break-inside: avoid;
    page-break-inside: avoid;
}

p {
    margin: 4px 0;
    color: #555;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 20px 0;
    font-size: 13px;
}

th {
    background-color: #3949ab;
    color: white;
    padding: 9px 12px;
    text-align: left;
    font-weight: bold;
}

td {
    border: 1px solid #c5cae9;
    padding: 8px 12px;
    vertical-align: top;
    line-height: 2.2;
}

tr:nth-child(even) td {
    background-color: #f3f4fb;
}

tr:hover td {
    background-color: #e8eaf6;
}
"""


def _generate_qr_base64(url: str) -> str:
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _convert_furigana_to_ruby(html: str) -> str:
    """漢字(よみ) 패턴을 inline-block 기반 후리가나로 변환"""
    pattern = r'([一-龯々〆〇]+)\(([ぁ-んァ-ンー・]+)\)'
    replacement = (
        r'<span class="ruby-group">'
        r'<span class="ruby-text">\2</span>'
        r'<span class="ruby-base">\1</span>'
        r'</span>'
    )
    return re.sub(pattern, replacement, html)


def _fetch_thumbnail_base64(url: str) -> str | None:
    """YouTube URL에서 video_id를 추출해 썸네일을 base64로 반환"""
    m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
    if not m:
        return None
    video_id = m.group(1)
    for quality in ('maxresdefault', 'hqdefault', 'mqdefault'):
        thumb_url = f'https://img.youtube.com/vi/{video_id}/{quality}.jpg'
        try:
            with urllib.request.urlopen(thumb_url, timeout=5) as resp:
                data = resp.read()
            return base64.b64encode(data).decode('utf-8')
        except urllib.error.URLError:
            continue
    return None


def _inject_qr_into_html(html: str, url: str) -> str:
    qr_b64 = _generate_qr_base64(url)
    qr_img_tag = (
        f'<img src="data:image/png;base64,{qr_b64}" '
        f'alt="QR Code" style="width:80px;height:80px;flex-shrink:0;" />'
    )

    thumb_b64 = _fetch_thumbnail_base64(url)
    if thumb_b64:
        thumb_block = (
            f'<a href="{url}" style="display:block;margin-top:10px;margin-bottom:4px;">'
            f'<img src="data:image/jpeg;base64,{thumb_b64}" '
            f'alt="YouTube thumbnail" '
            f'style="width:100%;max-height:200px;object-fit:cover;'
            f'border-radius:6px;border:1px solid #c5cae9;" />'
            f'</a>'
        )
    else:
        thumb_block = ''

    def replace_h1(m):
        inner = m.group(1)
        return (
            '<div style="border-bottom:3px solid #1a237e;padding-bottom:10px;margin-bottom:6px;">'
            '<div style="display:flex;align-items:center;gap:16px;">'
            f'<h1 style="border:none;padding:0;margin:0;flex:1;">{inner}</h1>'
            f'{qr_img_tag}'
            '</div>'
            f'{thumb_block}'
            '</div>'
        )

    return re.sub(r'<h1[^>]*>(.*?)</h1>', replace_h1, html, count=1, flags=re.DOTALL)


def markdown_to_pdf(markdown_text: str, output_path: str = "output/result.pdf", url: str = "") -> str:
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(markdown_text)
        md_path = f.name

    html_path = md_path.replace(".md", ".html")

    subprocess.run(
        ["pandoc", md_path, "-o", html_path, "--standalone", "--metadata", "charset=utf-8"],
        check=True,
    )

    with open(html_path, encoding="utf-8") as f:
        html_content = f.read()
    if url:
        html_content = _inject_qr_into_html(html_content, url)
    html_content = _convert_furigana_to_ruby(html_content)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    HTML(filename=html_path).write_pdf(output_path, stylesheets=[CSS(string=CSS_STYLE)])

    os.unlink(md_path)
    os.unlink(html_path)

    return output_path
```

---

### tools/google_sheets.py
```python
"""
Google Sheets 연동 헬퍼 (서비스 계정 인증)

스프레드시트 컬럼 구조:
  A: YouTube URL
  B: 영상 제목
  C: 채널명
  D: 영상 길이
  E: 업로드 날짜
  F: 등록 날짜
  G: 진행 여부 (대기 / 실행중 / 완료 / 오류)
  H: PDF 결과 (Drive 링크)
"""

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

STATUS_PENDING = "대기"
STATUS_RUNNING = "실행중"
STATUS_DONE = "완료"
STATUS_ERROR = "오류"

COL_URL = 1         # A
COL_TITLE = 2       # B
COL_CHANNEL = 3     # C
COL_DURATION = 4    # D
COL_UPLOAD = 5      # E
COL_REG_DATE = 6    # F
COL_STATUS = 7      # G
COL_PDF = 8         # H


def get_client(credentials_path: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet(credentials_path: str, spreadsheet_id: str, sheet_name: str = "시트1"):
    client = get_client(credentials_path)
    spreadsheet = client.open_by_key(spreadsheet_id)
    return spreadsheet.worksheet(sheet_name)


def get_pending_rows(sheet) -> list[dict]:
    rows = sheet.get_all_values()
    pending = []
    for i, row in enumerate(rows[1:], start=2):
        url = row[COL_URL - 1].strip() if len(row) >= COL_URL else ""
        status = row[COL_STATUS - 1].strip() if len(row) >= COL_STATUS else ""
        if url and status in (STATUS_PENDING, ""):
            pending.append({"row": i, "url": url})
    return pending


def set_status(sheet, row: int, status: str):
    sheet.update_cell(row, COL_STATUS, status)


def set_result(sheet, row: int, pdf_link: str):
    sheet.update_cell(row, COL_PDF, pdf_link)
    sheet.update_cell(row, COL_STATUS, STATUS_DONE)


def append_result(sheet, url: str, title: str, channel: str, duration: str,
                  upload_date: str, pdf_link: str):
    """새 행을 기존 형식에 맞춰 추가"""
    from datetime import date
    reg_date = date.today().strftime("%Y-%m-%d")
    sheet.append_row([url, title, channel, duration, upload_date, reg_date, STATUS_DONE, pdf_link])


def set_error(sheet, row: int, message: str):
    sheet.update_cell(row, COL_PDF, f"오류: {message}")
    sheet.update_cell(row, COL_STATUS, STATUS_ERROR)


def ensure_header(sheet):
    first_row = sheet.row_values(1)
    if not first_row or first_row[0] != "유튜브 링크":
        sheet.update("A1:H1", [["유튜브 링크", "영상 제목", "채널명", "영상 길이",
                                 "업로드 날짜", "등록 날짜", "진행 여부", "PDF 결과"]])
        sheet.format("A1:H1", {"textFormat": {"bold": True}})
```

---

### tools/drive_uploader.py
```python
"""
Google Drive 업로드 헬퍼 (OAuth2 사용자 인증)
- 첫 실행 시 브라우저 인증 → token 저장
- 이후 자동으로 token 재사용 (refresh)
"""

import os
import pickle

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_PATH = "config/oauth_token.pickle"
CLIENT_SECRET_PATH = "config/oauth_client.json"


def get_drive_service():
    creds = None

    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return build("drive", "v3", credentials=creds)


def upload_pdf(
    credentials_path: str,  # 하위 호환성 유지 (사용 안 함)
    pdf_path: str,
    folder_id: str = None,
    file_name: str = None,
) -> str:
    service = get_drive_service()

    name = file_name or os.path.basename(pdf_path)
    metadata = {"name": name}
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaFileUpload(pdf_path, mimetype="application/pdf", resumable=True)
    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id",
    ).execute()

    file_id = file["id"]

    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view"
```

---

### tools/batch_processor.py
```python
"""
배치 처리기

모드:
  --dry-run          대기 목록만 출력
  --fetch            YouTube 콘텐츠 수집 → /tmp/japannews_batch_{row}.json 저장
  --finalize ROW MD  마크다운을 받아 PDF → Drive → Sheets 업데이트
  (인자 없음)        API 방식 end-to-end 처리
"""

import argparse, json, os, re, sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools.google_sheets import (
    get_sheet, get_pending_rows, set_status, set_result, set_error, ensure_header, STATUS_RUNNING,
)
from tools.drive_uploader import upload_pdf
from tools.fetch_youtube import fetch_youtube_content
from tools.markdown_to_pdf import markdown_to_pdf

CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "config/credentials.json")
SPREADSHEET_ID   = os.getenv("GOOGLE_SPREADSHEET_ID", "")
DRIVE_FOLDER_ID  = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
SHEET_NAME       = os.getenv("GOOGLE_SHEET_NAME", "시트1")
OUTPUT_DIR       = "output"
FETCH_TMP_DIR    = "/tmp"


def extract_video_id(url: str) -> str:
    match = re.search(r"v=([^&]+)", url)
    return match.group(1) if match else re.sub(r"[^a-zA-Z0-9_-]", "_", url)[:20]


def _get_sheet():
    sheet = get_sheet(CREDENTIALS_PATH, SPREADSHEET_ID, SHEET_NAME)
    ensure_header(sheet)
    return sheet


def run_dry():
    sheet = _get_sheet()
    pending = get_pending_rows(sheet)
    for item in pending:
        print(f"  행 {item['row']}: {item['url']}")


def run_fetch():
    sheet = _get_sheet()
    pending = get_pending_rows(sheet)
    results = []
    for item in pending:
        row, url = item["row"], item["url"]
        video_id = extract_video_id(url)
        try:
            set_status(sheet, row, STATUS_RUNNING)
            content = fetch_youtube_content(url)
            tmp_path = os.path.join(FETCH_TMP_DIR, f"japannews_batch_{row}.json")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({"row": row, "url": url, "video_id": video_id, "content": content}, f, ensure_ascii=False, indent=2)
            results.append({"row": row, "url": url, "video_id": video_id,
                            "title": content["title"], "upload_date": content.get("upload_date", "unknown"), "tmp_path": tmp_path})
        except Exception as e:
            set_error(sheet, row, str(e)[:200])

    for r in results:
        md_path = os.path.join(OUTPUT_DIR, f"{r['video_id']}_{r['upload_date']}.md")
        print(f"  행 {r['row']}: {r['title']}")
        print(f"    JSON  : {r['tmp_path']}")
        print(f"    MD 출력: {md_path}")
        print(f"    완료 후: python tools/batch_processor.py --finalize {r['row']} {md_path}\n")


def run_finalize(row: int, md_path: str):
    sheet = _get_sheet()
    tmp_json = os.path.join(FETCH_TMP_DIR, f"japannews_batch_{row}.json")
    url = ""
    if os.path.exists(tmp_json):
        with open(tmp_json, encoding="utf-8") as f:
            data = json.load(f)
        url = data.get("url", "")

    try:
        pdf_path = md_path.replace(".md", ".pdf")
        markdown_to_pdf(open(md_path, encoding="utf-8").read(), pdf_path, url=url)
        drive_url = upload_pdf(CREDENTIALS_PATH, pdf_path, folder_id=DRIVE_FOLDER_ID or None)
        set_result(sheet, row, drive_url)
        if os.path.exists(tmp_json):
            os.unlink(tmp_json)
    except Exception as e:
        set_error(sheet, row, str(e)[:200])


def run_api_batch():
    from tools.text_to_markdown import text_to_markdown
    sheet = _get_sheet()
    for item in get_pending_rows(sheet):
        row, url = item["row"], item["url"]
        video_id = extract_video_id(url)
        try:
            set_status(sheet, row, STATUS_RUNNING)
            content = fetch_youtube_content(url)
            markdown = text_to_markdown(content)
            date = content.get("upload_date", "unknown")
            pdf_path = os.path.join(OUTPUT_DIR, f"{video_id}_{date}.pdf")
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            markdown_to_pdf(markdown, pdf_path, url=url)
            drive_url = upload_pdf(CREDENTIALS_PATH, pdf_path, folder_id=DRIVE_FOLDER_ID or None)
            set_result(sheet, row, drive_url)
        except Exception as e:
            set_error(sheet, row, str(e)[:200])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--finalize", nargs=2, metavar=("ROW", "MD_PATH"))
    args = parser.parse_args()

    if args.dry_run:
        run_dry()
    elif args.fetch:
        run_fetch()
    elif args.finalize:
        run_finalize(int(args.finalize[0]), args.finalize[1])
    else:
        run_api_batch()
```

---

### main.py
```python
import sys
from dotenv import load_dotenv
from tools.fetch_youtube import fetch_youtube_content
from tools.text_to_markdown import text_to_markdown
from tools.markdown_to_pdf import markdown_to_pdf

load_dotenv()


def process_youtube_to_pdf(url: str, output_path: str = "output/result.pdf") -> str:
    content = fetch_youtube_content(url)
    markdown = text_to_markdown(content)
    return markdown_to_pdf(markdown, output_path, url=url)


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=jOnVwFXTQG8"
    output = sys.argv[2] if len(sys.argv) > 2 else "output/result.pdf"
    process_youtube_to_pdf(url, output)
```

---

### .claude/commands/japannews.md
이 파일은 Claude Code에서 `/japannews <URL>` 슬래시 커맨드로 호출된다.
Claude가 직접 각 단계를 실행하는 방식이며, `$ARGUMENTS`에 YouTube URL이 주입된다.

```markdown
YouTube 일본어 뉴스 영상을 PDF 학습 자료로 변환합니다.

## 실행 절차

입력된 URL: $ARGUMENTS

### 1단계: YouTube 콘텐츠 수집
export PATH="/Users/minshik/Library/Python/3.9/bin:/opt/homebrew/bin:$PATH" 및
DYLD_LIBRARY_PATH=/opt/homebrew/lib 를 설정한 후 fetch_youtube_content() 호출.
결과(title, channel, upload_date, duration, transcript)를 확인.

### 2단계: 마크다운 직접 생성 (Claude 세션)
아래 규칙으로 마크다운을 직접 작성하여 output/{video_id}_{upload_date}.md 저장:
1. 제목은 H1(#), 채널명·날짜는 부제목
2. 타임스탬프 구간마다 H2(##) 섹션 — transcript를 실제 시간 흐름대로 빠짐없이 커버
3. 일본어 문장 테이블: | 일본어 문장 | 한국어 해석 |
4. 어휘 테이블: | 단어 (읽기) | 한국어 뜻 |
5. 후리가나: 漢字(よみ) 형식 (PDF 변환 시 ruby로 자동 변환)
6. transcript 전체를 커버할 것 — 내용 누락 금지

### 3단계: PDF 변환
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3으로 markdown_to_pdf() 호출.
output/{video_id}_{upload_date}.pdf 생성.

### 4단계: Google Drive 업로드
drive_uploader.upload_pdf() 호출 → 공개 링크 획득.
OAuth2 토큰은 config/oauth_token.pickle에 캐시됨 (첫 실행 시 브라우저 인증).

### 5단계: Google Sheets 기록
google_sheets.get_sheet() → ensure_header() → URL 중복 확인 후:
- 기존 행 있으면: set_result(sheet, row, drive_link)
- 없으면: append_result(sheet, url, title, channel, duration, upload_date, drive_link)
```

---

### .claude/settings.local.json
```json
{
  "env": {
    "DYLD_LIBRARY_PATH": "/opt/homebrew/lib"
  },
  "permissions": {
    "allow": [
      "Bash(yt-dlp:*)",
      "Bash(open:*)",
      "Bash(git init:*)",
      "Bash(git commit:*)",
      "Bash(git status:*)",
      "Bash(gh repo:*)",
      "Bash(git add:*)",
      "Bash(git push:*)",
      "Bash(brew install:*)",
      "Bash(/opt/homebrew/bin/python3:*)",
      "Bash(DYLD_LIBRARY_PATH=/opt/homebrew/lib /opt/homebrew/bin/python3:*)",
      "Bash(export PATH*)",
      "Bash(gh pr:*)"
    ]
  }
}
```

---

## Google 연동 설정

### Google Sheets (서비스 계정)
1. Google Cloud Console → APIs & Services → Credentials → Create Credentials → Service account
2. Keys 탭 → Add Key → JSON → `config/credentials.json`으로 저장
3. Google Sheets API + Google Drive API 활성화
4. 스프레드시트를 서비스 계정 이메일에 **편집자**로 공유

### Google Drive (OAuth2)
1. Google Cloud Console → OAuth 2.0 Client ID (Desktop app) → `config/oauth_client.json`으로 저장
2. 첫 실행 시 브라우저 인증 → `config/oauth_token.pickle` 자동 저장 (이후 자동 갱신)

### 스프레드시트 컬럼 구조 (A~H)
| A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|
| 유튜브 링크 | 영상 제목 | 채널명 | 영상 길이 | 업로드 날짜 | 등록 날짜 | 진행 여부 | PDF 결과 |

---

## 실행 예시

```bash
# 환경 설정
cp .env.example .env
pip install -r requirements.txt
export DYLD_LIBRARY_PATH=/opt/homebrew/lib   # macOS 필수

# Claude Code에서 슬래시 커맨드 (API 소비 없음)
/japannews https://www.youtube.com/watch?v=VIDEO_ID

# Python 직접 실행 (ANTHROPIC_API_KEY 필요)
python3 main.py https://www.youtube.com/watch?v=VIDEO_ID output/result.pdf

# 배치 처리
python3 tools/batch_processor.py --fetch
python3 tools/batch_processor.py --finalize 2 output/xxx.md
python3 tools/batch_processor.py --dry-run
```

---

## 주요 구현 원칙

1. **transcript 전체 커버**: 마크다운 생성 시 영상 길이에 비례해 내용을 빠짐없이 담을 것. 긴 영상일수록 H2 섹션을 더 많이 나눌 것.
2. **후리가나 형식**: `漢字(よみ)` — PDF 변환 시 `_convert_furigana_to_ruby()`가 자동으로 ruby 태그로 변환.
3. **Sheets 형식 일치**: `append_result()`를 사용해 기존 행과 동일한 8컬럼 구조로 기록.
4. **macOS WeasyPrint**: `DYLD_LIBRARY_PATH=/opt/homebrew/lib` 없이는 실행 불가.
5. **Drive 인증**: OAuth2 (`oauth_token.pickle`) — 서비스 계정 아님. Sheets는 서비스 계정.
```

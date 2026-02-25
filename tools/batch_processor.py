"""
배치 처리기 (Claude 세션 모드 지원)

모드:
  --dry-run          대기 목록만 출력
  --fetch            YouTube 콘텐츠 수집 → /tmp/japannews_batch_{row}.json 저장
                     (Claude 세션이 마크다운 생성 후 --finalize 호출)
  --finalize ROW MD  마크다운 파일을 받아 PDF 생성 → Drive 업로드 → Sheets 업데이트
  (인자 없음)        기존 방식: API로 end-to-end 처리

사용법:
  python tools/batch_processor.py --dry-run
  python tools/batch_processor.py --fetch
  python tools/batch_processor.py --finalize 2 output/xxx.md
  python tools/batch_processor.py                # API 방식
"""

import argparse
import json
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools.google_sheets import (
    get_sheet,
    get_pending_rows,
    set_status,
    set_result,
    set_error,
    ensure_header,
    STATUS_RUNNING,
)
from tools.drive_uploader import upload_pdf
from tools.fetch_youtube import fetch_youtube_content
from tools.markdown_to_pdf import markdown_to_pdf


# ── 환경 변수 ────────────────────────────────────────────────────────────────
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
    if not SPREADSHEET_ID:
        print("❌ GOOGLE_SPREADSHEET_ID 환경변수가 설정되지 않았습니다.")
        sys.exit(1)
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"❌ 인증 파일이 없습니다: {CREDENTIALS_PATH}")
        sys.exit(1)
    print("📋 Google Sheets 연결 중...")
    sheet = get_sheet(CREDENTIALS_PATH, SPREADSHEET_ID, SHEET_NAME)
    ensure_header(sheet)
    return sheet


# ── 모드 1: dry-run ──────────────────────────────────────────────────────────
def run_dry():
    sheet = _get_sheet()
    pending = get_pending_rows(sheet)
    if not pending:
        print("✅ 처리할 항목이 없습니다.")
        return
    print(f"🔍 대기 중인 항목: {len(pending)}개\n")
    for item in pending:
        print(f"  행 {item['row']}: {item['url']}")
    print("\n(dry-run 모드: 실제 처리하지 않음)")


# ── 모드 2: fetch (Claude 세션용) ────────────────────────────────────────────
def run_fetch():
    """
    YouTube 콘텐츠를 수집하고 JSON 파일로 저장.
    Claude 세션이 이 JSON을 읽어 마크다운을 직접 생성한 후 --finalize를 호출.
    """
    sheet = _get_sheet()
    pending = get_pending_rows(sheet)
    if not pending:
        print("✅ 처리할 항목이 없습니다.")
        return

    print(f"🔍 대기 중인 항목: {len(pending)}개\n")
    results = []

    for item in pending:
        row = item["row"]
        url = item["url"]
        video_id = extract_video_id(url)
        print(f"▶ [{row}행] {url}")

        try:
            set_status(sheet, row, STATUS_RUNNING)
            print(f"  [1/1] YouTube 콘텐츠 수집 중...")
            content = fetch_youtube_content(url)
            print(f"        제목: {content['title']}")

            # JSON으로 저장
            tmp_path = os.path.join(FETCH_TMP_DIR, f"japannews_batch_{row}.json")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({"row": row, "url": url, "video_id": video_id, "content": content}, f, ensure_ascii=False, indent=2)

            results.append({
                "row": row,
                "url": url,
                "video_id": video_id,
                "title": content["title"],
                "upload_date": content.get("upload_date", "unknown"),
                "tmp_path": tmp_path,
            })
            print(f"  ✅ 수집 완료 → {tmp_path}\n")

        except Exception as e:
            print(f"  ❌ 수집 오류: {e}\n")
            set_error(sheet, row, str(e)[:200])

    # Claude 세션을 위한 안내 출력
    print("=" * 50)
    print("📌 Claude가 아래 파일들을 읽어 마크다운을 생성해야 합니다:\n")
    for r in results:
        md_path = os.path.join(OUTPUT_DIR, f"{r['video_id']}_{r['upload_date']}.md")
        print(f"  행 {r['row']}: {r['title']}")
        print(f"    JSON  : {r['tmp_path']}")
        print(f"    MD 출력: {md_path}")
        print(f"    완료 후: python tools/batch_processor.py --finalize {r['row']} {md_path}\n")


# ── 모드 3: finalize ─────────────────────────────────────────────────────────
def run_finalize(row: int, md_path: str):
    """
    Claude가 생성한 마크다운을 받아 PDF 변환 → Drive 업로드 → Sheets 업데이트.
    """
    sheet = _get_sheet()

    if not os.path.exists(md_path):
        print(f"❌ 마크다운 파일이 없습니다: {md_path}")
        sys.exit(1)

    # JSON에서 URL 복원
    tmp_json = os.path.join(FETCH_TMP_DIR, f"japannews_batch_{row}.json")
    url = ""
    if os.path.exists(tmp_json):
        with open(tmp_json, encoding="utf-8") as f:
            data = json.load(f)
        url = data.get("url", "")

    print(f"▶ [{row}행] finalize 시작")

    try:
        # PDF 변환
        pdf_path = md_path.replace(".md", ".pdf")
        print(f"  [1/2] PDF 생성 중...")
        markdown_content = open(md_path, encoding="utf-8").read()
        markdown_to_pdf(markdown_content, pdf_path, url=url)
        print(f"        저장: {pdf_path}")

        # Drive 업로드
        print(f"  [2/2] Google Drive 업로드 중...")
        drive_url = upload_pdf(
            CREDENTIALS_PATH,
            pdf_path,
            folder_id=DRIVE_FOLDER_ID or None,
        )
        print(f"        업로드 완료: {drive_url}")

        set_result(sheet, row, drive_url)
        print(f"  ✅ Sheets 업데이트 완료\n")

        # 임시 파일 정리
        if os.path.exists(tmp_json):
            os.unlink(tmp_json)

    except Exception as e:
        print(f"  ❌ 오류: {e}\n")
        set_error(sheet, row, str(e)[:200])


# ── 모드 4: API 방식 (기존) ──────────────────────────────────────────────────
def run_api_batch():
    from tools.text_to_markdown import text_to_markdown

    sheet = _get_sheet()
    pending = get_pending_rows(sheet)
    if not pending:
        print("✅ 처리할 항목이 없습니다.")
        return

    print(f"🔍 대기 중인 항목: {len(pending)}개\n")
    success = fail = 0

    for item in pending:
        row, url = item["row"], item["url"]
        video_id = extract_video_id(url)
        print(f"▶ [{row}행] {url}")
        try:
            set_status(sheet, row, STATUS_RUNNING)
            content = fetch_youtube_content(url)
            print(f"  제목: {content['title']}")
            markdown = text_to_markdown(content)
            date = content.get("upload_date", "unknown")
            pdf_path = os.path.join(OUTPUT_DIR, f"{video_id}_{date}.pdf")
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            markdown_to_pdf(markdown, pdf_path, url=url)
            drive_url = upload_pdf(CREDENTIALS_PATH, pdf_path, folder_id=DRIVE_FOLDER_ID or None)
            set_result(sheet, row, drive_url)
            print(f"  ✅ 완료: {drive_url}\n")
            success += 1
        except Exception as e:
            print(f"  ❌ 오류: {e}\n")
            set_error(sheet, row, str(e)[:200])
            fail += 1

    print(f"═══════════════════════════════")
    print(f"완료: {success}개  |  오류: {fail}개")


# ── 진입점 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Japan News 배치 처리기")
    parser.add_argument("--dry-run",  action="store_true", help="대기 목록만 출력")
    parser.add_argument("--fetch",    action="store_true", help="YouTube 수집 (Claude 세션용)")
    parser.add_argument("--finalize", nargs=2, metavar=("ROW", "MD_PATH"), help="PDF 변환 + Drive 업로드")
    args = parser.parse_args()

    if args.dry_run:
        run_dry()
    elif args.fetch:
        run_fetch()
    elif args.finalize:
        run_finalize(int(args.finalize[0]), args.finalize[1])
    else:
        run_api_batch()

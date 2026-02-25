"""
배치 처리기
Google Sheets의 대기 중인 YouTube URL을 순서대로 처리:
  1. Sheets에서 '대기' 행 읽기
  2. 상태 → '실행중'
  3. YouTube → PDF 변환 (기존 파이프라인)
  4. PDF → Google Drive 업로드
  5. Sheets 업데이트 (링크 + '완료')

사용법:
  python tools/batch_processor.py
  python tools/batch_processor.py --dry-run   # 실제 처리 없이 대기 목록만 출력
"""

import argparse
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
from tools.text_to_markdown import text_to_markdown
from tools.markdown_to_pdf import markdown_to_pdf


# ── 환경 변수 ────────────────────────────────────────────────────────────────
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "config/credentials.json")
SPREADSHEET_ID   = os.getenv("GOOGLE_SPREADSHEET_ID", "")
DRIVE_FOLDER_ID  = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")   # 비어있으면 루트
SHEET_NAME       = os.getenv("GOOGLE_SHEET_NAME", "Sheet1")
OUTPUT_DIR       = "output"


def extract_video_id(url: str) -> str:
    match = re.search(r"v=([^&]+)", url)
    return match.group(1) if match else re.sub(r"[^a-zA-Z0-9_-]", "_", url)[:20]


def process_url(url: str) -> str:
    """단일 URL 처리 → PDF 경로 반환"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"  [1/3] YouTube 콘텐츠 가져오는 중...")
    content = fetch_youtube_content(url)
    print(f"        제목: {content['title']}")

    print(f"  [2/3] 마크다운 변환 중...")
    markdown = text_to_markdown(content)

    video_id = extract_video_id(url)
    date = content.get("upload_date", "unknown")
    pdf_filename = f"{video_id}_{date}.pdf"
    pdf_path = os.path.join(OUTPUT_DIR, pdf_filename)

    print(f"  [3/3] PDF 생성 중...")
    markdown_to_pdf(markdown, pdf_path, url=url)
    print(f"        저장: {pdf_path}")

    return pdf_path


def run_batch(dry_run: bool = False):
    # 설정 검증
    if not SPREADSHEET_ID:
        print("❌ GOOGLE_SPREADSHEET_ID 환경변수가 설정되지 않았습니다.")
        print("   .env 파일을 확인하세요.")
        sys.exit(1)
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"❌ 인증 파일이 없습니다: {CREDENTIALS_PATH}")
        print("   config/credentials.json 위치에 서비스 계정 키를 배치하세요.")
        sys.exit(1)

    print("📋 Google Sheets 연결 중...")
    sheet = get_sheet(CREDENTIALS_PATH, SPREADSHEET_ID, SHEET_NAME)
    ensure_header(sheet)

    pending = get_pending_rows(sheet)
    if not pending:
        print("✅ 처리할 항목이 없습니다.")
        return

    print(f"🔍 대기 중인 항목: {len(pending)}개\n")
    for item in pending:
        print(f"  행 {item['row']}: {item['url']}")

    if dry_run:
        print("\n(dry-run 모드: 실제 처리하지 않음)")
        return

    print()
    success = 0
    fail = 0

    for item in pending:
        row = item["row"]
        url = item["url"]
        print(f"▶ [{row}행] {url}")

        try:
            set_status(sheet, row, STATUS_RUNNING)

            pdf_path = process_url(url)

            print(f"  [4/4] Google Drive 업로드 중...")
            drive_url = upload_pdf(
                CREDENTIALS_PATH,
                pdf_path,
                folder_id=DRIVE_FOLDER_ID or None,
            )
            print(f"        업로드 완료: {drive_url}")

            set_result(sheet, row, drive_url)
            print(f"  ✅ 완료\n")
            success += 1

        except Exception as e:
            error_msg = str(e)[:200]
            print(f"  ❌ 오류: {error_msg}\n")
            set_error(sheet, row, error_msg)
            fail += 1

    print(f"═══════════════════════════════")
    print(f"완료: {success}개  |  오류: {fail}개")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Japan News 배치 처리기")
    parser.add_argument("--dry-run", action="store_true", help="대기 목록만 출력, 처리 안 함")
    args = parser.parse_args()
    run_batch(dry_run=args.dry_run)

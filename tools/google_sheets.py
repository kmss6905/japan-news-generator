"""
Google Sheets 연동 헬퍼
- 배치 처리 대상 URL 읽기
- 처리 상태 및 결과 링크 업데이트

스프레드시트 컬럼 구조:
  A: YouTube URL (입력)
  B: PDF 링크 (결과)
  C: 상태 (대기 / 실행중 / 완료 / 오류)
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

COL_URL = 1     # A
COL_PDF = 2     # B
COL_STATUS = 3  # C


def get_client(credentials_path: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet(credentials_path: str, spreadsheet_id: str, sheet_name: str = "Sheet1"):
    client = get_client(credentials_path)
    spreadsheet = client.open_by_key(spreadsheet_id)
    return spreadsheet.worksheet(sheet_name)


def get_pending_rows(sheet) -> list[dict]:
    """상태가 '대기'이거나 비어있는 행 반환 (헤더 행 제외)"""
    rows = sheet.get_all_values()
    pending = []
    for i, row in enumerate(rows[1:], start=2):  # 1-indexed, 헤더 스킵
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


def set_error(sheet, row: int, message: str):
    sheet.update_cell(row, COL_PDF, f"오류: {message}")
    sheet.update_cell(row, COL_STATUS, STATUS_ERROR)


def ensure_header(sheet):
    """헤더 행이 없으면 자동 생성"""
    first_row = sheet.row_values(1)
    if not first_row or first_row[0] != "유튜브 링크":
        sheet.update("A1:C1", [["유튜브 링크", "결과 PDF", "진행 여부"]])
        # 헤더 굵게
        sheet.format("A1:C1", {"textFormat": {"bold": True}})

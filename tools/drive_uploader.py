"""
Google Drive 업로드 헬퍼
- PDF 파일을 지정 폴더에 업로드
- 링크 공유 권한 설정 (누구나 열람 가능)
- 공유 URL 반환
"""

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
import os

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]


def get_drive_service(credentials_path: str):
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def upload_pdf(
    credentials_path: str,
    pdf_path: str,
    folder_id: str = None,
    file_name: str = None,
) -> str:
    """
    PDF를 Google Drive에 업로드하고 공유 URL 반환.

    Args:
        credentials_path: 서비스 계정 JSON 키 경로
        pdf_path: 업로드할 PDF 파일 경로
        folder_id: 업로드 대상 Drive 폴더 ID (None이면 루트)
        file_name: Drive에 저장될 파일명 (None이면 원본 파일명 사용)

    Returns:
        str: 공개 열람 가능한 Google Drive URL
    """
    service = get_drive_service(credentials_path)

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

    # 누구나 링크로 열람 가능하도록 권한 설정
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view"

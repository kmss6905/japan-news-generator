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

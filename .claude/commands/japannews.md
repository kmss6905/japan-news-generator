YouTube 일본어 뉴스 영상을 PDF 학습 자료로 변환합니다.

## 사용법
```
/japannews <YouTube_URL>
```

## 실행 절차

입력된 URL: $ARGUMENTS

### 1단계: YouTube 콘텐츠 수집

아래 명령어를 실행하여 영상 정보를 가져오세요:

```bash
export PATH="/Users/minshik/Library/Python/3.9/bin:/opt/homebrew/bin:$PATH" && DYLD_LIBRARY_PATH=/opt/homebrew/lib /opt/homebrew/bin/python3 -c "
import json, sys
sys.path.insert(0, '.')
from tools.fetch_youtube import fetch_youtube_content
content = fetch_youtube_content('$ARGUMENTS')
print(json.dumps(content, ensure_ascii=False, indent=2))
"
```

### 2단계: 마크다운 생성

수집된 콘텐츠를 바탕으로 아래 규칙에 따라 마크다운을 직접 생성하세요 (Claude API 호출 없이 Claude 세션이 직접 생성):

**규칙:**
1. 제목은 H1(`#`), 채널명과 날짜는 부제목으로 표기
2. 타임스탬프(00:00, 03:40 등)는 H2(`##`) 섹션으로 분리
3. 일본어 문장(뉴스 본문)은 아래 테이블 형식:
   ```
   | 일본어 문장 | 한국어 해석 |
   |---|---|
   | (일본어 원문) | (한국어 번역) |
   ```
4. 일본어 단어/어휘 목록은 아래 테이블 형식:
   ```
   | 단어 (읽기) | 한국어 뜻 |
   |---|---|
   | 단어(よみ) | 뜻 |
   ```
5. 후리가나는 `漢字(よみ)` 형식으로 작성 (PDF 변환 시 자동으로 루비 태그로 변환됨)
6. 마크다운 형식만 출력하고, 다른 설명은 하지 마세요

생성한 마크다운을 output 디렉토리에 `.md` 파일로 저장하세요.
파일명 형식: `output/{video_id}_{upload_date}.md`

### 3단계: PDF 변환

마크다운 파일이 저장되면 아래 명령어로 PDF를 생성하세요:

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib /opt/homebrew/bin/python3 -c "
from tools.markdown_to_pdf import markdown_to_pdf
md = open('{md_path}', encoding='utf-8').read()
pdf = markdown_to_pdf(md, '{pdf_path}', url='$ARGUMENTS')
print(f'PDF 저장 완료: {pdf}')
"
```

### 4단계: Google Drive 업로드

PDF가 생성되면 아래 명령어로 Drive에 업로드하세요:

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib /opt/homebrew/bin/python3 -c "
import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from tools.drive_uploader import upload_pdf
folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
link = upload_pdf('', '{pdf_path}', folder_id=folder_id)
print(f'Drive 업로드 완료: {link}')
"
```

### 5단계: Google Sheets 기록

Drive 업로드가 완료되면 아래 명령어로 스프레드시트에 결과를 기록하세요:

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib /opt/homebrew/bin/python3 -c "
import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from tools.google_sheets import get_sheet, ensure_header, set_result, append_result

creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'config/credentials.json')
spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
sheet_name = os.getenv('GOOGLE_SHEET_NAME', 'Sheet1')
url = '$ARGUMENTS'
drive_link = '{drive_link}'
title = '{title}'
channel = '{channel}'
duration = '{duration}'
upload_date = '{upload_date}'

sheet = get_sheet(creds_path, spreadsheet_id, sheet_name)
ensure_header(sheet)

rows = sheet.get_all_values()
found_row = None
for i, row in enumerate(rows[1:], start=2):
    if len(row) >= 1 and row[0].strip() == url:
        found_row = i
        break

if found_row:
    set_result(sheet, found_row, drive_link)
    print(f'기존 행 {found_row} 업데이트 완료')
else:
    append_result(sheet, url, title, channel, duration, upload_date, drive_link)
    print('새 행 추가 완료')
"
```

완료 후 PDF 경로와 Drive 링크를 알려주세요.

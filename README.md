# 🗞️ Japan News Generator

YouTube 일본어 뉴스 영상을 **PDF 학습 자료**로 자동 변환하는 도구.

영상 설명글·자막에서 일본어 문장과 어휘를 추출하여 표 형식의 마크다운으로 정리하고, PDF로 저장합니다.
생성된 PDF는 Google Drive에 업로드되고 Google Sheets에 링크가 자동 기록됩니다.

---

## PDF 출력 예시

실제 생성된 샘플 PDF → **[examples/sample.pdf](examples/sample.pdf)**

### PDF 구성

PDF는 다음 구조로 생성됩니다.

```
┌─────────────────────────────────────────────────────┬──────────┐
│ 영상 제목                                            │ QR Code  │
│ 채널: ○○○  |  날짜: YYYY-MM-DD                      │ (YouTube │
├─────────────────────────────────────────────────────┤  원본링크)│
│ ## 00:00  섹션명                                    └──────────┘
├───────────────────────────────┬─────────────────────────────────┤
│ 일본어 문장                   │ 한국어 해석                     │
├───────────────────────────────┼─────────────────────────────────┤
│ 今日の最低気温はマイナス13.2℃ │ 오늘 최저기온은 영하 13.2℃로,  │
│ と、今シーズン最も低くなりました。│ 이번 시즌 가장 낮아졌습니다.  │
├───────────────────────────────┴─────────────────────────────────┤
│ ## 어휘                                                         │
├───────────────────────┬─────────────────────────────────────────┤
│ 단어 (읽기)           │ 한국어 뜻                               │
├───────────────────────┼─────────────────────────────────────────┤
│ 凍(こお)る            │ 얼다                                    │
│ 寒波(かんぱ)          │ 한파                                    │
└───────────────────────┴─────────────────────────────────────────┘
```

- **QR 코드**: PDF 제목 우측에 YouTube 원본 링크 QR 코드 삽입
- **페이지 구분**: 뉴스 섹션(h2)마다 항상 새 페이지 상단에서 시작

---

## 처리 흐름

```
fetch_youtube     YouTube URL → 설명글 + VTT 자막 (yt-dlp)
    ↓
자막 교정          설명글 스크립트로 VTT 인식 오류 교정
    ↓
text_to_markdown  마크다운 테이블 생성 (Claude)
    ↓
markdown_to_pdf   마크다운 → PDF (WeasyPrint + QR 코드)
    ↓
drive_uploader    PDF → Google Drive 업로드 (OAuth2)
    ↓
google_sheets     결과 링크 + 완료 상태 기록
```

---

## 설치

### 시스템 의존성

```bash
brew install yt-dlp pandoc pango glib
```

### Python 패키지

```bash
pip install anthropic youtube-transcript-api python-dotenv weasyprint "qrcode[pil]"
pip install gspread google-api-python-client google-auth-oauthlib
```

### 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일 설정:

```env
# Anthropic API (방법 1 직접 실행 시만 필요)
ANTHROPIC_API_KEY=sk-ant-...

# macOS WeasyPrint 필수
DYLD_LIBRARY_PATH=/opt/homebrew/lib

# Google 연동 (배치 처리 시 필요)
GOOGLE_CREDENTIALS_PATH=config/credentials.json
GOOGLE_SPREADSHEET_ID=스프레드시트_ID
GOOGLE_DRIVE_FOLDER_ID=Drive_폴더_ID
GOOGLE_SHEET_NAME=시트1
```

---

## 사용법

### 방법 1: Claude Code 스킬 — 단일 영상

Claude Code 세션에서 URL 한 줄로 PDF까지 자동 생성:

```
/japannews https://www.youtube.com/watch?v=jOnVwFXTQG8
```

처리 순서:
1. `yt-dlp`로 설명글 + VTT 자막 수집
2. 설명글 스크립트로 자막 인식 오류 교정
3. Claude가 마크다운 직접 생성 (API 키 불필요)
4. WeasyPrint로 PDF 변환 → `output/` 저장

---

### 방법 2: Claude Code 스킬 — 배치 처리 (Google Sheets 연동)

Google Sheets에 YouTube URL 목록을 넣어두면 일괄 처리 후 Drive 링크를 자동 기록합니다.

#### 스프레드시트 컬럼 구조

| 유튜브 링크 | 결과 PDF | 진행 여부 |
|---|---|---|
| https://youtube.com/... | (Drive 링크 자동 기록) | 대기 / 실행중 / 완료 / 오류 |

#### Google 초기 설정 (최초 1회)

1. **서비스 계정 생성** (Sheets 읽기/쓰기용)
   - Google Cloud Console → API 및 서비스 → 사용자 인증 정보 → 서비스 계정
   - JSON 키 다운로드 → `config/credentials.json` 저장
   - 서비스 계정 이메일로 스프레드시트 **편집자** 공유

2. **OAuth2 클라이언트 생성** (Drive 업로드용)
   - Google Cloud Console → OAuth 클라이언트 ID → 데스크톱 앱
   - JSON 다운로드 → `config/oauth_client.json` 저장
   - Drive 업로드 폴더를 서비스 계정 이메일로 **편집자** 공유

3. **최초 Drive 인증** (브라우저 1회)
   - `python3 -c "from tools.drive_uploader import get_drive_service; get_drive_service()"`
   - 브라우저 인증 완료 → `config/oauth_token.pickle` 자동 저장

#### 배치 실행 (Claude Code 세션 모드)

```bash
# 1. 대기 목록 확인
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 tools/batch_processor.py --dry-run

# 2. YouTube 콘텐츠 수집 → /tmp/japannews_batch_{row}.json 저장
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 tools/batch_processor.py --fetch

# 3. Claude 세션에서 각 JSON을 읽어 마크다운 생성 (/japannews 방식과 동일)

# 4. PDF + Drive + Sheets 처리
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 tools/batch_processor.py --finalize {row} output/{video_id}_{date}.md
```

또는 Claude Code 스킬로 한 번에:

```
/japannews-batch
```

#### 배치 실행 (API 모드 — Anthropic API 크레딧 있을 때)

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 tools/batch_processor.py
```

---

### 방법 3: Python 직접 실행 (Anthropic API 키 필요)

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 main.py https://www.youtube.com/watch?v=XXXX
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 main.py https://www.youtube.com/watch?v=XXXX output/my.pdf
```

---

## 파일 구조

```
japan-news-generator/
├── main.py                      # 엔트리포인트 (단일 영상 처리)
├── tools/
│   ├── fetch_youtube.py         # YouTube 콘텐츠 수집 (yt-dlp)
│   ├── text_to_markdown.py      # 마크다운 변환 (Claude API)
│   ├── markdown_to_pdf.py       # PDF 변환 (WeasyPrint + QR 코드)
│   ├── google_sheets.py         # Google Sheets 읽기/쓰기
│   ├── drive_uploader.py        # Google Drive 업로드 (OAuth2)
│   └── batch_processor.py       # 배치 처리 오케스트레이터
├── config/
│   ├── credentials.json         # Google 서비스 계정 키 (gitignore)
│   ├── oauth_client.json        # OAuth2 클라이언트 (gitignore)
│   └── oauth_token.pickle       # OAuth2 토큰 캐시 (gitignore)
├── skill/
│   └── SKILL.md                 # /japannews 스킬 정의
├── examples/
│   └── sample.pdf               # 생성 결과 샘플
├── output/                      # 생성된 마크다운 + PDF (gitignore)
├── .env                         # 환경변수 (gitignore)
├── .env.example                 # 환경변수 템플릿
└── .gitignore
```

---

## 주의사항

- macOS에서 `DYLD_LIBRARY_PATH=/opt/homebrew/lib` 없으면 WeasyPrint 실행 불가
- Google Drive 업로드는 OAuth2 사용자 인증 방식 (서비스 계정은 개인 Drive 업로드 불가)
- `oauth_token.pickle`은 약 6개월 후 만료 → 만료 시 자동으로 브라우저 재인증 요청
- `output/`, `config/*.json`, `config/*.pickle` 은 `.gitignore`에 포함

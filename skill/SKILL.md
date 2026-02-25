---
name: japannews
description: |
  YouTube 일본어 뉴스 영상 URL을 받아 PDF 학습 자료로 자동 변환.
  yt-dlp로 설명글을 가져오고, Claude가 직접 마크다운으로 포맷한 후 PDF로 변환.
  "/japannews https://youtube.com/watch?v=..." 형식으로 호출.
---

# Japan News PDF Generator Skill

YouTube 일본어 뉴스 영상을 PDF 학습 자료로 변환하는 skill.

## 실행 순서

### Step 1: URL 파싱

사용자 입력에서 YouTube URL을 추출한다.
- 형식: `/japannews https://www.youtube.com/watch?v=XXXX`
- args에서 URL을 파싱

### Step 2: yt-dlp로 영상 메타데이터 + 설명글 가져오기

```bash
yt-dlp --dump-json --no-download "{URL}"
```

JSON에서 다음을 추출:
- `title`: 영상 제목
- `channel`: 채널명
- `upload_date`: 업로드 날짜 (YYYYMMDD → YYYY-MM-DD 변환)
- `description`: 설명글 (학습 콘텐츠 포함)

### Step 3: Claude가 직접 마크다운으로 변환 (API 키 불필요)

Claude가 Step 2에서 가져온 description을 분석하여 아래 규칙으로 마크다운을 직접 생성:

#### 마크다운 구조 규칙

```
# {title}
**채널**: {channel} | **날짜**: {upload_date}

---

## {타임스탬프} {섹션명}

### 본문

| 일본어 문장 | 한국어 해석 |
|---|---|
| (일본어 원문 문장) | (한국어 번역) |

### 어휘

| 단어 (읽기) | 한국어 뜻 |
|---|---|
| 단어 [읽기] | 뜻 |
```

#### 파싱 규칙

1. **타임스탬프 섹션 분리**: `00:00`, `03:40`, `06:23` 등 타임스탬프를 H2(##) 섹션으로 분리
2. **일본어 문장 식별**: 한자/히라가나/가타카나가 포함된 줄이 문장 (길이 15자 이상)
3. **어휘 목록 식별**: `단어 [읽기] 한국어뜻` 패턴 (짧은 줄, 단어+설명 형식)
4. **한국어 번역 생성**: 일본어 문장에 대해 Claude가 직접 자연스러운 한국어 번역 제공

### Step 4: 마크다운 파일 저장

```bash
# 파일명: 영상ID_YYYYMMDD.md
OUTPUT_DIR="/Users/minshik/ai/japan-news-generator/output"
MD_FILE="${OUTPUT_DIR}/{video_id}_{date}.md"
```

Write 도구로 마크다운 저장 (Bash echo 사용 금지 - UTF-8 인코딩 보장)

### Step 5: PDF 변환

```bash
cd /Users/minshik/ai/japan-news-generator
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 tools/markdown_to_pdf.py
```

`markdown_to_pdf.py`를 직접 호출하되, 입력 파일 경로와 출력 PDF 경로를 지정:

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 -c "
import sys
sys.path.insert(0, '/Users/minshik/ai/japan-news-generator')
from tools.markdown_to_pdf import markdown_to_pdf
pdf = markdown_to_pdf(open('{MD_FILE}', encoding='utf-8').read(), '{PDF_FILE}')
print(pdf)
"
```

### Step 6: 완료 보고

사용자에게 다음을 출력:
- 생성된 PDF 경로
- 영상 제목
- 섹션 수 / 문장 수 / 어휘 수 요약

---

## 파일 경로

| 항목 | 경로 |
|------|------|
| 프로젝트 루트 | `/Users/minshik/ai/japan-news-generator/` |
| tools 디렉토리 | `/Users/minshik/ai/japan-news-generator/tools/` |
| 출력 디렉토리 | `/Users/minshik/ai/japan-news-generator/output/` |
| markdown_to_pdf | `/Users/minshik/ai/japan-news-generator/tools/markdown_to_pdf.py` |

## 환경 설정

weasyprint 사용 시 반드시 필요:
```bash
export DYLD_LIBRARY_PATH=/opt/homebrew/lib
```

## 에러 처리

| 에러 | 대처 |
|------|------|
| yt-dlp 실패 | URL 형식 확인 후 재시도 안내 |
| 설명글 없음 | "이 영상은 설명글이 없습니다" 안내 |
| PDF 변환 실패 | 마크다운 파일 경로 안내 (직접 열기 가능) |
| DYLD_LIBRARY_PATH 누락 | 해당 환경변수 설정 후 재시도 |

## 사용 예시

```
/japannews https://www.youtube.com/watch?v=jOnVwFXTQG8
```

출력 예시:
```
✓ YouTube 콘텐츠 가져오기 완료
  제목: 뉴스로 배우는 일본어, 아나운서 발음 구간 반복듣기, 漢江ラーメン
  채널: 미디어일본어

✓ 마크다운 변환 완료
  4개 섹션 | 12개 문장 | 38개 어휘

✓ PDF 생성 완료
  경로: /Users/minshik/ai/japan-news-generator/output/jOnVwFXTQG8_2026-02-22.pdf
```

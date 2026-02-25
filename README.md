# 🗞️ Japan News Generator

YouTube 일본어 뉴스 영상을 **PDF 학습 자료**로 자동 변환하는 도구.

영상 설명글에서 일본어 문장과 어휘를 추출하여 표 형식의 마크다운으로 정리하고, PDF로 저장합니다.

---

## 결과물 예시

| 일본어 문장 | 한국어 해석 |
|---|---|
| 今日の最低気温はマイナス13.2℃と、今シーズン最も低くなりました。 | 오늘 최저기온은 영하 13.2℃로, 이번 시즌 가장 낮아졌습니다. |
| 日本では最長寒波の影響で各地で大雪への警戒が高まっています。 | 일본에서는 역대 최장 한파의 영향으로 각지에서 대설 경계가 높아지고 있습니다. |

| 단어 (읽기) | 한국어 뜻 |
|---|---|
| 凍(こお)る | 얼다 |
| 寒波(かんぱ) | 한파 |
| 積雪(せきせつ) | 적설 |

---

## 구조

```
Tool 0: fetch_youtube      YouTube URL → 설명글 + 자막 (yt-dlp + youtube-transcript-api)
    ↓
Tool 1: text_to_markdown   설명글 → 마크다운 테이블 (Claude API)
    ↓
Tool 2: markdown_to_pdf    마크다운 → PDF (pandoc + weasyprint)
```

---

## 설치

### 시스템 의존성

```bash
# yt-dlp
brew install yt-dlp

# pandoc
brew install pandoc

# weasyprint 의존성 (macOS)
brew install pango glib
```

### Python 패키지

```bash
pip install anthropic youtube-transcript-api python-dotenv weasyprint
```

### 환경변수 설정

```bash
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY 입력
```

---

## 사용법

### 기본 실행

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 main.py https://www.youtube.com/watch?v=jOnVwFXTQG8
```

### 출력 경로 지정

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 main.py https://www.youtube.com/watch?v=XXXX output/my.pdf
```

### Claude Code 스킬로 실행

```
/japannews https://www.youtube.com/watch?v=jOnVwFXTQG8
```

> Claude Code를 사용 중이라면 `/japannews` 스킬 한 줄로 PDF까지 자동 생성됩니다.

---

## 파일 구조

```
japan-news-generator/
├── main.py                  # 엔트리포인트 (3개 tool 체인 실행)
├── tools/
│   ├── fetch_youtube.py     # Tool 0: YouTube 콘텐츠 수집
│   ├── text_to_markdown.py  # Tool 1: 마크다운 변환 (Claude API)
│   └── markdown_to_pdf.py   # Tool 2: PDF 변환
├── output/                  # 생성된 마크다운 + PDF 저장 (gitignore)
├── .env.example             # 환경변수 템플릿
└── .gitignore
```

---

## 주의사항

- `DYLD_LIBRARY_PATH=/opt/homebrew/lib` 설정이 없으면 weasyprint가 실행되지 않습니다 (macOS)
- 영상 설명글이 없거나 일본어 학습 포맷이 아닌 경우 마크다운 품질이 달라질 수 있습니다
- `output/` 폴더는 `.gitignore`에 포함되어 있어 git에 올라가지 않습니다

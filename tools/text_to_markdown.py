"""
Tool 1: Text → Markdown 변환
- Claude API를 호출해 일본어 학습 콘텐츠를 구조화된 마크다운으로 변환
- 일본어 문장 → | 일본어 문장 | 한국어 해석 | 테이블
- 일본어 단어 → | 단어 (읽기) | 뜻 | 테이블
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


if __name__ == "__main__":
    sample_content = {
        "title": "뉴스로 배우는 일본어, 漢江ラーメン",
        "channel": "미디어일본어",
        "upload_date": "20260222",
        "description": """00:00 1/4 page
今日の最低気温はマイナス13.2℃と, 今シーズン最も低くなりました。
今(こん)シーズン 이번시즌
最(もっと)も 가장
低(ひく)い 낮다""",
    }
    markdown = text_to_markdown(sample_content)
    print(markdown)

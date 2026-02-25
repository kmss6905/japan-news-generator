"""
Japan News Generator - 메인 실행 파일
YouTube 일본어 뉴스 영상을 PDF 학습 자료로 변환합니다.

흐름:
  Tool 0: fetch_youtube  → YouTube URL에서 설명글 + 자막 추출
  Tool 1: text_to_markdown → Claude API로 마크다운 변환
  Tool 2: markdown_to_pdf  → pandoc + weasyprint로 PDF 생성
"""

import sys
from dotenv import load_dotenv
from tools.fetch_youtube import fetch_youtube_content
from tools.text_to_markdown import text_to_markdown
from tools.markdown_to_pdf import markdown_to_pdf

load_dotenv()


def process_youtube_to_pdf(url: str, output_path: str = "output/result.pdf") -> str:
    print(f"\n[1/3] YouTube 콘텐츠 가져오는 중...")
    content = fetch_youtube_content(url)
    print(f"  ✓ 제목: {content['title']}")
    print(f"  ✓ 채널: {content['channel']}")

    print(f"\n[2/3] 마크다운으로 변환 중 (Claude API)...")
    markdown = text_to_markdown(content)
    print(f"  ✓ 마크다운 생성 완료 ({len(markdown)} chars)")

    print(f"\n[3/3] PDF 생성 중...")
    pdf_path = markdown_to_pdf(markdown, output_path)
    print(f"  ✓ PDF 저장 완료: {pdf_path}")

    return pdf_path


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=jOnVwFXTQG8"
    output = sys.argv[2] if len(sys.argv) > 2 else "output/result.pdf"

    print("=" * 50)
    print("Japan News Generator")
    print("=" * 50)
    process_youtube_to_pdf(url, output)
    print("\n완료!")

"""
Tool 2: Markdown → PDF 변환
- pandoc: markdown → HTML 변환
- weasyprint: HTML → PDF 변환 (일본어 폰트 지원)
"""

import os
import subprocess
import tempfile
from weasyprint import HTML, CSS

CSS_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');

body {
    font-family: "Noto Sans JP", "Hiragino Sans", "Yu Gothic", "Meiryo", sans-serif;
    font-size: 13px;
    line-height: 1.9;
    margin: 0;
    padding: 40px;
    color: #2c2c2c;
    background: white;
}

h1 {
    font-size: 22px;
    color: #1a237e;
    border-bottom: 3px solid #1a237e;
    padding-bottom: 10px;
    margin-bottom: 6px;
}

h2 {
    font-size: 16px;
    color: #283593;
    background-color: #e8eaf6;
    padding: 6px 12px;
    border-left: 4px solid #3949ab;
    margin-top: 28px;
    margin-bottom: 12px;
}

p {
    margin: 4px 0;
    color: #555;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 20px 0;
    font-size: 13px;
}

th {
    background-color: #3949ab;
    color: white;
    padding: 9px 12px;
    text-align: left;
    font-weight: bold;
}

td {
    border: 1px solid #c5cae9;
    padding: 8px 12px;
    vertical-align: top;
}

tr:nth-child(even) td {
    background-color: #f3f4fb;
}

tr:hover td {
    background-color: #e8eaf6;
}
"""


def markdown_to_pdf(markdown_text: str, output_path: str = "output/result.pdf") -> str:
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    # 1단계: pandoc으로 markdown → HTML 변환
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(markdown_text)
        md_path = f.name

    html_path = md_path.replace(".md", ".html")

    subprocess.run(
        [
            "pandoc",
            md_path,
            "-o", html_path,
            "--standalone",
            "--metadata", "charset=utf-8",
        ],
        check=True,
    )

    # 2단계: weasyprint로 HTML → PDF 변환
    HTML(filename=html_path).write_pdf(
        output_path,
        stylesheets=[CSS(string=CSS_STYLE)],
    )

    # 임시 파일 정리
    os.unlink(md_path)
    os.unlink(html_path)

    return output_path


if __name__ == "__main__":
    sample_md = """# 테스트 문서

## 00:00 1/4 page

| 일본어 문장 | 한국어 해석 |
|---|---|
| 今日の最低気温はマイナス13.2℃と、今シーズン最も低くなりました。 | 오늘 최저기온은 영하 13.2℃로, 이번 시즌 가장 낮아졌습니다. |

| 단어 (읽기) | 한국어 뜻 |
|---|---|
| 今(こん)シーズン | 이번 시즌 |
| 最(もっと)も | 가장 |
| 低(ひく)い | 낮다 |
"""
    path = markdown_to_pdf(sample_md, "output/test.pdf")
    print(f"PDF 생성 완료: {path}")

"""
Tool 2: Markdown → PDF 변환
- pandoc: markdown → HTML 변환
- weasyprint: HTML → PDF 변환 (일본어 폰트 지원)
"""

import base64
import io
import os
import re
import subprocess
import tempfile
import urllib.request
import urllib.error

import qrcode
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

.ruby-group {
    display: inline-block;
    text-align: center;
    vertical-align: baseline;
    margin: 0 1px;
}

.ruby-text {
    display: block;
    font-size: 0.5em;
    color: #555;
    line-height: 1;
    white-space: nowrap;
    min-height: 0.7em;
}

.ruby-base {
    display: block;
    line-height: 1;
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
    break-before: page;
    page-break-before: always;
}

h2:first-of-type {
    break-before: auto;
    page-break-before: auto;
}

tr {
    break-inside: avoid;
    page-break-inside: avoid;
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
    line-height: 2.2;
}

tr:nth-child(even) td {
    background-color: #f3f4fb;
}

tr:hover td {
    background-color: #e8eaf6;
}
"""


def _generate_qr_base64(url: str) -> str:
    """URL을 QR 코드로 변환하여 base64 PNG 문자열 반환"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _convert_furigana_to_ruby(html: str) -> str:
    """漢字(よみ) 패턴을 inline-block 기반 후리가나로 변환"""
    pattern = r'([一-龯々〆〇]+)\(([ぁ-んァ-ンー・]+)\)'
    replacement = (
        r'<span class="ruby-group">'
        r'<span class="ruby-text">\2</span>'
        r'<span class="ruby-base">\1</span>'
        r'</span>'
    )
    return re.sub(pattern, replacement, html)


def _fetch_thumbnail_base64(url: str) -> str | None:
    """YouTube URL에서 video_id를 추출해 썸네일을 base64로 반환"""
    m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
    if not m:
        return None
    video_id = m.group(1)
    for quality in ('maxresdefault', 'hqdefault', 'mqdefault'):
        thumb_url = f'https://img.youtube.com/vi/{video_id}/{quality}.jpg'
        try:
            with urllib.request.urlopen(thumb_url, timeout=5) as resp:
                data = resp.read()
            return base64.b64encode(data).decode('utf-8')
        except urllib.error.URLError:
            continue
    return None


def _inject_qr_into_html(html: str, url: str) -> str:
    """HTML의 h1 태그를 QR 코드와 나란히 배치하는 flex 컨테이너로 교체"""
    qr_b64 = _generate_qr_base64(url)
    qr_img_tag = (
        f'<img src="data:image/png;base64,{qr_b64}" '
        f'alt="QR Code" style="width:80px;height:80px;flex-shrink:0;" />'
    )

    thumb_b64 = _fetch_thumbnail_base64(url)
    if thumb_b64:
        thumb_block = (
            f'<a href="{url}" style="display:block;margin-top:10px;margin-bottom:4px;">'
            f'<img src="data:image/jpeg;base64,{thumb_b64}" '
            f'alt="YouTube thumbnail" '
            f'style="width:100%;max-height:200px;object-fit:cover;'
            f'border-radius:6px;border:1px solid #c5cae9;" />'
            f'</a>'
        )
    else:
        thumb_block = ''

    def replace_h1(m):
        inner = m.group(1)
        return (
            '<div style="border-bottom:3px solid #1a237e;padding-bottom:10px;margin-bottom:6px;">'
            '<div style="display:flex;align-items:center;gap:16px;">'
            f'<h1 style="border:none;padding:0;margin:0;flex:1;">{inner}</h1>'
            f'{qr_img_tag}'
            '</div>'
            f'{thumb_block}'
            '</div>'
        )

    return re.sub(r'<h1[^>]*>(.*?)</h1>', replace_h1, html, count=1, flags=re.DOTALL)


def markdown_to_pdf(markdown_text: str, output_path: str = "output/result.pdf", url: str = "") -> str:
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

    # 2단계: HTML 후처리 (QR 코드 삽입, 후리가나 변환)
    with open(html_path, encoding="utf-8") as f:
        html_content = f.read()
    if url:
        html_content = _inject_qr_into_html(html_content, url)
    html_content = _convert_furigana_to_ruby(html_content)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 3단계: weasyprint로 HTML → PDF 변환
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

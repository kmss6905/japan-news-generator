"""
Tool 0: YouTube 콘텐츠 가져오기
- youtube-transcript-api: 자막(transcript) 추출
- yt-dlp: 영상 설명(description) 및 메타데이터 추출
"""

import re
import subprocess
import json
from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(url: str) -> str:
    match = re.search(r"v=([^&]+)", url)
    return match.group(1) if match else url


def fetch_youtube_content(url: str) -> dict:
    video_id = extract_video_id(url)

    # yt-dlp로 메타데이터 + 설명글 가져오기
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", url],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    # youtube-transcript-api로 자막 가져오기 (인스턴스 방식)
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["ja", "ko", "en"])
        transcript_text = " ".join([item.text for item in fetched])
    except Exception as e:
        print(f"자막 가져오기 실패 (무시하고 계속): {e}")
        transcript_text = ""

    return {
        "title": data.get("title", ""),
        "channel": data.get("channel", ""),
        "upload_date": data.get("upload_date", ""),
        "description": data.get("description", ""),
        "transcript": transcript_text,
    }


if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=jOnVwFXTQG8"
    content = fetch_youtube_content(url)
    print(f"제목: {content['title']}")
    print(f"채널: {content['channel']}")
    print(f"설명 길이: {len(content['description'])} chars")
    print(f"자막 길이: {len(content['transcript'])} chars")

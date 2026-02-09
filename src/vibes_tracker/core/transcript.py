"""
Single-video transcript fetching and formatting.

Fetches YouTube transcripts and formats them with paragraph breaks
at natural pauses, with optional [MM:SS] timestamps.
"""

import json
import re
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen, Request
from urllib.error import URLError

from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(url_or_id):
    """Extract a YouTube video ID from a URL or pass through a bare ID.

    Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://youtube.com/shorts/VIDEO_ID
        - bare VIDEO_ID strings

    Args:
        url_or_id: A YouTube URL or video ID string.

    Returns:
        The 11-character video ID.

    Raises:
        ValueError: If the input can't be parsed as a YouTube URL or video ID.
    """
    # Try youtube.com/watch?v= format
    parsed = urlparse(url_or_id)
    if parsed.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
        if parsed.path == '/watch':
            qs = parse_qs(parsed.query)
            if 'v' in qs:
                return qs['v'][0]
        # /shorts/VIDEO_ID or /live/VIDEO_ID
        match = re.match(r'^/(shorts|live)/([a-zA-Z0-9_-]{11})', parsed.path)
        if match:
            return match.group(2)

    # Try youtu.be/VIDEO_ID format
    if parsed.hostname == 'youtu.be' and parsed.path:
        return parsed.path.lstrip('/')

    # Assume bare video ID (typically 11 chars, alphanumeric + _ and -)
    if re.match(r'^[a-zA-Z0-9_-]{10,12}$', url_or_id):
        return url_or_id

    raise ValueError(
        f"Could not extract video ID from: {url_or_id}\n"
        "Expected a YouTube URL or 11-character video ID."
    )


def fetch_video_title(video_id):
    """Fetch the video title from YouTube's oEmbed API (no API key needed).

    Args:
        video_id: YouTube video ID.

    Returns:
        The video title string, or None if it can't be fetched.
    """
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        req = Request(oembed_url, headers={"User-Agent": "vibes-tracker"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("title")
    except (URLError, json.JSONDecodeError, OSError):
        return None


def _sanitize_filename(title):
    """Turn a video title into a safe filename."""
    # Replace characters not allowed in filenames
    safe = re.sub(r'[<>:"/\\|?*]', '', title)
    # Collapse whitespace to single spaces
    safe = re.sub(r'\s+', ' ', safe).strip()
    # Truncate to reasonable length
    if len(safe) > 120:
        safe = safe[:120].rsplit(' ', 1)[0]
    return safe


def fetch_transcript_segments(video_id):
    """Fetch raw transcript segments with timing data.

    Args:
        video_id: YouTube video ID.

    Returns:
        List of snippet objects with .text, .start, and .duration attributes.

    Raises:
        Exception: If transcripts are disabled or unavailable for the video.
    """
    api = YouTubeTranscriptApi()
    return api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])


def _format_timestamp(seconds):
    """Format seconds into [H:MM:SS] or [MM:SS]."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"[{h}:{m:02d}:{s:02d}]"
    return f"[{m}:{s:02d}]"


def format_transcript(snippets, pause_threshold=1.5, timestamps=True):
    """Format transcript snippets into readable paragraphs.

    Groups consecutive snippets into paragraphs based on pause gaps.
    A new paragraph starts when the silence between segments exceeds
    pause_threshold seconds.

    Args:
        snippets: List of snippet objects from fetch_transcript_segments().
        pause_threshold: Seconds of gap to trigger a paragraph break.
        timestamps: Whether to prepend [MM:SS] markers to each paragraph.

    Returns:
        Formatted transcript string.
    """
    if not snippets:
        return ""

    def _clean(text):
        """Collapse embedded newlines and extra whitespace from captions."""
        return re.sub(r'\s+', ' ', text).strip()

    paragraphs = []
    current_texts = [_clean(snippets[0].text)]
    current_start = snippets[0].start

    for i in range(1, len(snippets)):
        prev = snippets[i - 1]
        curr = snippets[i]

        gap = curr.start - (prev.start + prev.duration)

        if gap >= pause_threshold:
            # Flush current paragraph
            paragraph_text = " ".join(current_texts)
            if timestamps:
                paragraph_text = f"{_format_timestamp(current_start)}\n{paragraph_text}"
            paragraphs.append(paragraph_text)

            current_texts = [_clean(curr.text)]
            current_start = curr.start
        else:
            current_texts.append(_clean(curr.text))

    # Flush final paragraph
    paragraph_text = " ".join(current_texts)
    if timestamps:
        paragraph_text = f"{_format_timestamp(current_start)}\n{paragraph_text}"
    paragraphs.append(paragraph_text)

    return "\n\n".join(paragraphs)

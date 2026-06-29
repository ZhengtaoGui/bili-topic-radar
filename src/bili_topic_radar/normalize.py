from __future__ import annotations

import html
import re
from typing import Any

from .models import Comment, VideoCard

_TAG_RE = re.compile(r"<[^>]+>")
_NUMBER_RE = re.compile(r"([-+]?\d+(?:\.\d+)?)")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = _TAG_RE.sub("", text)
    return " ".join(text.split())


def parse_count(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "--"}:
        return 0

    multiplier = 1
    if "亿" in text:
        multiplier = 100_000_000
    elif "万" in text:
        multiplier = 10_000
    elif "千" in text:
        multiplier = 1_000

    match = _NUMBER_RE.search(text)
    if not match:
        return 0
    return int(float(match.group(1)) * multiplier)


def parse_duration(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    if ":" not in text:
        return parse_count(text)

    parts = [parse_count(part) for part in text.split(":")]
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


def normalize_video_card(raw: dict[str, Any]) -> VideoCard:
    return VideoCard(
        bvid=str(raw.get("bvid") or raw.get("id") or ""),
        title=clean_text(raw.get("title")),
        desc=clean_text(raw.get("description") or raw.get("desc")),
        play=parse_count(raw.get("play") or raw.get("view")),
        danmaku=parse_count(raw.get("video_review") or raw.get("danmaku")),
        like=parse_count(raw["like"]) if "like" in raw and raw.get("like") is not None else None,
        duration=parse_duration(raw.get("duration")),
        pubdate=parse_count(raw.get("pubdate") or raw.get("senddate")),
        author=clean_text(raw.get("author") or raw.get("owner", {}).get("name")),
        mid=parse_count(raw.get("mid") or raw.get("owner", {}).get("mid")) or None,
    )


def normalize_comment(raw: dict[str, Any]) -> Comment:
    content = raw.get("content") if isinstance(raw.get("content"), dict) else {}
    member = raw.get("member") if isinstance(raw.get("member"), dict) else {}
    return Comment(
        message=clean_text(content.get("message") or raw.get("message")),
        like=parse_count(raw.get("like")),
        ctime=parse_count(raw.get("ctime")),
        uname=clean_text(member.get("uname") or raw.get("uname")),
    )

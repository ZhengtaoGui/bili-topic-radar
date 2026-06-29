from __future__ import annotations

from .client import BilibiliClient
from .formatting import comments_to_json, comments_to_markdown, videos_to_json, videos_to_markdown


_CLIENT = BilibiliClient()


async def tool_search_topic(keyword: str, limit: int = 30, output_format: str = "json") -> str:
    videos = await _CLIENT.search_topic(keyword=keyword, limit=limit)
    if output_format == "markdown":
        return videos_to_markdown(videos)
    if output_format != "json":
        raise ValueError("output_format must be 'json' or 'markdown'")
    return videos_to_json(videos)


async def tool_get_video_hot_comments(bvid: str, limit: int = 20, output_format: str = "json") -> str:
    comments = await _CLIENT.get_video_hot_comments(bvid=bvid, limit=limit)
    if output_format == "markdown":
        return comments_to_markdown(comments)
    if output_format != "json":
        raise ValueError("output_format must be 'json' or 'markdown'")
    return comments_to_json(comments)

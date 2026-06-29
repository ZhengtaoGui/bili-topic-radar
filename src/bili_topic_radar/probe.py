from __future__ import annotations

import asyncio
import json
import sys

from .tools import tool_get_video_hot_comments, tool_search_topic


async def _run(keyword: str) -> None:
    print(f"== search: {keyword} ==")
    search_json = await tool_search_topic(keyword, limit=5, output_format="json")
    print(search_json)

    videos = json.loads(search_json)
    if not videos:
        print("No videos found; skip comments probe.")
        return

    bvid = videos[0]["bvid"]
    print(f"\n== hot comments: {bvid} ==")
    comments_json = await tool_get_video_hot_comments(bvid, limit=10, output_format="json")
    print(comments_json)

    comments = json.loads(comments_json)
    likes = [item["like"] for item in comments]
    print(f"\ncomment_like_descending={likes == sorted(likes, reverse=True)}")


def main() -> None:
    keyword = sys.argv[1] if len(sys.argv) > 1 else "MCP"
    asyncio.run(_run(keyword))


if __name__ == "__main__":
    main()

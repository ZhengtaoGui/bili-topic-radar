from __future__ import annotations

from fastmcp import FastMCP

from .tools import tool_get_video_hot_comments, tool_search_topic

mcp = FastMCP("bili-topic-radar")

mcp.tool()(tool_search_topic)
mcp.tool()(tool_get_video_hot_comments)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

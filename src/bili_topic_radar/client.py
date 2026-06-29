from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

from .cache import FileTTLCache
from .models import Comment, VideoCard
from .normalize import normalize_comment, normalize_video_card
from .rate_limit import AsyncRateLimiter

_HTTP_CLIENT_READY = False


def _ensure_http_client() -> None:
    """Select an HTTP backend for bilibili-api (v17 requires an explicit pick).

    Done lazily on first network call so offline imports/tests don't need
    bilibili_api. Honors SOCKS/HTTP proxy via httpx (needs httpx[socks]).
    """
    global _HTTP_CLIENT_READY
    if _HTTP_CLIENT_READY:
        return
    from bilibili_api import request_settings, select_client

    select_client("httpx")
    # Reaching B站 from outside CN often goes through a slow local SOCKS
    # proxy; bump the per-request timeout so transient slowness doesn't abort.
    try:
        request_settings.set_timeout(20.0)
    except Exception:
        pass
    _HTTP_CLIENT_READY = True


class BilibiliClient:
    def __init__(
        self,
        cache: FileTTLCache | None = None,
        limiter: AsyncRateLimiter | None = None,
        max_retries: int = 3,
    ) -> None:
        self.cache = cache or FileTTLCache()
        self.limiter = limiter or AsyncRateLimiter()
        self.max_retries = max_retries

    async def search_topic(self, keyword: str, limit: int = 30) -> list[VideoCard]:
        safe_limit = max(1, min(limit, 50))
        key = json.dumps({"tool": "search_topic", "keyword": keyword, "limit": safe_limit}, ensure_ascii=False)
        raw = await self.cache.get_or_set(key, lambda: self._search_topic_uncached(keyword, safe_limit))
        return [normalize_video_card(item) for item in raw][:safe_limit]

    async def get_video_hot_comments(self, bvid: str, limit: int = 20) -> list[Comment]:
        safe_limit = max(1, min(limit, 50))
        key = json.dumps({"tool": "hot_comments", "bvid": bvid, "limit": safe_limit}, ensure_ascii=False)
        raw = await self.cache.get_or_set(key, lambda: self._hot_comments_uncached(bvid, safe_limit))
        comments = [normalize_comment(item) for item in raw]
        comments.sort(key=lambda item: item.like, reverse=True)
        return comments[:safe_limit]

    async def _search_topic_uncached(self, keyword: str, limit: int) -> list[dict[str, Any]]:
        _ensure_http_client()
        from bilibili_api import search

        SearchObjectType = getattr(search, "SearchObjectType")
        page_size = min(limit, 42)
        page = 1
        results: list[dict[str, Any]] = []

        while len(results) < limit:
            payload = await self._call_with_retry(
                search.search_by_type,
                keyword=keyword,
                search_type=SearchObjectType.VIDEO,
                page=page,
                page_size=page_size,
                order_type=getattr(search.OrderVideo, "TOTALRANK", None),
            )
            page_results = self._extract_search_results(payload)
            if not page_results:
                break
            results.extend(page_results)
            page += 1
        return results[:limit]

    async def _hot_comments_uncached(self, bvid: str, limit: int) -> list[dict[str, Any]]:
        _ensure_http_client()
        from bilibili_api import comment, video

        CommentResourceType = getattr(comment, "CommentResourceType")
        OrderType = getattr(comment, "OrderType")
        get_comments_lazy = getattr(comment, "get_comments_lazy", None)

        comments: list[dict[str, Any]] = []
        oid = await self._get_aid_from_bvid(video, bvid)
        if get_comments_lazy is not None:
            offset = ""
            while len(comments) < limit:
                page = await self._call_with_retry(
                    get_comments_lazy,
                    oid=oid,
                    type_=CommentResourceType.VIDEO,
                    offset=offset,
                    order=OrderType.LIKE,
                )
                replies = page.get("replies") or []
                comments.extend(replies)
                next_offset = (
                    page.get("cursor", {})
                    .get("pagination_reply", {})
                    .get("next_offset", "")
                )
                if not replies or not next_offset or next_offset == offset:
                    break
                offset = next_offset
            return comments[:limit]

        payload = await self._call_with_retry(
            comment.get_comments,
            oid=oid,
            type_=CommentResourceType.VIDEO,
            page_index=1,
            order=OrderType.LIKE,
        )
        comments.extend(payload.get("replies") or [])
        return comments[:limit]

    async def _get_aid_from_bvid(self, video_module: Any, bvid: str) -> int:
        video_obj = video_module.Video(bvid=bvid)
        getter = getattr(video_obj, "get_aid", None)
        if getter is not None:
            aid = getter()
            if inspect.isawaitable(aid):
                aid = await aid
            return int(aid)

        info = await self._call_with_retry(video_obj.get_info)
        return int(info["aid"])

    async def _call_with_retry(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        attempt = 0
        while True:
            await self.limiter.wait()
            try:
                return await func(*args, **{key: value for key, value in kwargs.items() if value is not None})
            except Exception as exc:
                if not self._is_retryable(exc) or attempt >= self.max_retries:
                    raise
                # risk control needs a longer cooldown; network blips recover fast
                delay = 2**attempt * 5 if self._is_risk_control(exc) else min(2**attempt * 2, 8)
                await asyncio.sleep(delay)
                attempt += 1

    @staticmethod
    def _extract_search_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        result = data.get("result") if isinstance(data, dict) else []
        return result if isinstance(result, list) else []

    @staticmethod
    def _is_risk_control(exc: Exception) -> bool:
        text = str(exc)
        return "-412" in text or "412" in text or "风控" in text

    @classmethod
    def _is_retryable(cls, exc: Exception) -> bool:
        """Retry on risk control (-412) AND transient network errors.

        The local SOCKS proxy occasionally drops/stalls a request; a single
        ReadTimeout shouldn't abort a whole collection run.
        """
        if cls._is_risk_control(exc):
            return True
        try:
            import httpx

            if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
                return True
        except Exception:
            pass
        return type(exc).__name__ in {
            "ReadTimeout", "ConnectTimeout", "ConnectError",
            "PoolTimeout", "ReadError", "RemoteProtocolError",
        }

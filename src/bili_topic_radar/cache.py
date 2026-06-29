from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable


class FileTTLCache:
    def __init__(self, root: Path | None = None, ttl_seconds: int = 6 * 60 * 60) -> None:
        cache_root = root or Path(os.environ.get("BILI_TOPIC_RADAR_CACHE", ".cache/bili-topic-radar"))
        self.root = cache_root
        self.ttl_seconds = ttl_seconds
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    async def get_or_set(self, key: str, factory: Callable[[], Awaitable[Any]]) -> Any:
        path = self._path_for(key)
        cached = await asyncio.to_thread(self._read_if_fresh, path)
        if cached is not None:
            return cached

        value = await factory()
        await asyncio.to_thread(self._write, path, value)
        return value

    def _read_if_fresh(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if time.time() - float(payload.get("created_at", 0)) > self.ttl_seconds:
            return None
        return payload.get("value")

    def _write(self, path: Path, value: Any) -> None:
        payload = {"created_at": time.time(), "value": value}
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)

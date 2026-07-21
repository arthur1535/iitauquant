from __future__ import annotations

import time
import requests

from .core import CACHE_ROOT, CacheResult, Manifest, atomic_write_bytes, ensure_directories, sha256_bytes


DEFAULT_HEADERS = {
    "User-Agent": "iitauquant-data/0.1 research contact-required@example.com",
    "Accept-Encoding": "gzip, deflate",
}


class CachedHttpClient:
    def __init__(self, user_agent: str | None = None, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if user_agent:
            self.session.headers["User-Agent"] = user_agent

    def get(
        self,
        url: str,
        cache_key: str,
        *,
        refresh: bool = False,
        retries: int = 3,
        pause_seconds: float = 1.0,
    ) -> CacheResult:
        ensure_directories()
        cache_path = CACHE_ROOT / cache_key
        if cache_path.exists() and not refresh:
            content = cache_path.read_bytes()
            Manifest().record(event="download", url=url, status="cache_hit", cache_key=cache_key, sha256=sha256_bytes(content))
            return CacheResult(content=content, cache_hit=True, path=cache_path)

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                content = response.content
                atomic_write_bytes(cache_path, content)
                Manifest().record(
                    event="download", url=url, status="ok", attempt=attempt,
                    cache_key=cache_key, bytes=len(content), sha256=sha256_bytes(content),
                )
                return CacheResult(content=content, cache_hit=False, path=cache_path)
            except (requests.RequestException, OSError) as exc:
                last_error = exc
                Manifest().record(event="download", url=url, status="failed", attempt=attempt, cache_key=cache_key, error=str(exc))
                if attempt < retries:
                    time.sleep(pause_seconds * (2 ** (attempt - 1)))
        raise RuntimeError(f"falha no download apos {retries} tentativas: {url}") from last_error

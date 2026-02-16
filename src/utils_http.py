import hashlib
import time
from pathlib import Path
from typing import Optional

import requests

from .config import Config


def _hash_key(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:24]


def _read_cache(path: Path) -> Optional[bytes]:
    if path.exists():
        return path.read_bytes()
    return None


def _write_cache(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def get_bytes_cached(url: str, cfg: Config, *, cache_key: Optional[str] = None, force_refresh: bool = False) -> bytes:
    """
    GET a URL and cache the raw bytes on disk.
    - Uses retries + simple exponential-ish backoff.
    """
    key = cache_key or _hash_key(url)
    cache_path = cfg.cache_dir / f"{key}.bin"

    if not force_refresh:
        cached = _read_cache(cache_path)
        if cached is not None:
            return cached

    headers = {"User-Agent": cfg.user_agent}

    last_err: Optional[Exception] = None
    for attempt in range(1, cfg.request_retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=cfg.request_timeout_s)
            r.raise_for_status()
            data = r.content
            _write_cache(cache_path, data)
            return data
        except Exception as e:
            last_err = e
            # backoff (1.25^attempt) * base
            sleep_s = (cfg.request_backoff_s ** attempt)
            time.sleep(sleep_s)

    # If all retries failed:
    assert last_err is not None
    raise last_err

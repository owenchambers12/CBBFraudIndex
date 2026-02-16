from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import pandas as pd

from .config import Config
from .utils_http import get_bytes_cached


@dataclass(frozen=True)
class CBBDataCredentials:
    api_key: str


def login_cbbdata(username: str, password: str, cfg: Config) -> CBBDataCredentials:
    """
    Logs in to CBBData and returns an API key.

    Endpoint behavior is based on the official cbbdata package source:
    POST https://www.cbbdata.com/api/auth/login  with JSON {username, password}
    and the response contains the API key. :contentReference[oaicite:2]{index=2}
    """
    import requests

    url = "https://www.cbbdata.com/api/auth/login"
    headers = {"User-Agent": cfg.user_agent}
    r = requests.post(url, json={"username": username, "password": password}, headers=headers, timeout=cfg.request_timeout_s)
    r.raise_for_status()

    data = r.json()
    # In the R package, they pluck(1); so response is likely a list like ["KEY"].
    if isinstance(data, list) and len(data) >= 1 and isinstance(data[0], str):
        return CBBDataCredentials(api_key=data[0])

    # Or it might be {"key": "..."} depending on server changes.
    if isinstance(data, dict):
        for k in ("key", "api_key", "token"):
            if k in data and isinstance(data[k], str):
                return CBBDataCredentials(api_key=data[k])

    raise RuntimeError(f"Unexpected login response shape: {type(data)} -> {data}")


def get_api_key_from_env() -> Optional[str]:
    """
    Prefer setting this once in your shell:
      export CBD_API_KEY="..."
    """
    return os.getenv("CBD_API_KEY") or None


def fetch_parquet_endpoint(
    base_url: str,
    params: Dict[str, Any],
    cfg: Config,
    *,
    cache_key: str,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    CBBData endpoints commonly serve Parquet bytes directly. :contentReference[oaicite:3]{index=3}
    """
    url = base_url + urlencode(params)
    raw = get_bytes_cached(url, cfg, cache_key=cache_key, force_refresh=force_refresh)
    # pandas can read parquet from bytes via BytesIO
    import io
    return pd.read_parquet(io.BytesIO(raw))

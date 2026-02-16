from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    cache_dir: Path = Path("data") / "raw" / "http_cache"
    outputs_dir: Path = Path("outputs")
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    request_timeout_s: int = 30
    request_retries: int = 3
    request_backoff_s: float = 1.25

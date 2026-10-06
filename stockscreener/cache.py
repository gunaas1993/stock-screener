"""Tiny pickle cache with TTL so reruns are fast and we stay polite to data sources."""
from __future__ import annotations

import pickle
import time
from typing import Callable, TypeVar

from .config import CACHE_DIR

T = TypeVar("T")


def cached(key: str, ttl_hours: float, fn: Callable[[], T], refresh: bool = False) -> T:
    path = CACHE_DIR / f"{key}.pkl"
    if not refresh and path.exists() and (time.time() - path.stat().st_mtime) < ttl_hours * 3600:
        try:
            with path.open("rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    value = fn()
    with path.open("wb") as f:
        pickle.dump(value, f)
    return value

"""Shared helpers for ToS;DR harvesting / dataset building (domain + stable split)."""
from __future__ import annotations

import hashlib

SEED = 42
TEST_PCT = 20  # percent of split keys assigned to test


def primary_domain(urls) -> str | None:
    for u in urls or []:
        u = (u or "").strip().lower()
        if u and not u.endswith(".onion"):
            return u.removeprefix("www.")
    return None


def split_key(service: dict) -> str:
    """Group key for train/test: services sharing a primary domain stay together."""
    return primary_domain(service.get("urls")) or f"tosdr:{service.get('slug') or service.get('id')}"


def is_test(service: dict, seed: int = SEED) -> bool:
    """Stable per-key assignment (adding new services never moves existing ones)."""
    h = hashlib.sha256(f"{seed}:{split_key(service)}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 100 < TEST_PCT


def is_rated(service: dict) -> bool:
    return service.get("rating") in ("A", "B", "C", "D", "E")

from __future__ import annotations

from enum import Enum
import re


class ITLiteracy(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_HIGH_MARKERS = (
    r"\bapi\b",
    r"\brest\b",
    r"\bgraphql\b",
    r"\bwebhook\b",
    r"\bjwt\b",
    r"\boauth\b",
    r"\bpostgres\b",
    r"\bpostgresql\b",
    r"\bkubernetes\b",
    r"\bk8s\b",
    r"\bdocker\b",
    r"\bmicroservice",
    r"\bci/?cd\b",
    r"\bopenapi\b",
    r"\bsql\b",
    r"\bllm\b",
    r"\brag\b",
    r"\bfastapi\b",
    r"\bredis\b",
    r"\bneo4j\b",
)

_MEDIUM_MARKERS = (
    r"\bdatabase\b",
    r"\bbackend\b",
    r"\bfrontend\b",
    r"\bintegrat",
    r"\bauth",
    r"\bdeploy",
    r"\bserver\b",
    r"\bcloud\b",
    r"\bbot\b",
    r"\btelegram\b",
    r"\badmin\b",
    r"\bdashboard\b",
    r"\bsaas\b",
)


def infer_literacy(text: str, previous: ITLiteracy | str | None = None) -> ITLiteracy:
    """Heuristic IT literacy from customer wording. Never downgrades without cause."""
    base = _parse_previous(previous)
    lowered = (text or "").lower()
    if not lowered.strip():
        return base

    high_hits = sum(1 for p in _HIGH_MARKERS if re.search(p, lowered))
    medium_hits = sum(1 for p in _MEDIUM_MARKERS if re.search(p, lowered))

    if high_hits >= 2 or (high_hits >= 1 and medium_hits >= 1):
        detected = ITLiteracy.HIGH
    elif high_hits >= 1 or medium_hits >= 2:
        detected = ITLiteracy.MEDIUM
    elif medium_hits >= 1:
        detected = ITLiteracy.MEDIUM
    else:
        detected = ITLiteracy.LOW

    return _max_literacy(base, detected)


def _parse_previous(previous: ITLiteracy | str | None) -> ITLiteracy:
    if previous is None:
        return ITLiteracy.LOW
    if isinstance(previous, ITLiteracy):
        return previous
    try:
        return ITLiteracy(previous)
    except ValueError:
        return ITLiteracy.LOW


def _max_literacy(a: ITLiteracy, b: ITLiteracy) -> ITLiteracy:
    order = {ITLiteracy.LOW: 0, ITLiteracy.MEDIUM: 1, ITLiteracy.HIGH: 2}
    return a if order[a] >= order[b] else b

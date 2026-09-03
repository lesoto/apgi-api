"""
Runtime access to identifiers.yaml — the single source of truth
(scripts/generate_identifiers.py generates the static copies: README.md,
CITATION.cff, .zenodo.json). GET /v1/meta and /v1/dataset-card read this
module directly rather than re-deriving any of this information, so there
is exactly one place any of it is ever typed.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

_IDENTIFIERS_PATH = Path(__file__).resolve().parent.parent.parent / "identifiers.yaml"


@functools.lru_cache(maxsize=1)
def load_identifiers() -> dict[str, Any]:
    """Load and cache identifiers.yaml. Call `load_identifiers.cache_clear()`
    in tests that need to observe a file change within the same process."""
    with open(_IDENTIFIERS_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return data


def current_release_state() -> str:
    """The current release_state.current label (pre-registered | pilot | calibrated)."""
    return str(load_identifiers()["release_state"]["current"])

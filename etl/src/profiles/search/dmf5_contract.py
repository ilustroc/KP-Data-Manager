from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def contract() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[4] / "resources" / "contracts" / "search-dm-f5-v1.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def conditions() -> frozenset[str]:
    return frozenset(contract()["sbs_conditions"])


def shifted_detail_fields() -> dict[str, str | bool]:
    return dict(contract()["sbs_detail_shift"])

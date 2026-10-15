from __future__ import annotations

import json
import re
from pathlib import Path


def _load_pattern() -> re.Pattern[str]:
    path = Path(__file__).resolve().parents[4] / "resources" / "contracts" / "search-telefonos-v1.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    operators = contract.get("operators")
    if not isinstance(operators, list) or not operators:
        raise RuntimeError("El contrato TELEFONOS v1 no contiene operadores.")
    ordered = sorted((str(operator) for operator in operators), key=len, reverse=True)
    alternatives = "|".join(re.escape(operator) for operator in ordered)
    return re.compile(
        rf"(?<![A-Z0-9])(?:{alternatives})(?![A-Z0-9])"
    )


OPERATOR_PATTERN = _load_pattern()


def match_operator(value: str) -> tuple[str | None, str | None]:
    selected = set(OPERATOR_PATTERN.findall(value))
    if not selected:
        return None, "OPERATOR_INVALID"
    if len(selected) > 1:
        return None, "OPERATOR_AMBIGUOUS"
    return next(iter(selected)), None

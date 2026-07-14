import json
from pathlib import Path

from .schema import ALLOWED_EXCLUDED_SYSTEMS, REQUIRED_CASE_FIELDS


def load_watch_case(path: str | Path) -> dict:
    case_path = Path(path)
    payload = json.loads(case_path.read_text(encoding="utf-8"))

    missing_fields = [
        field for field in REQUIRED_CASE_FIELDS if field not in payload
    ]
    if missing_fields:
        fields = ", ".join(missing_fields)
        raise ValueError(f"watch case missing required field(s): {fields}")

    excluded_systems = payload["excluded_systems"]
    unknown_exclusions = sorted(
        set(excluded_systems) - ALLOWED_EXCLUDED_SYSTEMS
    )
    if unknown_exclusions:
        systems = ", ".join(unknown_exclusions)
        raise ValueError(f"watch case has unknown excluded system(s): {systems}")

    if len(payload["output_axes"]) < 2:
        raise ValueError("watch case requires at least two output axes")

    return payload

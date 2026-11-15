"""Pages accepted from the AI discovery step.

Discovery results are runtime data, not repository config: a page the owner
accepted on the Live check screen is stored in ``data/discovered.json``
(gitignored), so the tracked ``live_sources.json`` and ``parsers/profiles.json``
stay reviewable and a clean checkout has no half-tested sites.

The same "a site is a profile, not code" rule applies: accepting a page writes a
profile and a watched source here; the collector and the parser merge them in.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATH = ROOT / "data" / "discovered.json"


def _path(path: Path | str | None = None) -> Path:
    return Path(path) if path is not None else PATH


def empty() -> dict:
    return {"profiles": {}, "sources": []}


def load(path: Path | str | None = None) -> dict:
    """Accepted pages; a missing or broken file means "none yet"."""
    file = _path(path)
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty()
    if not isinstance(payload, dict):
        return empty()
    profiles = payload.get("profiles")
    sources = payload.get("sources")
    return {
        "profiles": profiles if isinstance(profiles, dict) else {},
        "sources": sources if isinstance(sources, list) else [],
    }


def save(payload: dict, path: Path | str | None = None) -> None:
    """Write the accepted pages atomically (temp file then replace)."""
    file = _path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    temp = file.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, file)


def profiles(path: Path | str | None = None) -> dict:
    return load(path)["profiles"]


def sources(path: Path | str | None = None) -> list[dict]:
    return load(path)["sources"]


def accept(
    profile_id: str,
    profile: dict,
    source: dict,
    path: Path | str | None = None,
) -> dict:
    """Remember one accepted page; returns what was stored."""
    file = _path(path)
    payload = load(file)
    payload["profiles"][profile_id] = profile
    payload["sources"] = [item for item in payload["sources"] if item.get("id") != source["id"]]
    payload["sources"].append(source)
    save(payload, file)
    return {"profileId": profile_id, "source": source}


def clear(path: Path | str | None = None) -> int:
    """Forget accepted pages (used by the demo reset); returns how many went."""
    file = _path(path)
    payload = load(file)
    removed = len(payload["sources"])
    if file.exists():
        try:
            file.unlink()
        except OSError:
            return 0
    return removed

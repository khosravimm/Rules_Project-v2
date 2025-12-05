"""KB versioning helpers (semver-style bumping and history tracking)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Tuple


def parse_semver(version: str) -> Tuple[int, int, int]:
    """Parse a semantic-ish version string into (major, minor, patch)."""
    try:
        parts = [int(x) for x in str(version).strip().split(".")]
        while len(parts) < 3:
            parts.append(0)
        return parts[0], parts[1], parts[2]
    except Exception as exc:
        raise ValueError(f"Invalid version string: {version}") from exc


def _format_version(parts: Tuple[int, int, int]) -> str:
    return ".".join(str(p) for p in parts)


def bump_major(version: str) -> str:
    major, _, _ = parse_semver(version)
    return _format_version((major + 1, 0, 0))


def bump_minor(version: str) -> str:
    major, minor, _ = parse_semver(version)
    return _format_version((major, minor + 1, 0))


def bump_patch(version: str) -> str:
    major, minor, patch = parse_semver(version)
    return _format_version((major, minor, patch + 1))


def bump_kb_version(
    kb: dict[str, Any],
    *,
    reason: str,
    level: Literal["major", "minor", "patch"],
    now: datetime,
) -> dict[str, Any]:
    """Bump kb/meta versions and append to version_history."""

    meta = kb.setdefault("meta", {})
    kb_version = str(meta.get("kb_version") or meta.get("version") or "0.1.0")
    schema_version = str(meta.get("schema_version") or meta.get("version") or "0.1.0")
    current_version = str(meta.get("version") or kb_version)

    if level == "major":
        next_version = bump_major(current_version)
        next_kb = bump_major(kb_version)
    elif level == "minor":
        next_version = bump_minor(current_version)
        next_kb = bump_minor(kb_version)
    else:
        next_version = bump_patch(current_version)
        next_kb = bump_patch(kb_version)

    meta["version"] = next_version
    meta["kb_version"] = next_kb
    meta["updated_at"] = now.isoformat(timespec="seconds") + "Z"

    history = meta.setdefault("version_history", [])
    if not isinstance(history, list):
        history = []
        meta["version_history"] = history
    history.append(
        {
            "version": next_version,
            "kb_version": next_kb,
            "schema_version": schema_version,
            "changed_at": meta["updated_at"],
            "notes": [reason],
        }
    )
    return kb


__all__ = [
    "parse_semver",
    "bump_major",
    "bump_minor",
    "bump_patch",
    "bump_kb_version",
]

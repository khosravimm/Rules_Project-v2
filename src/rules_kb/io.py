"""Lightweight YAML IO utilities shared across CLI commands."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

import yaml


def load_yaml(path: Path) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"YAML not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at top-level for {path}")
    return data


def write_yaml_atomic(path: Path, data: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(path.parent)) as tmp:
        yaml.safe_dump(data, tmp, allow_unicode=True, sort_keys=False)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


__all__ = ["load_yaml", "write_yaml_atomic"]

"""YAML loading and validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import ValidationError

from .models import KnowledgeBase, KnowledgeValidationError, MasterKnowledge


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file using a safe loader."""

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:  # pragma: no cover - defensive guardrail
        raise KnowledgeValidationError(f"Failed to parse YAML: {path}") from exc

    if data is None:
        raise KnowledgeValidationError(f"YAML file is empty: {path}")

    if not isinstance(data, dict):
        raise KnowledgeValidationError(f"Top-level YAML content must be a mapping: {path}")

    return data


def load_knowledge(path: Path) -> KnowledgeBase:
    """Load and validate a kb/*_knowledge.yaml file."""

    raw = load_yaml(path)
    try:
        return KnowledgeBase.model_validate(raw)
    except ValidationError as exc:
        raise KnowledgeValidationError(f"Knowledge base validation failed for {path}") from exc


def load_master_knowledge(path: Path) -> MasterKnowledge:
    """Load and validate the project/MASTER_KNOWLEDGE.yaml file."""

    raw = load_yaml(path)
    try:
        return MasterKnowledge.model_validate(raw)
    except ValidationError as exc:
        raise KnowledgeValidationError(f"Master knowledge validation failed for {path}") from exc


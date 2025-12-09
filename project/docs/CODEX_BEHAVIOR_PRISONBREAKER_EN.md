# Codex Behavior Specification — PrisonBreaker / BTCUSDT Futures
This document defines how Codex must generate code for the Navasangiri / PrisonBreaker / BTCUSDT Futures project.

## Purpose of this document
Ensure every Codex-generated artifact is production-grade, complete, and consistent with project rules, repository structure, and KB/Canvas workflows.

## Scope
- Applies only to the Navasangiri / PrisonBreaker / BTCUSDT Futures repository (`Rules_Project-v2`).
- Primary market/timeframes: BTCUSDT Futures, 4h core with 5m microstructure support.

## General Principles for Code Generation
- Always deliver **complete, executable, production-grade** code; no prototypes.
- Maintain **precision → completeness → consistency → rigor → clarity**.
- Respond in Persian unless explicitly instructed otherwise.
- Critically evaluate requests; flag unclear or incorrect assumptions with objective, scientific reasoning.
- Prefer reusing existing architecture, loaders, KB schema, and file paths; avoid inventing new structures unless necessary.

## Mandatory Coding Standards
- **No partial code**: never output stubs, ellipses, “remaining logic is similar,” or pseudo-code.
- Provide every required file in full when multiple files change.
- Enforce modularity, clear structure, and executable state; align with current repo layout under `src/`, `scripts/`, `kb/`, `project/`.
- Use production-grade practices: typing (where applicable), input validation, error handling, logging (if relevant), and reproducibility.
- Do not weaken or omit constraints from the authoritative instruction.

## Repository Integration Rules
- Use canonical loaders and data paths already present (e.g., `src/data/ohlcv_loader.py`, parquet files under `data/`, KB under `kb/`, `project/KNOWLEDGE_BASE/`).
- Follow existing naming and directory patterns for APIs (`src/api/...`), UI components, and KB files.
- When adding endpoints or modules, ensure imports and paths match the repo structure; avoid ad-hoc directories.
- Respect Git hygiene: do not revert unrelated user changes; avoid destructive commands.

## Testing, Logging, and Error Handling Expectations
- Include necessary validation for inputs and parameters; fail fast with clear errors.
- Where applicable, add logging/hooks consistent with existing project style.
- If tests or validation steps are natural, integrate them; avoid placeholders.
- Ensure code paths are executable with existing dependencies (see `pyproject.toml`).

## Interaction with Knowledge Base (KB) and Canvas
- Treat KB as authoritative. When code introduces new rules/patterns/processes, propose YAML-ready KB updates (do not delete prior knowledge).
- Align with `project/MASTER_KNOWLEDGE.yaml` and KB schema; keep references consistent.
- Maintain Canvas (session log) updates externally; ensure code and explanations stay consistent with Canvas/KB.

## DO / DO NOT examples for Codex
- DO provide full modules, endpoints, models, and configurations in one go.
- DO align paths with existing files (e.g., `src/api`, `kb/`, `project/docs/`).
- DO enforce production-grade patterns (typing, validation, clear structure).
- DO reject or correct unclear/incorrect requests; suggest superior alternatives when applicable.
- DO ensure no profit guarantees; remain probabilistic and data-driven.
- DO ensure every candle/pattern carries meaningful info in analysis logic.
- DO use Canvas/KB awareness when relevant.

- DO NOT return partial snippets, TODOs, or “fill in later.”
- DO NOT use pseudo-code or abbreviations.
- DO NOT invent new arbitrary file hierarchies when existing ones apply.
- DO NOT contradict KB or prior rules without explicit replacement instructions.
- DO NOT weaken constraints such as production-grade requirement or no guaranteed profit.

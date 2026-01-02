# GitHub Copilot / AI Agent instructions for Aumiao-py

Quick, actionable context to get productive working on this repo.

Why this matters
- This project is a CLI + optional GUI automation tool for the 编程猫 community. The README explicitly warns about misuse; do not add or modify functionality that facilitates abuse or automated spamming. See `README.md` for the project's ethical position.

High-level architecture (what to read first)
- Entry points: `main.py` (CLI) and `mainWindows.py` (PyQt GUI). The `pyproject.toml` exposes a console script `aumiao = main:main`.
- Public libraries: `src/` contains most code:
  - `src/api/`: wrappers for remote endpoints (auth, community, work, etc.).
  - `src/core/`: application business logic, processors and services.
  - `src/utils/`: helper modules (notably `data.py` for persistent paths/configs and `plugin.py` for plugin system).
- Dynamic imports: `src/__init__.py` dynamically exposes modules via __getattr__ using a module map. When changing public module names or locations, update this module map to keep the public surface stable.

Project conventions & useful files
- Naming & design patterns: `document/Naming-Convention.md` — follow prefixes like `fetch_` (remote I/O) vs `grab_` (local), `is_`/`has_` for booleans, etc.
- Plugin system: `src/utils/plugin.py` and `document/Plugin-Development.md` — plugins live in `plugins/` and must implement a `Plugin` class following documented schema. Plugins can modify code at runtime (line/pattern injection or function rewrite); see docs for safe patterns and timing (must apply *before* target module is imported).
- Paths & data: `src/utils/data.py::PathConfig` centralizes paths (cache, data, download, plugins). Tests and local runs rely on these directories being present; `ensure_directories()` is called at import-time.
- Formatting & linting: `ruff.toml` (tabs, line-length 180, target py313). CI runs Ruff and typos checks (`.github/workflows/ci.yml`). Prefer `ruff check --fix --preview ./src` and `ruff format` locally.
- Spelling: repo uses `typos.toml` and crate-ci/typos in CI.
- Packaging: `pyproject.toml` (requires Python >= 3.13). Dev packaging mentions `nuitka` and there's an Inno Setup script `resource/aumiao.iss` for Windows installers.

What to check before writing code
- Security & ethics: The README warns about misuse; do not add features that enable automated abuse. If a change could be used offensively, add justification and opt-in safeguards (limits, confirmations, logging, and opt-outs).
- Public API stability: Because `src/__init__.py` exposes a module mapping, avoid renaming modules without updating the map and adding a small migration note in the PR.
- Plugins & modification timing: If your change is intended to be modified by a plugin, document how and ensure plugin docs show a safe method (prefer function rewrite over fragile line-number injection).

Tooling & common dev flows
- Run static checks locally: `ruff check --fix --preview ./src` and `ruff format ./src`.
- Run spell checks locally using `typos` (as configured in `typos.toml`).
- Running locally: `python main.py` (CLI) or `python mainWindows.py` (GUI). The console entrypoint `aumiao` is registered via `pyproject.toml` when installed.
- Build packaging (Windows): Nuitka for binary builds and `resource/aumiao.iss` for Inno Setup. Verify builds on Windows when touching packaging logic.

Testing & QA notes
- There are no conventional unit tests in CI. Use the lightweight `test.py` for integration/debug scenarios and add targeted unit tests when introducing logic changes.
- When changing data schema: `src/utils/data.py` contains dataclass schemas and default files (`data/`, `cache/`); add migration helpers and back-compat checks where necessary.

PR & review tips for AI agents
- Keep changes small and self-contained. Reference existing conventions (`document/*`) in PR descriptions.
- Add a short example or reproducible snippet when modifying public functions (inputs/outputs). Use `plugins/` examples if the change affects plugin behavior.
- Run Ruff and typos locally and attach a short checklist in the PR: lint ✅, spell ✅, smoke-run (CLI or GUI) ✅.

Files to read first when onboarding
1. `README.md` (ethics & overview) ✅
2. `document/Naming-Convention.md` (code style & naming) ✅
3. `document/Plugin-Development.md` (plugin rules & examples) ✅
4. `src/__init__.py` (module export & dynamic import behavior) ✅
5. `src/utils/data.py` (paths & dataclasses) ✅
6. `ruff.toml` and `.github/workflows/ci.yml` (lint + CI behavior) ✅

If something is unclear
- Ask for a small example or a short test case demonstrating desired behavior. Prefer PR feedback loops for ambiguous behavior.

Safety note
- If a requested change would materially make mass automation, abuse, or evasion easier, decline with a short explanation and propose safe alternatives (rate limits, confirmation flows, logging, opt-in flags).

---
If you'd like, I can open a draft PR with this file added, or iterate specific sections if you want more/less detail. Any preferences?
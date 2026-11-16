# Changelog

All notable changes to Mother AI OS are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0]

Mother became a genuinely standalone open-source project in this release. It
previously carried integrations with tooling that is not publicly installable,
which meant a clean checkout could not actually pass its own test suite.

### Removed

- **Eight integration plugins** that wrapped CLIs unavailable outside the
  author's machines. This is a **breaking change** for 0.3.0 users who relied
  on them. No core change is needed to restore that functionality: plugins now
  install as separate packages and register through the `mother.plugins` entry
  point group, which the loader already discovered.
- The marketing website, which moved to its own repository.

### Fixed

- **The `datacraft` built-in plugin no longer requires a private package.** Its
  parser had been rewritten as a thin adapter over an engine that is not on
  PyPI, so every one of its capabilities raised `ModuleNotFoundError` on a
  normal install. It is self-contained again, parsing PDF, DOCX and text through
  `pypdf` and `python-docx`, both already declared dependencies.
- **The test suite passes on a clean checkout.** It previously asserted that
  particular CLI binaries were present on `$PATH`, so it only passed on a
  machine that happened to have them installed. External-CLI checks are now
  opt-in via `MOTHER_TEST_EXTERNAL_CLIS`.
- **The dark web OSINT engine's dependencies are declared.** Its vendored
  LangChain stack was imported but never listed, so it failed to import on any
  install. It is now the optional `darkweb` extra, keeping it out of the base
  install since the plugin is high-risk and disabled by default; its tests skip
  cleanly when the extra is absent.
- **The tools catalog is packaged.** `DEFAULT_CATALOG_PATH` pointed outside the
  package, so `pip install mother-ai-os` shipped no catalog at all. It now lives
  at `mother/tools/tools-catalog.yaml`, is force-included in the wheel, and
  honours `MOTHER_CATALOG_PATH`.
- **Version drift.** `pyproject.toml`, `mother/__init__.py`, the PyPI release and
  the live `/health` endpoint reported four different versions.
  `mother/__init__.py` is now the single source via `[tool.hatch.version]`.
- **Missing licence notice for the vendored `robin_engine`.** Attribution was in
  the module docstring, but MIT requires shipping the copyright notice. Added
  `mother/plugins/builtin/robin_engine/LICENSE` (MIT, Copyright (c) 2025 Apurv
  Singh Gautam).

### Changed

- Tool-specific phrasing in the agent core moved behind
  `register_action_describer()`, so a plugin supplies its own wording instead of
  the core hard-coding a branch for it.
- A generic email-table parser was renamed to `parse_email_list`.

### Added

- `CONTRIBUTING.md`, `SECURITY.md` and this changelog.

### Security

- Releases 0.1.0, 0.2.0 and 0.3.0 were deleted from PyPI. Their source
  distributions contained files that were never intended to be published.
  Those version numbers will not be reused. **Upgrade to 0.4.0.**

## [0.3.0]

### Added

- **Multi-LLM provider support** — Anthropic Claude, OpenAI GPT, Zhipu GLM-4 and
  Google Gemini, selected with `AI_PROVIDER`.
- **`tor` and `tor-shell` plugins** for anonymous browsing and `.onion` access.
  Both are high-risk: disabled by default and blocked by `safe_mode`.
- **`darkweb-osint` plugin** over the vendored robin engine, under the same
  high-risk gating.

### Changed

- Migrated from the deprecated `google-generativeai` package to the unified
  `google-genai` SDK.

## [0.2.0]

### Added

- **Universal plugin system** — 12 built-in plugins, up from 4, exposing 98
  capabilities, up from 35.
- **Setup wizard** (`mother setup`) for first-time configuration.
- **Email management** with credential storage via the system keyring.

## [0.1.0]

Initial release: the agent core, the policy engine, the audit log, the FastAPI
server, and the first four plugins.

[Unreleased]: https://github.com/Mother-AI-OS/mother/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Mother-AI-OS/mother/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Mother-AI-OS/mother/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Mother-AI-OS/mother/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Mother-AI-OS/mother/releases/tag/v0.1.0

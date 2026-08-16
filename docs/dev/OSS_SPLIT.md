# OSS split — 2026-08-16

Record of what left this repository and why, so the boundary is not
re-crossed by accident.

## What changed

This repo was already public (GitHub `Mother-AI-OS/mother`, PyPI
`mother-ai-os` 0.1.0–0.3.0) but still carried three kinds of content that do
not belong in an MIT-licensed public project:

1. plugins wrapping CLIs nobody outside the author's machines can install,
2. private business documents, and
3. a marketing site with cross-references to unrelated private brands.

### 1. `*Craft` plugins → private package

Moved to `mother-craft-plugins` (private, never published):

`contentcraft`, `longcraft`, `mailcraft`, `taskcraft`, `mattercraft`,
`taxcraft`, `leads`, `transmit`.

They wrapped non-public CLIs, and their capability descriptions named private
business processes and brand rosters.

**No core changes were needed to support this.** Mother already discovered
plugins through the `mother.plugins` entry-point group
(`PluginLoader._discover_from_entry_points`); the built-ins were simply
hard-imported in `mother/plugins/builtin/__init__.py` instead of using it.
Installing the private package is now the entire integration.

Each extracted module gained a module-level `MANIFEST` (which the loader
reads) and had its manifest `module=` path rewritten to `mother_craft.*`.

### 2. Private documents → deleted and purged from history

- the business plan — pricing tiers, revenue split, launch plan
- `docs/ecosystem/OVERVIEW.md` — map of the author's private tool estate
- `docs/ecosystem/tools-catalog.yaml` — catalog of non-public tool repos
- `scripts/ecosystem_scan.py` — scanner for the same estate

`docs/ecosystem/INTEGRATION_CONTRACT.md` was **kept** — 634 lines of genuinely
public developer documentation with no private references — and moved to
`docs/dev/INTEGRATION_CONTRACT.md`.

History was rewritten with `git-filter-repo` and force-pushed. This was done
while the repo had 0 stars and 0 forks; it gets progressively more disruptive
after that.

### 3. Website → own repo

`website/` (Docusaurus) moved to a separate repo with its `website/` history
preserved. It mixed marketing with code and its blog posts cross-referenced
private brands.

## Incidental fixes made along the way

- **Version drift.** `pyproject.toml`, `mother/__init__.py`, the PyPI release
  and the live `/health` endpoint reported four different versions
  (0.3.1 / 0.3.0 / 0.3.0 / 0.2.0 stale install metadata). `mother/__init__.py`
  is now the single source via `[tool.hatch.version]`. Bumped to **0.4.0**
  because removing built-in plugins is a breaking change for 0.3.0 users.
- **Catalog was never packaged.** `DEFAULT_CATALOG_PATH` pointed at
  `docs/ecosystem/tools-catalog.yaml`, outside the package — so `pip install
  mother-ai-os` shipped no catalog at all. It now lives at
  `mother/tools/tools-catalog.yaml`, is force-included in the wheel, and
  honours `MOTHER_CATALOG_PATH`.
- **Vendored `robin_engine` had no upstream LICENSE file.** Attribution was
  present in the module docstring, but MIT requires shipping the copyright
  notice. Added `mother/plugins/builtin/robin_engine/LICENSE` (verified
  against upstream: MIT, Copyright (c) 2025 Apurv Singh Gautam).
- **Agent core named a private tool.** `_describe_action` hard-coded a
  `mailcraft` branch. Replaced with `register_action_describer()`, so
  tool-specific phrasing lives with the tool. The private package registers
  its own describer and behaviour is unchanged.
- **Private config removed from core settings**: `mailcraft_password`,
  `mailcraft_bin`, `leads_bin`, `taxlord_dir` (the last still referencing the
  pre-rename `taxlord` path). None had consumers.
- `parsers/output.py::parse_mailcraft_list` → `parse_email_list`; it is a
  generic email-table parser and kept its tests.

## The rule going forward

Anything that names a private tool, brand, client, process or host does not go
in this repo. Plugins for private tooling go in `mother-craft-plugins` and
register via entry points.

`MOTHER_OS_LINK.md` is `.gitignore`d — it references private infrastructure
addresses and must never be committed here.

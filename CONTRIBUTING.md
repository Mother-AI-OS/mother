# Contributing to Mother AI OS

Thanks for taking the time. This document covers what you need to get a change
merged.

## Getting set up

Mother targets **Python 3.11+** and is tested on 3.11 and 3.12.

```bash
git clone https://github.com/Mother-AI-OS/mother.git
cd mother
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

That is the whole setup. The test suite runs offline with no API keys and no
external services — if it needs a network call or a binary on your `$PATH`, that
is a bug, please report it.

```bash
pytest                  # full suite
ruff check .            # lint
ruff format --check .   # formatting
mypy mother             # types
```

CI runs exactly these four. Green locally means green in CI.

### Optional extras

The dark web OSINT plugin uses a vendored engine with a heavy LangChain stack,
so it is **not** part of the base install:

```bash
pip install -e ".[darkweb]"
```

`.[dev]` pulls this in already, so the suite exercises it. Without it those
tests skip rather than fail.

## Making a change

1. Open an issue first for anything larger than a bugfix, so you don't build
   something that gets rejected on design grounds.
2. Branch from `main`.
3. Write the test alongside the change. New capabilities need coverage; the
   project holds a coverage floor in CI.
4. Keep the commit message in the imperative mood and explain *why* in the
   body, not just what.
5. Open the PR against `main`.

## Writing a plugin

You very likely do **not** need to modify this repository. Mother discovers
plugins through the `mother.plugins` entry point group, so a plugin ships as
its own package:

```toml
[project.entry-points."mother.plugins"]
mytool = "mypackage.mytool:MyToolPlugin"
```

The target module exposes a module-level `MANIFEST` and the named `PluginBase`
subclass. See [docs/dev/INTEGRATION_CONTRACT.md](docs/dev/INTEGRATION_CONTRACT.md)
for the full contract.

Built-in plugins are reserved for capabilities with no third-party dependencies
that essentially every deployment wants. A plugin that wraps a specific vendor,
service, or CLI belongs in its own package.

## Things that will block a PR

Mother's entire value proposition is that an organization can hand it real
permissions and still sleep. Changes are held to that:

- **Never weaken a permission check to make something work.** If a capability
  needs a broader grant, declare it in the manifest and let the policy engine
  decide.
- **New capabilities declare an honest `risk_level`.** Anything that writes,
  deletes, spends money, sends a message, or reaches the network is not `LOW`.
- **High-risk capabilities stay disabled by default** and must be blocked by
  `safe_mode`.
- **Nothing bypasses the audit log.** If an action isn't logged, it didn't
  happen — and reviewers will treat that as a defect.
- **No secrets, tokens, private hostnames, or internal paths** in code, tests,
  fixtures, or documentation.

## Reporting bugs

Include the output of `mother doctor -v` (it redacts secrets), your Python
version, how you installed Mother, and the smallest reproduction you can
manage.

For anything security-related, do **not** open a public issue — see
[SECURITY.md](SECURITY.md).

## Licence

Contributions are accepted under the [MIT Licence](LICENSE), the licence this
project ships under.

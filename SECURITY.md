# Security Policy

## Supported versions

Mother is pre-1.0 and under active development. Security fixes land on the
latest minor release only.

| Version | Supported |
|---------|-----------|
| 0.4.x   | Yes       |
| < 0.4   | No        |

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Report it through
[GitHub's private vulnerability reporting](https://github.com/Mother-AI-OS/mother/security/advisories/new),
which keeps the report confidential until a fix ships.

Please include the affected version, what an attacker gains, a reproduction,
and any suggested fix. You will get an acknowledgement within 72 hours and an
assessment within 7 days. If a fix is warranted we will agree a disclosure date
with you, and you will be credited in the advisory unless you prefer otherwise.

## What counts as a vulnerability

Mother executes actions on a real system on behalf of an LLM. The security
boundary is the **policy engine**: an operator grants a set of capabilities, and
nothing outside that set should be reachable. Anything that crosses it matters:

- A capability executing without its policy check, or with the wrong one.
- Escaping a configured path restriction, allow-list, or `safe_mode`.
- A high-risk capability reachable while disabled or under `safe_mode`.
- An action that reaches the system without an audit record.
- Secrets, credentials, or API keys appearing in logs, audit records, error
  messages, or `mother doctor` output — the redaction layer failing.
- Authentication or API-key handling flaws, including privilege escalation
  between keys.
- **Prompt injection that causes a capability to execute outside the granted
  set.** Content Mother reads — a web page, an email, a document — is untrusted
  input. Injected text steering the *conversation* is expected and is not a
  vulnerability. Injected text defeating a *permission check* is.

## What does not

- An LLM producing a wrong, useless, or strange answer.
- An operator deliberately granting a dangerous capability, then it working as
  granted. `shell` and `filesystem` execute what they are permitted to; that is
  the product, not a bug.
- Anything requiring a pre-existing root or host compromise.
- Vulnerabilities in a third-party plugin — report those to its maintainer.

## Operator guidance

- Keep `safe_mode` on unless you have a specific reason not to.
- Grant the narrowest capability set that does the job, and treat `shell`,
  `ssh`, `tor`, `tor-shell` and `darkweb-osint` as privileged.
- Run with `MOTHER_REQUIRE_AUTH=true` for anything reachable off localhost.
- Rotate API keys with `mother keys rotate`; give each client its own key so
  one can be revoked alone.
- Ship the audit log somewhere Mother cannot write to.

# Lamia — Agent Guide

Lamia is an open-source autonomous AI pentesting tool. This file is for AI coding agents that want to **use** Lamia (run security scans) or **contribute** to it.

## Using Lamia from an agent

The workflows in `skills/` are the step-by-step guides:

- `penetration-testing-with-lamia` — run a headless pentest against code, URLs, domains, or IPs and read results
- `fix-security-vulnerabilities-with-lamia` — remediate findings and re-run Lamia to verify
- `ci-security-scanning-with-lamia` — add PR scanning to CI/CD

Target-specific workflows built on the same engine:

- `application-security-testing` — whole-product AppSec review: pick the right test per asset, then rank the results
- `web-app-penetration-testing` — black-box pentest of a live web app or staging site
- `api-security-testing` — REST/GraphQL APIs and the OWASP API Security Top 10 (BOLA/IDOR, authz)
- `owasp-top-10-testing` — systematic OWASP Top 10 assessment with honest per-category coverage
- `find-security-vulnerabilities-in-code` — white-box review of a repo or working tree

The CLI is local: Docker, your own LLM key, no hosted platform.

```bash
pipx install lamia-agent
export LAMIA_LLM="openrouter/z-ai/glm-5.3"        # any LiteLLM model id
export LLM_API_KEY="<key>"
lamia -n -t ./ --scan-mode quick --max-budget 10  # headless scan; always use -n
```

- Requires Docker running. Scans take minutes (`quick`) to hours (`deep`). Run them in the background.
- Exit codes (headless): `0` clean, `1` fatal error, `2` vulnerabilities found. A `0` only covers what was analyzed. Check `run.json` (`status`, `llm_usage.cost` vs the budget) before calling a run clean.
- New runs are written to `lamia_runs/<run-name>/`. Resume and `lamia view` also find runs left in `strix_runs/`. Artifacts: `penetration_test_report.md`, `vulnerabilities/*.md`, `vulnerabilities.json`, `findings.sarif` (SARIF 2.1.0), `run.json`.
- Only scan targets the user is authorized to test.

## Contributing to this repo

- Python 3.12+, managed with `uv`. Install dev deps: `make dev-install`.
- Lint/format/type-check/security, all in one: `make check-all` (ruff, mypy, bandit).
- Tests: `uv run pytest`.
- Run from source: `uv run lamia --target <target>`.
- Layout: `lamia/agents` (agent graph + prompts), `lamia/tools` (proxy, browser, terminal, scanners), `lamia/runtime` (Docker sandbox), `lamia/report` (findings, SARIF), `lamia/skills` (internal knowledge packs the pentest agents load — different from the consumer skills in `skills/`), `lamia/interface` (CLI/TUI), `containers/` (sandbox image).
- Pre-commit hooks: `make pre-commit` (or `uv run pre-commit install`).

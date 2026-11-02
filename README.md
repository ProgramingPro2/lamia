<div align="center">

# Lamia

### The open-source AI pentesting tool. Autonomous AI hackers that find and fix your app's vulnerabilities.

<br/>

<a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-3b82f6?style=flat-square" alt="License"></a>
<a href="https://pypi.org/project/lamia-agent/"><img src="https://img.shields.io/pypi/v/lamia-agent?style=flat-square" alt="PyPI"></a>

</div>

---


## Lamia Overview

Lamia are autonomous AI penetration testing agents that act just like real hackers - they run your code dynamically, find vulnerabilities, and validate them through actual proofs-of-concept. Built for developers and security teams who need fast, accurate security testing without the overhead of manual pentesting or the false positives of static analysis tools.

**Key Capabilities:**

- **Full pentesting toolkit** - reconnaissance, exploitation, and validation out of the box
- **Multi-agent orchestration** - teams of AI pentesters that collaborate and scale
- **Real exploit validation** - working PoCs, not false positives like legacy vulnerability scanners
- **Developer‑first CLI** - actionable findings with remediation guidance
- **Auto‑fix & reporting** - generate patches and compliance-ready pentest reports


## Use Cases

- **Application Security Testing** - Detect and validate critical vulnerabilities in your applications
- **Rapid Penetration Testing** - Get penetration tests done in hours, not weeks, with compliance reports
- **Bug Bounty Automation** - Automate bug bounty research and generate PoCs for faster reporting
- **CI/CD Integration** - Run tests in CI/CD to block vulnerabilities before reaching production

## Quick Start

**Prerequisites:**
- Docker (running)
- An LLM API key from a supported provider (OpenAI, Anthropic, Google, and others; see `docs/llm-providers/overview.mdx`)

### Installation & First Scan

```bash
# Install Lamia (pick one)
pipx install lamia-agent
# uv tool install lamia-agent
# curl -fsSL https://raw.githubusercontent.com/ProgramingPro2/lamia/lamia/scripts/install.sh | bash

# Configure your AI provider
export LAMIA_LLM="vercel_ai_gateway/zai/glm-5.3"   # Vercel AI Gateway
# export LAMIA_LLM="openrouter/z-ai/glm-5.3"       # OpenRouter
export LLM_API_KEY="your-api-key"

# Run your first security assessment
lamia --target ./app-directory
```

> [!NOTE]
> First run automatically pulls the sandbox Docker image. Results are saved to `lamia_runs/<run-name>`

### Updating

```bash
# Self-update the standalone binary to the latest release
lamia --update

# ...or upgrade the package you installed
pipx upgrade lamia-agent
# uv tool upgrade lamia-agent
```

Installed with pipx, uv, or pip? `lamia --update` prints the matching upgrade command instead (`pipx upgrade lamia-agent`, `uv tool upgrade lamia-agent`, `pip install --upgrade lamia-agent`). Lamia also shows a notice with the right command when a new version is available.

---

## Use Lamia from Your Coding Agent

Lamia is agent-ready. The workflows in `skills/` tell an agent how to run a local pentest, fix findings, and set up CI scanning against code, web apps, APIs, and the OWASP Top 10.

See [`AGENTS.md`](AGENTS.md) for the quick reference. The rest of the documentation is in `docs/`.

---

## ✨ Features

### Agentic Pentesting Tools

Lamia agents come equipped with a comprehensive offensive security toolkit - the same tools used by professional penetration testers and ethical hackers:

- **HTTP Interception Proxy** - Full request/response manipulation and analysis with Caido
- **Browser Exploitation** - Automated browser for testing XSS, CSRF, clickjacking, and auth bypass flows
- **Shell & Command Execution** - Interactive terminal for exploit development and post-exploitation
- **Custom Exploit Runtime** - Python sandbox for writing and validating proof-of-concept exploits
- **Reconnaissance & OSINT** - Automated attack surface mapping, subdomain enumeration, and fingerprinting
- **Static & Dynamic Code Analysis** - SAST + DAST capabilities for comprehensive application security testing
- **Vulnerability Knowledge Base** - Structured findings with CVSS scoring and OWASP classification

### Comprehensive Vulnerability Scanner

Lamia identifies, validates, and exploits a wide range of security vulnerabilities across the OWASP Top 10 and beyond:

- **Broken Access Control** - IDOR, privilege escalation, auth bypass
- **Injection Attacks** - SQL injection, NoSQL injection, OS command injection, SSTI
- **Server-Side Vulnerabilities** - SSRF, XXE, insecure deserialization, RCE
- **Client-Side Attacks** - XSS (stored/reflected/DOM), prototype pollution, CSRF
- **Business Logic Flaws** - Race conditions, payment manipulation, workflow bypass
- **Authentication & Session** - JWT attacks, session fixation, credential stuffing vectors
- **Infrastructure & Cloud** - Misconfigurations, exposed services, cloud security issues
- **API Security** - Broken authentication, mass assignment, rate limiting bypass

### Graph of Agents (Multi-Agent Pentesting)

Advanced multi-agent orchestration for comprehensive automated penetration testing:

- **Distributed Pentesting** - Specialized AI agents for recon, exploitation, and post-exploitation
- **Scalable Security Testing** - Parallel execution across multiple targets for fast, comprehensive coverage
- **Dynamic Coordination** - Agents share discoveries, chain vulnerabilities, and collaborate like a red team

---

## 🖥️ Local Web Viewer

Every scan writes its results to disk as it runs. Bring them up in a local dashboard with a single command:

```bash
# Open the most recent run
lamia view

# ...or open a specific run by name
lamia view my-run-name

# Expose the viewer on all IPv4 interfaces at a fixed port
lamia view --host 0.0.0.0 --port 8080 --no-open
```

The dashboard shows the findings, a live map of the agent team, and past runs. Nothing leaves your machine, and the UI ships prebuilt. `lamia view` binds to `127.0.0.1` and prints a tokened link that grants access to the run, so share it carefully.

See `docs/usage/viewer.mdx` for the options and for reaching the viewer from another machine.

---

## Usage Examples

### Basic Usage

```bash
# Scan a local codebase
lamia --target ./app-directory

# Security review of a GitHub repository
lamia --target https://github.com/org/repo

# Black-box web application assessment
lamia --target https://your-app.com
```

### API Testing (OpenAPI / Swagger / Postman)

Point Lamia at an API contract and it tests every declared endpoint instead of
having to discover them by crawling. Pair the spec with the live base URL so the
agent knows where to send traffic:

```bash
# OpenAPI / Swagger file, Postman export, or a live collection by id
lamia --target ./openapi.yaml --target https://api.your-app.com
lamia --target postman://<collection-uuid> --target https://api.your-app.com
```


### Advanced Testing Scenarios

```bash
# Grey-box authenticated testing
lamia --target https://your-app.com --instruction "Perform authenticated testing using credentials: user:pass"

# Multi-target testing (source code + deployed app)
lamia -t https://github.com/org/app -t https://your-app.com

# Targets from a file, one target per non-empty, non-comment line
lamia --target-list ./targets.txt
```

See `docs/usage/cli.mdx` for every option, including scan modes, diff scope, instruction files, and budgets.

### Headless Mode

Run Lamia programmatically without interactive UI using the `-n/--non-interactive` flag - perfect for servers and automated jobs. The CLI prints real-time vulnerability findings and the final report before exiting. Exits with non-zero code when vulnerabilities are found.

```bash
lamia -n --target https://your-app.com
```

### CI/CD (GitHub Actions)

Lamia can be added to your pipeline to run a security test on pull requests with a lightweight GitHub Actions workflow:

```yaml
name: lamia-penetration-test

on:
  pull_request:

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - name: Install Lamia
        run: pipx install lamia-agent

      - name: Run Lamia
        env:
          LAMIA_LLM: ${{ secrets.LAMIA_LLM }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}

        run: lamia -n -t ./ --scan-mode quick
```

> [!TIP]
> In CI pull request runs, Lamia automatically scopes quick reviews to changed files, which is why the
> checkout above fetches full history. See the
> `docs/integrations/github-actions.mdx` for the details.

### Configuration

```bash
export LAMIA_LLM="vercel_ai_gateway/zai/glm-5.3"   # Vercel AI Gateway
# export LAMIA_LLM="openrouter/z-ai/glm-5.3"       # OpenRouter
export LLM_API_KEY="your-api-key"

# Optional
export LLM_API_BASE="your-api-base-url"  # if using a local model, e.g. Ollama, LMStudio
```

> [!NOTE]
> Lamia automatically saves your configuration to `~/.lamia/cli-config.json`, so you don't have to re-enter it on every run.
> See `docs/advanced/configuration.mdx` for every environment variable.

#### Sign in with a ChatGPT subscription

Instead of a metered API key, you can run Lamia on your ChatGPT Plus/Pro subscription:

```bash
lamia auth login chatgpt             # sign in with your ChatGPT account
export LAMIA_LLM="chatgpt/gpt-5.4"   # chatgpt/<model> runs on the subscription
lamia auth status                    # show the active sign-in, or logout to forget it
```

#### Connect your own MCP servers

Lamia can connect to Model Context Protocol (MCP) servers you list and expose their tools to the agent during a run. Create `~/.lamia/mcp-servers.json` with a JSON list of local `stdio` servers or remote `http` servers:

```json
[
  {
    "name": "github",
    "transport": "http",
    "url": "https://api.githubcopilot.com/mcp/",
    "auth": { "kind": "bearer", "token": "your-token" },
    "allowed_tools": ["list_issues"]
  }
]
```

Each server's tools are namespaced by `name`, for example `github_list_issues`. See `docs/integrations/mcp.mdx` for the full schema, tool filtering, and `stdio` servers.

**Recommended models for best results:**

- [Z.ai GLM-5.3 on Vercel AI Gateway](https://vercel.com/ai-gateway/models/glm-5.3) - `vercel_ai_gateway/zai/glm-5.3` (recommended)
- [Z.ai GLM-5.3 on OpenRouter](https://openrouter.ai/z-ai/glm-5.3) - `openrouter/z-ai/glm-5.3` (recommended)
- [DeepSeek V4.1 Flash on OpenRouter](https://openrouter.ai/deepseek/deepseek-v4.1-flash-1017) - `openrouter/deepseek/deepseek-v4.1-flash-1017`
- [OpenAI GPT-6.1 Sol](https://openai.com/api/) - `openai/gpt-6.1-sol` (needs [Daybreak](https://openai.com/daybreak/) access)
- [Anthropic Claude Opus 5.5](https://claude.com/platform/api) - `anthropic/claude-opus-5-5` (needs [CVP](https://support.claude.com/en/articles/14604842-cyber-verification-program) access)
- [Google Gemini 4 Argon](https://cloud.google.com/vertex-ai) - `vertex_ai/gemini-4-argon` (needs [Fairwind](https://deepmind.google/fairwind-program/) access)
- [DeepSeek V4 Pro](https://platform.deepseek.com) - `deepseek/deepseek-v4-pro`
- [Moonshot Kimi K3.1 Pro](https://platform.kimi.ai) - `moonshot/kimi-k3.1-pro`

See `docs/llm-providers/overview.mdx` for supported providers including Vertex AI, Bedrock, Azure, and local models.

## Documentation

Guides for usage, CI, skills, and configuration live in `docs/`.

## Contributing

Contributions of code, docs, and skills are welcome. Start with `docs/contributing.mdx` and `CONTRIBUTING.md`.

## Acknowledgements

Lamia builds on the incredible work of open-source projects like [LiteLLM](https://github.com/BerriAI/litellm), [Caido](https://github.com/caido/caido), [Nuclei](https://github.com/projectdiscovery/nuclei), [Playwright](https://github.com/microsoft/playwright), and [Bubble Tea](https://github.com/charmbracelet/bubbletea). Huge thanks to their maintainers!


> [!WARNING]
> **Authorized use only.** Lamia actively tests the targets you point it at, so only run it against systems you own or have **explicit, written permission** to test, and stay within the agreed scope. Unauthorized testing is illegal in most jurisdictions.
> You alone are responsible for obtaining authorization and complying with the law. Lamia is provided "as is" with no warranty or liability for misuse.

</div>

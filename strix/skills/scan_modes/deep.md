---
name: deep
description: Full-penetration assessment that closes each reachable in-scope attack path from entry to demonstrated impact
---

# Deep Testing Mode

Full-penetration assessment. Depth is spending your budget on paths that reach real impact, not on visiting every surface once. The deliverable is a demonstrated attack path: entry, foothold, privilege boundary crossed, data or action reached, evidence captured.

## Approach

Map the target first, then follow the paths that reach high-value data or actions to the end. One closed path outranks a dozen opened ones.

A path is closed when it ends in exactly one state: confirmed with evidence, ruled out with the specific control named, or recorded as a proof gap with the evidence that would settle it. A path you stopped testing is still open.

## Phase 1: Reconnaissance and Mapping

Map enough to choose paths. Depth here means knowing where the trust boundaries and sinks are, not enumerating every asset the target owns.

**Whitebox (source available)**
- Map modules, entry points, routing, and the data model
- Start with source-aware triage (`semgrep`, `ast-grep`, `gitleaks`, `trufflehog`, `trivy fs`) and use the output to rank candidate paths
- Run at least one structural AST pass (`sg` and/or Tree-sitter) per repository and keep artifacts reusable
- Keep AST artifacts bounded and query-driven: target relevant paths and sinks, not whole-repo function dumps
- Trace entry points to sinks through the controls between them: validation, authentication, authorization, encoding
- Map authorization checks and the access control model, including where it is enforced and where it is assumed
- Map background jobs, cron tasks, async processing, and any internal caller that reaches the same sink as an HTTP route
- Identify serialization, deserialization, file handling, and external integration points
- Check dependency versions and repository risks with `trivy fs`, `gitleaks`, and `trufflehog`
- For quick CVE lookups on a named product/version, use `vulnx search <query>` before falling back to web_search

**Blackbox (no source)**
- Subdomain and host enumeration across multiple sources, scoped to the in-scope root domains
- Port and service discovery on in-scope hosts and ranges only
- Bounded content discovery: enough breadth to find the routes that matter, then stop
- Technology fingerprinting and version identification on everything that answered
- API discovery through docs, JavaScript analysis, and observed traffic
- Map user roles and account types the target exposes
- Document the controls you can observe: rate limiting, WAF behavior, session handling
- Write down the application architecture as far as the outside can confirm it

## Phase 2: Path Selection

Rank candidate paths before you test any of them. Pick by reach, not by novelty.

- **Entry** - what an attacker can touch without already holding access
- **Boundary** - which privilege or tenant boundary the path could cross
- **Reach** - what data or action sits at the end, and how much of it
- **Blast radius** - how many users or tenants the end impact covers
- **Cost** - what it takes to prove, and whether that proof is reproducible

Work the highest-ranked path to closure before opening the next. Open a second path in parallel only when the two share no evidence and no state.

## Phase 3: Follow Each Path to Impact

For the path you selected, drive it as far as it goes.

**Entry and foothold**
- Injection across every parser the entry reaches: SQL, NoSQL, LDAP, XPath, command, template
- Encoding and normalization bypasses: double encoding, unicode, null bytes, case and path variants
- Boundary conditions, type confusion, oversized input, and truncation
- File handling: upload bypass by extension, content type, and magic bytes; traversal on every path parameter; SSRF and XXE where the parser is reached
- Authentication and session: token handling, JWT manipulation, OAuth flows, reset token leakage or reuse, MFA bypass, account enumeration
- When SSRF, XXE, or a blind injection is in play, use interactsh to confirm the out-of-band channel rather than assuming it

**Boundary crossing**
- Horizontal and vertical access control on every object reference the path touches
- Session state changes: logout, role change, impersonation, re-authentication
- Forced browsing, method tampering, and parameter pollution against the same handler
- Mass assignment and hidden field acceptance on the objects you can write

**Reach**
- Read, then write, then act: escalate one step at a time and record which step crossed the boundary
- Race conditions and TOCTOU on any state-changing step the path crosses
- Business logic: workflow bypass, price and quantity manipulation, replay
- Confirm the end impact on data or an action that matters, not on a canary you planted

**When a control fires**
- The first blocked payload is not the end of the path. Vary the technique on the same sink
- Change the surface: a sibling route, an older API version, a different role, an admin alias, a GraphQL resolver, a background job, or a mobile endpoint
- Read the control and test what it does not cover: encoding it misses, paths it skips, roles it trusts
- Record the control by name and location whether it holds or not; a bypass and a ruled-out path both need the same specificity

## Phase 4: Chaining

Low impact alone is not a reason to file or to drop. Follow the chain first.

- Treat every confirmed weakness as a pivot: what does it unlock next
- Prefer end-to-end paths over isolated bugs: entry, foothold, privilege gain, sensitive action or data
- Cross boundaries deliberately: user to admin, external to internal, read to write, one tenant to another
- Execute the full sequence, not just the first hop; a chain you did not run is a hypothesis
- Score the chain by its end impact, not by its weakest link
- When a pivot lands in a different component, spawn a specialist for that segment and hand it the state you reached

## Phase 5: Persistence Within the Path

Depth means exhausting the path, not the target.

- Research the technology-specific bypasses for the control that stopped you before trying random variants
- Try the same weakness with a different client context, role, or protocol version
- Use timing and blind techniques where the response gives you nothing
- Revisit a path when another finding changes what you know about it
- Stop when the path is closed, not when the first attempt failed; stop the target when its paths are closed

## Phase 6: Reporting

- File every confirmed path with its full sequence and the evidence for each step
- Report the intermediate weaknesses that make the chain work, and name the chain in the end finding
- Score severity at the end impact of the chain
- Record what you ruled out and with which control; record proof gaps with what would settle them
- Note the paths you did not reach and why, so the next run starts where this one stopped

## Agent Strategy

Decompose by attack path, not by vulnerability type:

1. **Path level** - one specialist per entry-to-impact path, owning it end to end
2. **Segment level** - a follow-on specialist when the path crosses into a component the first specialist cannot reach, carrying the state forward
3. **Validation level** - an independent check when the path's central claim is the whole finding

- Give each specialist the path, its entry point, and the state already reached, so it continues rather than restarts
- Keep 1-3 related skills per specialist; a path rarely needs a generalist
- Do not split one path across agents that cannot see each other's progress
- Spawn reactively, as the path opens up, not as a broad swarm at the start
- Stop agents whose path is closed, ruled out, or superseded by another path

## Mindset

Relentless on the path you chose, indifferent to the ones you did not. Vary the technique before you vary the target. Treat every control that fires as a question about what it fails to cover. A path is only finished when it is closed.

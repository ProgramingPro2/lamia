---
name: deep
description: Full-penetration assessment that closes every applicable class on every mapped in-scope surface
---

# Deep Testing Mode

Full-penetration assessment. Depth is closing every applicable class on every mapped in-scope surface, starting with the paths that reach real impact. The deliverable is still a demonstrated attack path: entry, foothold, privilege boundary crossed, data or action reached, evidence captured. Closing the highest-value paths does not end the target.

## Approach

Map the target first. Then build an applicable-class checklist for each in-scope surface and work it until every class is closed or the budget wind-down fires.

A class applies when that surface can reach the parser or control: SQL, NoSQL, LDAP, XPath, command, template, XML, XSS, SSRF, traversal, upload, IDOR, BFLA, mass assignment, authentication (JWT, OAuth, SAML), CSRF, race, business logic, deserialization, WebSocket. A class that cannot apply is a one-line ruled-out row that names why, not a skipped row.

A class is closed when it ends in exactly one state: confirmed with evidence, ruled out with the specific control named, or recorded as a proof gap with the evidence that would settle it. A class you stopped testing is still open.

## Phase 1: Reconnaissance and Mapping

Map enough to know which classes apply. An unmapped route is not a tested route. Record routes you could not reach as proof gaps.

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
- Content discovery wide enough to list the routes that answer, then test those routes
- Technology fingerprinting and version identification on everything that answered
- API discovery through docs, JavaScript analysis, and observed traffic
- Map user roles and account types the target exposes
- Document the controls you can observe: rate limiting, WAF behavior, session handling
- Write down the application architecture as far as the outside can confirm it

## Phase 2: Class Checklist

Rank candidate classes by reach before you test them, then keep going after the first ones close.

- **Entry** - what an attacker can touch without already holding access
- **Boundary** - which privilege or tenant boundary the class could cross
- **Reach** - what data or action sits at the end, and how much of it
- **Blast radius** - how many users or tenants the end impact covers
- **Cost** - what it takes to prove, and whether that proof is reproducible

Work the highest-ranked classes first. Open a second class in parallel when the two share no evidence and no state. When those classes close, continue with the remaining applicable classes on the same surfaces.

## Phase 3: Follow Each Class to Impact

For the class you selected, drive it as far as it goes.

**Entry and foothold**
- Injection across every parser the entry reaches: SQL, NoSQL, LDAP, XPath, command, template
- Encoding and normalization bypasses: double encoding, unicode, null bytes, case and path variants
- Boundary conditions, type confusion, oversized input, and truncation
- File handling: upload bypass by extension, content type, and magic bytes; traversal on every path parameter; SSRF and XXE where the parser is reached
- Authentication and session: token handling, JWT manipulation, OAuth flows, SAML assertions, reset token leakage or reuse, MFA bypass, account enumeration
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
- The first blocked payload is not the end of the class. Vary the technique on the same sink
- Change the surface: a sibling route, an older API version, a different role, an admin alias, a GraphQL resolver, a WebSocket message, a background job, or a mobile endpoint
- Read the control and test what it does not cover: encoding it misses, paths it skips, roles it trusts
- Record the control by name and location whether it holds or not; a bypass and a ruled-out class both need the same specificity

## Phase 4: Chaining

Low impact alone is not a reason to file or to drop. Follow the chain first.

- Treat every confirmed weakness as a pivot: what does it unlock next
- Prefer end-to-end paths over isolated bugs: entry, foothold, privilege gain, sensitive action or data
- Cross boundaries deliberately: user to admin, external to internal, read to write, one tenant to another
- Execute the full sequence, not just the first hop; a chain you did not run is a hypothesis
- Score the chain by its end impact, not by its weakest link
- When a pivot lands in a different component, spawn a specialist for that segment and hand it the state you reached
- A finished chain does not close the other applicable classes on that surface

## Phase 5: Do Not Leave a Class on the First Failure

- Research the technology-specific bypasses for the control that stopped you before trying random variants
- Try the same weakness with a different client context, role, or protocol version
- Use timing and blind techniques where the response gives you nothing
- Revisit a class when another finding changes what you know about it
- Before ruling an injection or authentication class out, escalate one step past the tooling skill's conservative baseline:
  - sqlmap `--level 3 --risk 2` with `--batch`, aimed at the specific parameter, and a bounded proof read rather than a database dump
  - Nuclei through medium: `-s critical,high,medium`
  - nmap `--top-ports 1000` on in-scope hosts
- The shared sqlmap and nuclei playbooks stay at their conservative baseline for other modes. This mode overrides that baseline before a class is ruled out
- Stop when the class is closed, not when the first attempt failed. Stop the target only when its applicable classes are closed or the budget wind-down fires

## Phase 6: Reporting

- File every confirmed path with its full sequence and the evidence for each step
- Report the intermediate weaknesses that make the chain work, and name the chain in the end finding
- Score severity at the end impact of the chain
- Record what you ruled out and with which control; record proof gaps with what would settle them
- Note the classes and surfaces you did not reach and why, so the next run starts where this one stopped

## Agent Strategy

Decompose by attack path first, then by every applicable class that path owner did not close:

1. **Path level** - one specialist per entry-to-impact path, owning it end to end
2. **Remaining classes** - when that owner reports, spawn a specialist for each applicable class it did not close
3. **Segment level** - a follow-on specialist when the path crosses into a component the first specialist cannot reach, carrying the state forward
4. **Validation level** - an independent check when the path's central claim is the whole finding

- Give each specialist the surface, the class, and the state already reached, so it continues rather than restarts
- Keep at most 5 related skills per specialist. Breadth comes from more specialists, not from one generalist
- Do not split one path across agents that cannot see each other's progress
- Spawn the follow-up class specialists as soon as the path owner closes or stalls
- Stop agents whose assigned classes are closed

## Mindset

Relentless on every applicable class of every mapped in-scope surface. Vary the technique before you leave a class. A class is only finished when it is closed. The target is finished when those classes are closed or the budget wind-down fires.

---
name: exhaustive
description: Maximum-coverage assessment that swarms every applicable class and escalates scanners, exploit checks, and post-exploitation inside scope
---

# Exhaustive Testing Mode

Maximum-coverage assessment. Everything deep mode requires applies here, and then you go further: class-cluster specialists, advanced variants before any ruled-out row, scanner escalation, and exploit validation against fingerprinted in-scope services. The destructive-action limits still apply. No denial of service, no data destruction, no persistence, no mass dump, and no target outside the operator's scope.

## Approach

Map the target, write the threat model, then spawn class-cluster specialists per major surface. Do not wait for one path owner to get around to a class.

A class applies when that surface can reach the parser or control: SQL, NoSQL, LDAP, XPath, command, template, XML, XSS, SSRF, traversal, upload, IDOR, BFLA, mass assignment, authentication (JWT, OAuth, SAML), CSRF, race, business logic, deserialization, WebSocket, and backend services once a version, foothold, or SSRF sink is confirmed. A class that cannot apply is a one-line ruled-out row that names why, not a skipped row.

A class is closed only after its advanced variants have been tried: confirmed with evidence, ruled out with the specific control named, or recorded as a proof gap with the evidence that would settle it. The first basic failure is not a ruled-out row.

## Phase 1: Reconnaissance

Map every in-scope surface you can reach without degrading the target.

**Whitebox**
- Map modules, routes, jobs, and sinks, then trace each entry through its controls
- Run source-aware triage (`semgrep`, `ast-grep`, `gitleaks`, `trufflehog`, `trivy fs`) and at least one structural AST pass
- Rank by reach, then schedule a class cluster for every sink you traced, including the ones that are not the highest impact

**Blackbox**
- Subdomain and host enumeration scoped to in-scope roots
- `nmap -p- -sV` on in-scope hosts. Record the service and version; that version is the input to `searchsploit` and Metasploit
- Content discovery with ffuf or dirsearch against SecLists (`/usr/share/seclists/Discovery/Web-Content/`), scoped to the host you are testing. Capture the route list and delete the raw output
- Technology fingerprinting, API docs, JavaScript routes, and observed proxy traffic
- Roles, tenants, session model, WAF, and rate limits

## Phase 2: Class Swarm

After the threat model exists, spawn these clusters per major surface. Clusters that share no state run side by side.

1. **Injection** - SQL, NoSQL, LDAP, XPath, command, template, XML
2. **Access control** - IDOR, BFLA, mass assignment
3. **Authentication** - JWT, OAuth, SAML, session, reset, MFA
4. **Client-side** - XSS, CSRF, open redirect, browser-context issues
5. **Backend services** - exposed service versions, SSRF to internal listeners, and any foothold

Give each specialist the surface, the cluster, and the state already known. Cap each specialist at 5 related skills. A path that produces a finding stays with one owner through impact and chaining. When a cluster reports, spawn a specialist for any applicable class inside it that is still open.

## Phase 3: Advanced Variants Before Ruled Out

Do not rule a class out on the first basic failure. Load the class skill and run its advanced variants first: encoding and parser differentials, a second role, a sibling route, an older API version, a WebSocket or background-job entry to the same sink.

Scanner ceiling for this mode, still inside the no-DoS and no-mass-dump rules:

- sqlmap `--level 5 --risk 3 --batch` on the specific parameter. Prove with a bounded read (`--current-user`, a single cell, or `--banner`). Do not `--dump` a table to prove the bug
- Nuclei with no severity filter, rate-limited (`-rl 50`), tech-mapped with `-as` once versions are known
- `nmap -p- -sV` as above. Add default scripts only on the ports that answered
- ffuf and dirsearch use SecLists wordlists for the surface under test, not a short hand-written list
- On a confirmed service version, `searchsploit` that product and version, then Metasploit `check` before `exploit`, and only against that in-scope host
- On a foothold, hand the session to a specialist carrying the post-exploitation skill. Prove one privilege boundary, collect the evidence, and remove artifacts created for the proof

The shared sqlmap, nuclei, and nmap playbooks stay conservative for other modes. This mode overrides them.

## Phase 4: Chaining and Reporting

- Treat every confirmed weakness as a pivot and execute the chain before you file it
- A finished chain does not close the other clusters on that surface
- File confirmed paths with the full sequence. Record ruled-out classes with the control named. Record proof gaps with what would settle them
- The finish summary names every cluster that was not closed and why

## Mindset

Try the applicable possibility, then the next one. A class is finished when it is closed after its advanced variants, not when the first payload failed. The target is finished when those classes are closed or the budget wind-down fires.

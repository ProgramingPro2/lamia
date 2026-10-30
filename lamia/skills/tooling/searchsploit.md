---
name: searchsploit
description: Map a confirmed product version to Exploit-DB entries, then hand a match to Metasploit or a manual proof
---

# searchsploit

`searchsploit` ships with Exploit-DB and is the index between a confirmed version and a module worth trying. An Exploit-DB hit is not a finding.

## When to run it

Run it after nmap, a banner, or a dependency manifest gives you a product and a version on an in-scope host. Do not search a vendor name alone and then try every result.

## Commands

- Exact version: `searchsploit <product> <version>`
- Title filter: `searchsploit <product> --exclude="dos"`
- Read the entry path, do not execute it yet: `searchsploit -p <EDB-ID>`
- Update the index only when a search returns nothing for a version you are sure is current: `searchsploit -u`

Ignore denial-of-service titles. They are out of scope for this engagement.

## What to do with a hit

1. Confirm the installed version still matches the entry. A banner from a different vhost does not count.
2. If Metasploit has the same module, hand it to the metasploit skill: `check` first, one in-scope host, session closed after the proof.
3. If the entry is a manual proof, reproduce the smallest observation that shows impact (one unauthorized read, one command that returns the user id). Stay inside the destructive-action limits: no data destruction, no persistence, no crash.
4. If the version does not match, or the proof fails because a control blocks it, record the control. Do not file the Exploit-DB title.

## Copy

Copy an entry into `/tmp` only when you are about to run that proof, and delete it afterwards:

`searchsploit -m <EDB-ID>`

Do not leave exploit files in `/workspace`.

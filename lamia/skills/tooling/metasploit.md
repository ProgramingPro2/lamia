---
name: metasploit
description: Non-interactive Metasploit module search, check, and in-scope exploit validation with session cleanup
---

# Metasploit

Use Metasploit when a fingerprinted in-scope service has a matching module. `msfconsole` is installed in the sandbox. Run it non-interactively. A module match is a lead until `check` or a bounded proof says otherwise.

## Scope

- `RHOSTS` and `RPORT` come from the operator's scope and from the port that answered. Never add a host you discovered yourself.
- Search by the product and version nmap or the banner actually returned.
- `check` before `exploit`. If the module has no check, confirm the version match another way before running it, and prefer a proof that reads one fact (user id, banner, a single file the service should not expose) over a shell you do not need.
- One in-scope host at a time. No sweeps.

## Commands

Search, then exit:

`msfconsole -q -x 'search type:exploit name:<product>; exit'`

Check a named module:

`msfconsole -q -x 'use <module>; set RHOSTS <in-scope-host>; set RPORT <port>; check; exit'`

A resource file is easier to re-run. Save this as `/workspace/check.rc`, point it at one host, and delete it when the proof is captured:

```
use <module>
set RHOSTS <in-scope-host>
set RPORT <port>
check
exploit -z
sessions -K
exit
```

`msfconsole -q -r /workspace/check.rc`

`-z` backgrounds a session so the resource script can reach `sessions -K`. Do not leave a handler listening.

## After a session opens

- Record the module, the options, and the observation that proves impact (`sysinfo`, `getuid`, or a single file read).
- Hand a real foothold to the post-exploitation skill. Do not keep exploring from inside `msfconsole`.
- Run `sessions -K` before you exit. A session left open is unfinished work, not persistence you are allowed to keep.

## Do not run

- `auxiliary/dos` and any module whose purpose is to crash or exhaust the service
- Persistence modules: cron, services, SSH keys, Run keys, new local users left behind, or `exploit/multi/handler` left running after the proof
- `set RHOSTS` to a file, a range, or a hostname that is not in scope
- Credential or password modules that spray an account list. Weak-password testing belongs to that skill and stays rate-limited

## Failure recovery

- Database init warnings on first launch are not a failed check. Re-run the same `-x` command.
- `check` returning "cannot tell" is a proof gap, not a vulnerability. Name the version you matched and what a safe confirmation would be.
- A session that dies immediately is a failed attempt. Record the module and the error, then try the next matched module or stop.

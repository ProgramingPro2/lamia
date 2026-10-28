---
name: social-engineering
description: Authorized human-targeted testing against the operator's own personnel and test channels, with the scope gates, stop conditions, and reporting obligations that apply before anything is sent
---

# Social Engineering

Use this skill when a path needs a human step that technical testing cannot reach: a credential a test user would hand over, a link a test user would click, a workflow that only completes when someone approves it. It covers scope, gates, stop conditions, and reporting. Pair it with `business_logic` when the human step is part of a workflow you can also drive directly.

It does not cover message bodies, call scripts, pretext narratives, or credential-capture pages. Build the test from the operator's approved material, not from this file.

## Authorization Gates

All of these are entry conditions, not advice. A test that fails any one of them does not run.

- **Named population.** The operator names the test population in scope. "Employees" or "the company" is not a population; a named team, a named list of test accounts, or a named channel is.
- **Named channel.** The operator names the approved channel: which mailbox, which chat space, which phone numbers, which system. Testing outside that channel is out of scope.
- **Own personnel only.** Targets are the operator's own personnel, test accounts, and test channels. Never third parties, vendors, customers, suppliers, or the public.
- **Designated identities.** Send from operator-designated test identities and mailboxes. Do not register lookalike domains or accounts the operator did not provision.
- **Constructed pretexts only.** Do not impersonate a real named person, a real external brand, or a real government body. A constructed role inside the operator's own organization is the ceiling.
- **Recorded approval.** If the population or the channel is not stated in the run, record it as an open item and do not run the test. An unrecorded gate is a closed gate.

## Data Handling

- Collect only what the test needs to prove reach: whether a message was delivered, opened, clicked, or a form submitted.
- Never collect, store, or reuse real credentials, MFA codes, session tokens, or personal data belonging to a real person.
- If a real secret is exposed, stop the test, do not record the value, and report the exposure to the operator. Note it happened, never what it was.
- Do not retain harvested submissions beyond the run. Report the count and the fields, not the values.

## Pressure Limits

- No threats, and nothing that implies harm to a person.
- No urgency built on job loss, safety, disciplinary action, or financial hardship.
- No targeting of personal accounts, personal devices, or non-work channels, even when the person is in the test population.
- No leverage over an individual's standing, relationships, or livelihood. Persuasion about the task is the limit; pressure on the person is not available.

## Stop Conditions

Stop the test immediately and report when any of these happens:

- A target asks to stop, or asks whether this is a test. Do not continue with that person, and do not talk them out of the question.
- The test reaches a real customer, a real vendor, or anyone outside the named population.
- The test would touch production customer data, or a live financial or safety action.
- A real credential, token, or personal record surfaces, per the data handling rules above.
- The operator withdraws the scope or the channel.

Stopping is a result. Record where it stopped and why.

## Running The Test

- Confirm the gates in the run record before the first message, so the approval exists before the action that needs it.
- Keep each send small and reversible: one channel, one population, no follow-on escalation without the operator's approval.
- Rate-limit. A burst looks like a real campaign and damages the target's trust in the exercise.
- Keep the technical path ready, so the human step is the only thing being tested and a success can be followed to its end impact immediately.
- Do not build persistence, forwarding rules, mail filters, or anything else that outlives the run.

## Reporting

Report enough for the operator to run the follow-up and the awareness debrief:

- What was sent, and on which channel.
- Who received it, by role and team, never by personal identity.
- What was clicked, submitted, or handed over, and how many of the population did it.
- Where the test stopped, if it stopped, and why.
- What the technical path reached after the human step succeeded, scored at that end impact rather than at the click.
- What the operator should do next: which accounts to reset, which people to brief, which control failed.

## Closure

A social engineering path closes the same way any other path does: confirmed with evidence, ruled out with the control that stopped it, or recorded as a proof gap. A test that reached nobody is not a ruled-out path; it is a proof gap about delivery, and it says what would settle it.

---
name: saml
description: SAML response testing for signature scope, assertion audience, recipient, and replay
---

# SAML

SAML bugs are almost always in how the service provider checks the response, not in the identity provider. You need a test account that can complete login, and the SP's ACS URL in scope. Capture one real response, then change one thing at a time.

## What to capture

- The `SAMLResponse` posted to the assertion consumer service
- Whether it is signed at the response, the assertion, or both, and which certificate the SP trusts
- `Audience`, `Recipient`, `Destination`, `InResponseTo`, `NotOnOrAfter`, `SubjectConfirmationData`, and the `NameID` of the test account

Decode the POST body. Do not log the raw response into the report; describe the field you changed and the decision the SP made.

## Checks

Work through these on the captured response. Each one is its own result.

- **Signature scope.** Modify an unsigned copy of the `NameID` or a group attribute while leaving a signature that does not cover that element. If the SP still accepts it, the signature is not binding the claim you changed. If both the response and the assertion are signed, changing either unsigned is the test; an accepted modified assertion is the finding.
- **Audience and recipient.** Replay the assertion against a second in-scope SP, or change `Recipient` to another ACS you are allowed to hit. Acceptance means the SP is not enforcing the restriction.
- **Replay.** Submit the same valid response twice, and submit it after `NotOnOrAfter`. A second session from a spent response is the finding.
- **InResponseTo.** Submit a response that was not issued for the outstanding request. If the SP accepts it, an attacker who can obtain any assertion for the account can use it.
- **Comment and truncation.** If the parser treats a comment or a truncated value as the end of `NameID` while the signature was computed over the full value, show the authenticated identity differing from the signed identity.

XML signature wrapping is the signature-scope check above: the SP verifies a signed element and then reads a different, unsigned one. Show the two elements and which identity the session received.

## Proof and limits

The proof is a session whose identity or role is not the one the identity provider signed for that request, demonstrated with test accounts. Do not forge assertions for real employees, do not remove the signature and call a rejected response a finding, and do not disable TLS checks on the identity provider.

## Ruled out

The SP rejects the response when the signed `NameID` or attribute is altered, enforces `Audience` and `Recipient`, and rejects a replayed or expired assertion. Name which of those responses you observed.

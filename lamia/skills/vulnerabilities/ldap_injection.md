---
name: ldap-injection
description: LDAP injection testing for authentication filters and directory search queries
---

# LDAP Injection

LDAP filters are often built by concatenating user input into `(& (uid=...)(password=...))` or a search filter. A successful injection returns a directory entry, attribute, or authentication decision the caller should not get. A wildcard that dumps the directory is not the proof you want.

## Where it shows up

- Login forms and "forgot username" lookups whose error or timing changes with the filter
- Address books, user search, group membership, and admin user pickers
- HTTP parameters named `user`, `uid`, `filter`, `query`, `member`, `dn`
- Application code that formats an LDAP filter string instead of using a filter API with escaped assertions

## Detection

Send a pair of values that should differ only if the filter structure changed, and compare status, body length, and which account comes back:

- A benign value you control, such as a test account that exists
- The same value with a filter metacharacter (`*`, `(`, `)`, `\`, NUL) that the application does not reject as a bad request
- A boolean pair: one predicate that should match only your account, and one that should match an account you do not own, if the filter is concatenated

Useful contexts, adapted to the filter you can see in source or infer from errors:

- Authentication: close the password assertion and add a clause that is always true, then compare with a clause that is always false
- Search: `*` versus a value that matches nothing, then a value that matches one other test account

Encode `* ( ) \ /` the way the client does (raw in JSON, URL-encoded in a query). A `400` that names a filter syntax error is a lead. A `200` that returns another subject's attributes is the finding.

## Proof

Show one of these, using operator-approved test accounts:

- Authentication as a test account without its password, with the request and the resulting session
- A search response that contains an attribute of an account the caller does not own, which the same request without the metacharacter does not return

Do not walk the directory, dump `userPassword`, or use a filter whose only purpose is to return every entry. One extra record is the proof. If the server times out or returns a size-limit error, narrow the filter; do not retry harder.

## Ruled out

Name the control: an LDAP escape or filter API that treats the input as an assertion value, demonstrated by the metacharacter being matched literally or rejected before the directory is queried. A bind that still requires the real password is not injection. An error page with no behavior change is not a finding.

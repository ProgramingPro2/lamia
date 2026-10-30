---
name: xpath-injection
description: XPath injection testing for authentication and XML node queries built from user input
---

# XPath Injection

XPath injection happens when user input is concatenated into an expression such as `//user[name='...' and password='...']`. The impact is reading or matching a node the caller should not reach. Treat it like SQL injection against an XML document: prove a different node, not a parser error.

## Where it shows up

- Login and account lookup against an XML user store
- Search, report, and "find node" parameters passed to an XPath engine
- Source that builds an expression with string formatting around `name`, `password`, `id`, or `query`
- SOAP or XML APIs that take an XPath string from the client. Client-supplied XPath is the bug even before a payload, if the endpoint evaluates it

## Detection

Compare two requests that differ by one predicate:

- A value that matches a fixture you are allowed to see
- The same request with a quote or bracket that changes the expression, so a boolean-true predicate and a boolean-false predicate return different nodes or different lengths
- `count()` or `string-length()` only as a blind channel when the response body is a single boolean or a stable template. Keep the difference to one node

Quote style follows the expression you are in (single quote, double quote). If the application rejects the character with a validation error before the XML is queried, record that control and try the encoding the validator skips, once.

## Proof

- Return a node or attribute that belongs to another test account, in the same response field the benign query uses for the caller's own node
- Or authenticate a test account by changing the predicate, and show the session that results

Do not extract the whole document. One unauthorized node is enough. If the engine returns a syntax error and nothing else, that is a lead, not a finding.

## Ruled out

The input is passed as an XPath variable, or it is escaped so quotes cannot close the literal, and the boolean pair returns the same authorized node both times. Say which of those you observed.

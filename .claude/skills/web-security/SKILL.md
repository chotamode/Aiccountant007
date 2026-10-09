---
name: web-security
description: Apply web application security conventions when writing or reviewing anything crossing a trust boundary — request handlers, auth, DB queries, file/shell access, rendering user content, secrets, and dependencies. OWASP-aligned checklist for input validation, injection (SQL/command/XSS), authn/authz and IDOR, secret hygiene, CSRF, secure transport. Use for endpoints, auth flows, forms, or any handling of untrusted input. Mirrors rules/security/web-security.mdc.
---

# Web Security

Claude-Code counterpart to `rules/security/web-security.mdc`. Security is a functional
requirement applied while coding, not a later pass. Assume every input crossing a trust
boundary is hostile until validated.

## Checklist (run on any code touching a trust boundary)

**Input** — validate/sanitize ALL external input on the **server** (bodies, params, headers, cookies, uploads, webhooks). Validate with a schema, fail closed, prefer allow-lists. Client-side validation is UX only.

**Injection**
- SQL/NoSQL: parameterized queries or ORM only — never string-concatenate user input.
- Command/path: no user input to a shell, no dynamic `eval`; confine file paths (block `../`).
- XSS: rely on framework escaping; treat `dangerouslySetInnerHTML`/`innerHTML` as a red flag (sanitize with DOMPurify if unavoidable); set a CSP.

**Auth** — authorize **every** request server-side for the specific resource+action; prevent IDOR (verify ownership of any id passed). Hash passwords with bcrypt/argon2. Sessions in `HttpOnly`+`Secure`+`SameSite` cookies; protect state-changing requests from CSRF. Least privilege for tokens/DB users.

**Secrets & transport** — no secrets in source or git; use env vars / a secret manager (see the `docker` skill and `rules/web-architecture/*`). Only `NEXT_PUBLIC_`-style config reaches the browser. HTTPS + HSTS + secure headers; never log secrets/tokens/PII.

**Dependencies & errors** — patch deps; run `npm audit`/`pip-audit`/Dependabot in CI, criticals fail the build. Generic client errors (no stack traces/SQL/paths); log details server-side. Rate-limit auth and expensive endpoints.

## How to use
When adding or reviewing endpoints, auth, queries, file/shell access, or rendering of
user content, walk this checklist for the specific trust boundary. When unsure whether
something is exploitable, assume it is and close it. Read `rules/security/web-security.mdc`
for the full rationale and examples.

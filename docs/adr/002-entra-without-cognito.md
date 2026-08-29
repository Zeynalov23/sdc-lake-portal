# 002 — Authenticate against Entra directly, no Cognito broker

**Status:** Accepted · 2026-08

## Context

Logins went Entra → Cognito user pool → application. Cognito acted as a broker,
federating an upstream identity provider so that a Cognito *identity pool*
could exchange the resulting token for AWS credentials.

Once [ADR 001](001-app-level-authorization.md) removed the identity pool, the
broker had nothing left to do. It still cost a second set of client ids and
redirect URIs, a second token format to reason about, and one more service
that could fail.

## Decision

The frontend performs the OIDC authorization-code flow directly against Entra
as a confidential client, exchanging the code server-side with a client secret
and PKCE. The data service verifies the resulting ID token against Entra's
JWKS on every request.

Users are identified by the `oid` claim.

## Consequences

`oid` rather than `sub` is the part worth stating: `sub` is unique *per
application*, so the same person receives a different `sub` in a different app
registration. `oid` is the tenant-wide object id and is stable for the life of
the account. Every grant in DynamoDB is keyed on it, so email changes and
display-name changes do not affect access.

Tokens are held in httpOnly cookies, so page scripts cannot read them and an
XSS bug cannot exfiltrate a session.

The frontend decodes the ID token for display only. That is not a security
check — the signature, audience and expiry are verified server-side by the
data service, which is the only verification that counts. The frontend could
be lied to by its own client and it would not matter.

Cost: the platform is now tied to Entra as the identity provider. Supporting a
second provider would mean either reintroducing a broker or handling multiple
issuers in `auth.py`. For a single-tenant internal platform that is the right
trade.

## Alternatives considered

**Keep Cognito as a broker** — would allow federating several providers behind
one issuer. Rejected: no second provider is planned, and the hop added a
failure mode and a second identity model for no current benefit.

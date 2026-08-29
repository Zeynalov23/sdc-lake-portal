# 001 — Authorization in the application, not in IAM

**Status:** Accepted · 2026-08

## Context

The original design created AWS resources per space: two IAM roles (reader and
writer), two S3 access points, and a set of Cognito identity-pool role-mapping
rules. The intent was for AWS itself to enforce who could read what.

It did not work that way. The data service signed every S3 URL with its own
pod identity, so the user's personal AWS role was never used for anything. The
per-space roles existed, cost API calls to create, and were read by nothing.

The design also had a hard ceiling. An identity pool allows 25 role-mapping
rules per provider, and each space needed two, capping the platform at about
twelve spaces. Nothing in the code acknowledged that limit.

## Decision

Delete the per-space IAM roles, access points and identity pool. Store grants
in DynamoDB and enforce them in one module (`authz.py`), which resolves the
caller's allowed key prefixes. Every S3 operation is a presigned URL for one
specific object key, checked against those prefixes before signing.

## Consequences

A bug in `authz.py` is a security hole. With IAM enforcement, buggy
application code still could not exceed the role's permissions; now the
application is the only thing standing between a caller and the bucket. That
is a real loss and the main argument against this decision.

It is accepted because the protection was illusory: the pod signed everything
with its own identity regardless, so IAM was never actually constraining the
user. Removing the machinery made the real trust boundary visible instead of
implied.

In exchange: no 25-rule ceiling, no per-space AWS resources to create or clean
up, no IAM propagation delay on space creation, and one place to read to
understand who can do what. The provisioning service lost `iam:CreateRole`
entirely.

Mitigations: `authz.py` is deliberately small; the guards are the only path to
S3; prefix confinement is covered by tests that assert on cross-folder reads,
listing narrowing and revocation.

## Alternatives considered

**Keep per-space IAM roles and actually use them** — have the browser assume
the role and talk to S3 directly. This would give real AWS enforcement, but
requires handing AWS credentials to the browser, keeps the 25-rule ceiling,
and makes every permission change an IAM change with its own propagation
delay.

**S3 access points with policies per space** — enforcement without per-user
roles, but the policies would still have to name principals, which brings the
identity-pool problem back.

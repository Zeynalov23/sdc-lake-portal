# 003 — Writes go to the data service, not a Lambda behind API Gateway

**Status:** Accepted · 2026-08

## Context

Reads went to the data service in the cluster. Writes went to a separate
Lambda behind API Gateway, authenticated with a shared API key that the
frontend held. Two code paths, two deployment mechanisms, two auth models for
one application.

The API key was also a static credential in a Helm values file, and the Lambda
accepted `ownerId` from the request body — so a caller could nominate someone
else as the owner of a space they created.

## Decision

Delete the Lambda, API Gateway, the usage plan and the API key. Writes go to
the data service, which already verifies the Entra token on every request.

## Consequences

One service, one auth model, one deployment pipeline. The owner of a space is
now whoever the verified token says it is; the client cannot name anyone.

The static API key is gone, along with the question of how to rotate it.

Cost: the write path no longer scales independently of reads, and a data
service outage now takes writes down with it. For this workload — a handful of
control-plane writes per space — that is not a real constraint, and the write
volume is nowhere near needing separate scaling.

Also lost: API Gateway's built-in throttling. If rate limiting becomes
necessary it now has to be implemented in the cluster, at the Gateway or in
the service.

## Alternatives considered

**Keep the Lambda but authenticate with the Entra token** — would fix the auth
duplication but keep two deployment paths and two runtimes for one small API.

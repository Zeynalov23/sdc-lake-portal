# 014 — Secrets synced from Secrets Manager by External Secrets Operator

**Status:** Accepted · 2026-09

## Context

The Entra client secret was created with `kubectl create secret` after every
cluster rebuild. It was the only object in the cluster not reproducible from
this repository, which meant the claim in
[ADR 005](005-app-of-apps.md) — destroy the cluster, rebuild it from git — was
true with an asterisk.

## Decision

External Secrets Operator syncs `sdc-lake-dev/entra-client-secret` from AWS
Secrets Manager into a Kubernetes Secret named `sdc-lake-entra`.

## Consequences

The deployments did not change. They already referenced the Secret by name
through `secretKeyRef`, so replacing a hand-made Secret with an operator-made
one was invisible to them. That is the property worth having: the consumer
does not know or care where the value came from.

Terraform creates the Secrets Manager container but never the value. Anything
passed through Terraform is written to the state file in plaintext, and the
state file lives in S3 — so the value is set by hand once, out of band, and
then survives everything.

**The value does end up in etcd.** ESO writes a normal Kubernetes Secret, so
anyone with `get secrets` in the `app` namespace can read it. EKS encrypts
etcd at rest and RBAC controls access, which makes this acceptable, but it is
a real difference from the alternatives. Secrets Store CSI Driver mounts values
as files without creating a Secret; calling Secrets Manager directly from the
application avoids the cluster entirely. Both were rejected: CSI needs the app
to read files rather than environment variables, and direct SDK calls put
AWS-specific credential code into every service that needs a secret.

The IAM policy names two secrets explicitly. A wildcard would let a typo in an
`ExternalSecret` pull any secret in the account into a namespace where it can
be read — the store is cluster-scoped, so the IAM policy is the real boundary.

**Two Applications, not one.** Sync waves order the apply *within* an
Application, but ArgoCD dry-runs every manifest in an Application before any
wave runs. An `ExternalSecret` sitting beside the operator that defines its CRD
fails validation before ordering can help. Splitting the operator (wave 1) from
the configuration (wave 2) means the second sync begins only after the first
has completed and the CRDs exist.

The alternative, `SkipDryRunOnMissingResource=true`, works inside one
Application but hides the dependency in a flag rather than showing it in the
repository layout.

**Rotation is not instant.** The operator re-reads Secrets Manager hourly, but
pods read environment variables once at container start, so a rotated value
only reaches a running pod when it restarts. Making rotation take effect
without a restart would mean mounting the secret as a file and re-reading it,
which the application does not currently do.

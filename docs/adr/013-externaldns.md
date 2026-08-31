# 013 — DNS records maintained by ExternalDNS

**Status:** Accepted · 2026-08

## Context

The cluster is destroyed and rebuilt daily, and each rebuild provisions a new
NLB with a new hostname. Route 53 records written by hand would point at a
load balancer that no longer exists every morning.

## Decision

Run ExternalDNS, reading Gateway API resources, with records scoped to
`sdc-lake.jobnode.io`.

## Consequences

Hostnames are declared once, in the HTTPRoute that already needs them. Adding
a service means adding a route; the DNS record follows. There is no second
place to update and no way for the two to disagree.

**Ownership is tracked by TXT records.** ExternalDNS writes a TXT record beside
each managed record, containing the owner id, and will only modify or delete
records whose TXT marker matches. Without that it could not distinguish its own
records from ones created by hand.

The owner id is `sdclake-platform-dev`: stable across rebuilds, so a new
cluster adopts yesterday's records rather than orphaning them. It is not
unique per cluster — a second cluster with the same id would claim the same
records and the two would fight, each overwriting the other. The `-dev` suffix
exists so that adding a second environment is an obvious change rather than a
subtle outage.

**`--policy=sync`**, so deleting an HTTPRoute deletes its record. The
alternative, `upsert-only`, never deletes: safer against a mistake in the
domain filter, but it accumulates stale records on every teardown, which for a
cluster rebuilt daily would be most of them.

The IAM policy allows `ChangeResourceRecordSets` on the platform zone only.
`ListHostedZones` and `ListResourceRecordSets` have to be granted on `*`
because Route 53 does not support resource-level permissions for them — a
limitation of the service, not a choice. The write permission, which is the
one that matters, is properly scoped.

Deployed through ArgoCD rather than Terraform, per
[ADR 004](004-terraform-gitops-boundary.md): it is not a bootstrap dependency,
so it belongs on the GitOps side. Its ServiceAccount is referenced by a Pod
Identity association in Terraform, with the same unvalidated string agreement
described there.

**One replica, `Recreate` strategy.** ExternalDNS has no leader election, so
two instances would reconcile the same zone concurrently and race on the same
records.

# 005 — App-of-apps, with the root Application outside the managed tree

**Status:** Accepted · 2026-08

## Context

Something has to create ArgoCD `Application` objects. Applying each one with
`kubectl` leaves them outside git, so they do not survive a cluster rebuild.
Creating them in Terraform puts Kubernetes objects back in Terraform, against
[ADR 004](004-terraform-gitops-boundary.md).

## Decision

One root Application, applied once by `make up`, whose source is
`argocd/apps/child/`. Every file in that directory is an Application pointing
at a chart under `apps/`.

The root Application lives in `argocd/apps/`, one level above the directory it
watches, so it does not manage itself.

## Consequences

Adding a service is: add a chart, add one Application file, push. No
`kubectl`, no `terraform apply`.

The root being outside the managed tree is deliberate. A self-managing root
can prune itself — and with `prune: true`, an Application that deletes itself
takes everything it owns with it. Keeping the bootstrap object out of its own
scope removes that failure mode entirely.

Exactly one imperative step remains: applying the root Application. That is
the irreducible bootstrap, and reducing it from N objects to one is the point.

`make down` destroys every Application along with the cluster, and this is
fine: Applications are a projection of the repository, not data. `make up`
plus one command rebuilds all of it. The daily teardown, adopted to control
cost, incidentally proves the disaster-recovery story every single day.

The limit of that claim: it holds only for what ArgoCD manages. Anything
created in the cluster and not in git — a hand-made Secret, for example — is
lost. That is the argument for External Secrets, not yet implemented.

Sync waves are used to order the platform chart before the application charts.
It costs nothing today and matters once NetworkPolicies live there.

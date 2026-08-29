# 010 — Gateway API CRDs come from the Envoy Gateway chart

**Status:** Accepted · 2026-08

## Context

Envoy Gateway needs the Gateway API CRDs. They were being installed by a
`null_resource` running `kubectl apply` against a GitHub release URL, pinned
to the standard channel at v1.2.0.

## Decision

Remove the separate installation. The `gateway-helm` chart ships the CRDs in
its own `crds/` directory and installs them.

## Consequences

The removed resource was not merely redundant, it was conflicting: the chart
carries the *experimental* channel for its version, while the `null_resource`
applied the *standard* channel at a different version. Two sources for the
same CRDs, with whichever ran last winning.

The ordering the old comment claimed was never actually enforced, either —
`helm_release.envoy_gateway` depended only on `module.eks`, not on the CRD
resource. It worked because Helm installs its own CRDs first regardless.

The remaining limitation is a Helm one, and worth knowing: **Helm installs
`crds/` on first install but never on upgrade.** Bumping the chart version
will not update the CRDs. Doing that requires a deliberate
`kubectl apply --server-side` of the new CRD set, and is the main argument for
eventually managing CRDs through ArgoCD, which reconciles at object level
rather than release level.

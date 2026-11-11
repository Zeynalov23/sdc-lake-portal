# 016 — Disruption budgets on the request-serving services only

**Status:** Accepted · 2026-11

## Context

Nothing in the cluster declared how much voluntary disruption it could
tolerate. A node drain, a version upgrade or a consolidation could take every
replica of a service at once and nothing would refuse it.

## Decision

A `PodDisruptionBudget` with `maxUnavailable: 1` on `data-service` and
`frontend-service`. The frontend moves from one replica to two so that the
budget means something. `provisioning-service` deliberately has none.

## Consequences

**maxUnavailable rather than minAvailable.** `minAvailable` set equal to the
replica count permits zero disruptions: `ALLOWED DISRUPTIONS` sits at 0, every
eviction is refused, and a drain retries forever instead of being constrained.
The failure is silent — the budget looks correct until the first drain, which
may be weeks later — and on a managed node group the upgrade eventually times
out and force-terminates the node anyway, turning a protected voluntary
disruption into an unprotected involuntary one. `maxUnavailable` also stays
correct when the replica count changes, which `minAvailable` does not.

**A budget cannot create availability.** The frontend ran one replica, where
a PDB is either useless — `maxUnavailable: 1` permits the only pod to go — or
harmful. Two replicas is the actual fix; the budget is what stops both going
at once.

**Nothing is protected from node failure.** A PDB gates the eviction
subresource. Node-pressure eviction by the kubelet does not go through it, and
a node that dies does not ask. A rollout does not consult it either, because
the Deployment controller deletes pods directly rather than evicting them —
so `maxUnavailable` in the rollout strategy and `maxUnavailable` in the budget
are different numbers read by different components.

**provisioning-service has no budget, on purpose.** It is a single-replica
queue consumer driven by an EventBridge pipe from SQS. Work it was handling
when the pod dies returns to the queue and is picked up by the replacement, so
a disruption costs latency rather than correctness. A budget here would
protect nothing and would block drains if written carelessly. The honest
statement is that this service tolerates disruption, not that it is unguarded
by oversight.

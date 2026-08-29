# 009 — Memory limits, no CPU limits

**Status:** Partially applied · 2026-08

## Context

Every container needs resource requests so the scheduler can place it. Whether
to also set limits is contested.

## Decision

Set requests for CPU and memory. Set a memory limit. Do not set a CPU limit.

## Consequences

CPU is compressible: exceeding a CPU limit means the kernel throttles the
container via CFS quota. A container that briefly needs more CPU is slowed
down even when the node has idle cores, which adds latency for no benefit. The
CPU *request* already guarantees a share under contention, which is the
property actually needed.

Memory is not compressible. Exceeding it means the OOM killer, so a limit is
real protection against one container taking down its neighbours. Setting the
memory request equal to its limit also puts the pod in the Guaranteed QoS
class, so it is the last to be evicted under node pressure.

The counterargument, which is legitimate: on a multi-tenant cluster, CPU
limits stop a noisy neighbour and make capacity planning predictable. This
cluster runs one team's workloads, so the throttling cost outweighs that.

**Not yet consistent.** The frontend chart follows this; the provisioning
service still carries `cpu: 500m`. That is an oversight rather than a
deliberate exception and should be reconciled.

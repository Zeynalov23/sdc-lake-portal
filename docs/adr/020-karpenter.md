# 020 — Karpenter provisions nodes; the node group is a floor

**Status:** Accepted · 2026-11

## Context

The cluster ran on one managed node group: `t3.medium`, min 1, desired 2,
max 4. The autoscaling group could grow, but nothing ever asked it to —
there was no Cluster Autoscaler and no Karpenter, so `desired_size` was a
number Terraform set and nothing changed.

That made the HPA in [ADR 018](018-autoscaling-on-request-rate.md)
incomplete. It could ask for ten replicas of the data service, and once two
`t3.medium` nodes were full the extra pods would stay `Pending` forever.
Scaling pods without being able to scale nodes is a loop with no output.

It was also already tight. A `t3.medium` is 2 vCPU and roughly 3.2 GiB
allocatable, and the monitoring stack added in
[ADR 015](015-observability.md) requests 1 GiB for Prometheus alone.

## Decision

Karpenter, installed by Terraform, with a NodePool and EC2NodeClass managed
by ArgoCD. The managed node group stays as a floor: enough to run Karpenter
and the control-plane-adjacent workloads.

## Consequences

**Karpenter is pinned off its own nodes.** The node group carries a
`karpenter.sh/controller` label and the chart has a matching nodeSelector.
Without it, a consolidation decision could drain the node the controller is
running on — and the controller has to stay alive to finish what it started.
The node group is not tainted, so ordinary workloads still use it; only the
controller is pinned to it.

**The chart is installed by Terraform, the NodePool by ArgoCD.** Not an
inconsistency: the chart's values are Terraform outputs (the interruption
queue, the node IAM role), and ArgoCD cannot read Terraform state. The
NodePool and EC2NodeClass are custom resources and belong in git with
everything else, which makes this the fourth time the same CRD ordering
problem has had to be solved with a separate Application in a later wave.

**Discovery is by tag, and a missing tag fails quietly.** The private
subnets and the node security group now carry `karpenter.sh/discovery`. If
they did not, `subnetSelectorTerms` would match nothing and every NodeClaim
would fail — with an error that names the selector rather than the missing
tag.

**Spot by default.** Karpenter picks the cheapest instance that fits, which
is almost always spot. The module creates an SQS queue fed by EventBridge
rules for interruption notices, so a reclaim arrives as roughly two minutes'
warning and Karpenter drains the node rather than losing it. `on-demand`
stays in the list so there is somewhere to go when spot capacity for a shape
runs out.

**Consolidation is continuous, and that is the point.** Karpenter removes
empty nodes and replaces underutilised ones with something smaller, on a
two-minute horizon. This is not a maintenance event — it is a background
process that drains nodes all day. It is why the disruption budgets in
[ADR 016](016-disruption-budgets.md) stopped being optional, and the
disruption budget of one node here is the other half of that.

**Limits are a cost control, not a capacity plan.** 48 vCPU and 192 GiB cap
what Karpenter may ever launch. Without a ceiling, one pod with a mistaken
resource request — or a runaway HPA — provisions until the account quota
stops it. On a personal account that is the difference between a bad
afternoon and a bad invoice.

**No burstable instances.** The NodePool allows `c`, `m` and `r` families
from generation 6 up, not `t`. Burstable instances are cheaper but their CPU
credits make sustained workloads unpredictable, and Prometheus is exactly
the kind of workload that exhausts them quietly. The node group is still
`t3.medium`, which is defensible for a floor and not for real capacity.

**The requirements are deliberately broad.** Constraining Karpenter to one
instance type would reproduce the node group it replaces. The bounds here
only keep it to current-generation hardware at sane sizes; which instance
fits is Karpenter's decision to make from the pending pods.

**Three scaling layers now exist and none of them know about each other.**
The HPA adds pods, Karpenter adds nodes, the node group holds a floor. They
coordinate only through the scheduler: a pending pod is the signal that
crosses between them. That is worth stating plainly, because it is also the
failure mode — if pods are pending for a reason Karpenter cannot fix, such
as a zonal volume or an unsatisfiable affinity, it will launch nothing and
nothing will say why.

**Subnet addresses are still finite.** The two private subnets are a `/24`
each. Karpenter can now create nodes faster than before, and every pod on
them takes a VPC address from the same pool.

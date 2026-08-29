# 008 — Persistent and cluster infrastructure in separate states

**Status:** Accepted · 2026-08

## Context

The cluster is destroyed at the end of most working sessions to control cost.
The data must not be.

## Decision

Two Terraform root modules with separate state:

* `infra-persistent` — DynamoDB, S3, SQS, ECR, IAM, Secrets Manager,
  EventBridge Pipe. Applied once, rarely changed.
* `infra-cluster` — VPC, EKS, ArgoCD, Envoy Gateway, Pod Identity
  associations. Created and destroyed freely.

`infra-cluster` reads `infra-persistent` outputs via remote state.

## Consequences

`make down` cannot destroy data, because the data is not in that state file.
That is a structural guarantee rather than a matter of remembering to use
`-target`.

`make up` applies in two phases: `-target=module.vpc -target=module.eks`
first, then everything else. This is not a stylistic choice. The Kubernetes
and Helm providers are configured from EKS outputs and evaluated at plan time,
so on an empty state they cannot authenticate to a cluster that does not exist
yet. The targeted apply creates the cluster, then the second pass configures
the providers against something real.

The usual advice is to split those into separate states as well. The two-phase
`make up` achieves the same result with one fewer state file to manage; if the
cluster module grows, splitting is the next step.

`make down` deletes Gateway resources before running destroy, so the NLB is
deprovisioned before Terraform tries to delete the VPC. Without that the VPC
delete hangs on an ENI that AWS still owns — a dependency Terraform cannot see
because it did not create the load balancer.

Cost: a change spanning both states is two applies in the right order, and
remote state lookups couple the modules loosely.

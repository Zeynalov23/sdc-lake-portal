# 004 — Terraform owns AWS, ArgoCD owns cluster contents

**Status:** Accepted · 2026-08

## Context

Both tools can create Kubernetes objects. Terraform has a Kubernetes provider;
ArgoCD can only manage things inside the cluster. Without an explicit rule,
objects land wherever was convenient at the time, and nobody can say which
tool owns a given resource.

The repository had drifted exactly that way: ServiceAccounts created by
Terraform, an HTTPRoute applied by `local-exec kubectl`, and Gateway API CRDs
installed by a `null_resource`.

## Decision

**Terraform owns things with an AWS API and a lifecycle independent of the
cluster.** VPC, EKS, IAM, DynamoDB, SQS, ECR, Secrets Manager, Pod Identity
associations.

**ArgoCD owns things that live in the cluster's API server.** Deployments,
Services, ServiceAccounts, HTTPRoutes, and later NetworkPolicies and
ExternalSecrets.

Two deliberate exceptions:

* **ArgoCD itself** is a Helm release in Terraform. Something has to exist
  before the thing that manages everything else.
* **Namespaces** stay in Terraform. They are containers that predate the
  workloads, and putting them in a chart raises the question of which of
  several Applications owns them.

## Consequences

Every `null_resource` running `kubectl` was removed. Those resources recorded
"the command ran" rather than "the object exists": changing the YAML produced
no Terraform diff, deleting the object by hand produced no diff either, and
`terraform apply` required kubectl and a kubeconfig on the machine running it.

ServiceAccounts moved into the charts of the services that use them. This is
safe because a Pod Identity association is just four strings — cluster,
namespace, service account name, role ARN — and AWS never checks whether the
ServiceAccount exists. Ordering therefore does not matter, and a cluster
rebuild works in either order.

The cost of that: the agreement between Terraform and the chart is by
convention, not by reference. Nothing validates it. Rename the ServiceAccount
in the chart, or deploy to a different namespace, and both systems stay green
while the pod fails at runtime with `AccessDenied` on its first AWS call. A CI
check comparing associations in state against `serviceAccountName` in the
charts is the intended mitigation and is not yet written — see
[ADR 011](011-known-gaps.md).

## Alternatives considered

**Terraform for everything**, using `kubernetes_manifest`. Rejected: the
provider needs the cluster API reachable at plan time, which breaks a
first-time apply, and it gives up ArgoCD's continuous reconciliation.

**ArgoCD for everything**, with Crossplane or ACK managing AWS. Rejected as
too much new machinery for the value; Terraform for AWS is also the more
common industry setup and therefore the more useful thing to be fluent in.

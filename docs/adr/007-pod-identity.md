# 007 — EKS Pod Identity rather than IRSA

**Status:** Accepted · 2026-08

## Context

Pods need AWS credentials. The options on EKS are IRSA (IAM Roles for Service
Accounts) and Pod Identity.

## Decision

Pod Identity, via the `eks-pod-identity-agent` addon and
`aws_eks_pod_identity_association` resources in Terraform.

## Consequences

The mechanism, since it is worth being able to describe: the agent runs as a
DaemonSet and serves a link-local address, `169.254.170.23`. Pods receive
`AWS_CONTAINER_CREDENTIALS_FULL_URI` and
`AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE`. The SDK presents the projected
ServiceAccount token from that file, the agent validates it against the API
server, looks up the association for (namespace, service account), calls STS,
and returns temporary credentials.

The application contains no credential code at all. boto3 reads those
variables itself, which is also why the same code works locally against an
exported session — only the source of the credentials differs.

Why not IRSA: IRSA requires an OIDC provider per cluster and an IAM trust
policy naming that cluster's issuer URL. A role therefore cannot be reused
across clusters without editing its trust policy, and every new cluster means
touching IAM. Pod Identity roles trust `pods.eks.amazonaws.com` generically,
and the mapping lives in an EKS association instead of an IAM trust policy —
so a cluster rebuild does not touch IAM at all. That matters here because the
cluster is destroyed and recreated daily.

The addon must be installed before compute (`before_compute` in the EKS
module), or pods scheduled during bootstrap start without a credential source.

Cost: Pod Identity is EKS-only. IRSA works on any Kubernetes cluster with an
OIDC issuer, including self-managed ones. This platform is EKS-only by design,
so that portability is not being given up in practice.

# 012 — TLS terminates at the NLB, with the certificate ARN pinned in git

**Status:** Accepted · 2026-08

## Context

The platform needs HTTPS on real hostnames. Two things had to be decided:
where TLS terminates, and how the certificate reaches the Gateway manifest.

## Decision

TLS terminates at the NLB using an ACM certificate, attached with the
`service.beta.kubernetes.io/aws-load-balancer-ssl-cert` annotation. The ARN is
pinned in `apps/platform/helm/values.yaml`.

## Consequences

The certificate's private key never leaves AWS. Nothing has to hold it in a
Kubernetes Secret, so there is no key to rotate, mount or leak. That is the
main reason for terminating at the load balancer rather than in Envoy.

The 443 listener is therefore declared as `protocol: HTTP`. By the time a
request reaches Envoy it has already been decrypted; declaring HTTPS would
make Envoy try to terminate TLS a second time on a connection that carries
none.

**No HTTP-to-HTTPS redirect.** An NLB is layer 4 and adds no
`X-Forwarded-Proto`, so Envoy cannot distinguish a request that arrived
encrypted from one that did not. Rather than guess, port 80 is not exposed at
all. A redirect would require an ALB, or proxy protocol enabled on the NLB and
configured in Envoy.

**The ARN is pinned by hand.** Certificate discovery by hostname exists in the
AWS Load Balancer Controller, but only for ALB via Ingress; an NLB provisioned
through the in-tree cloud provider accepts nothing but an explicit ARN. Since
an ARN is generated rather than chosen, there is no naming convention that
Terraform and the chart could follow independently, so the value has to travel
between them.

Pinning it in `values.yaml` was chosen over having Terraform generate the file
or write a ConfigMap: it keeps the repository the complete description of what
is deployed, and makes the coupling visible rather than implicit.

The risk is a silent one — replacing the certificate changes the ARN, and
nothing here would notice. Renewal keeps the same ARN, so in normal operation
this does not move.

## Alternatives considered

**AWS Load Balancer Controller with an ALB** — would give certificate
discovery by hostname, path-based routing and WAF integration, removing the
pinned ARN entirely. Rejected for now: it means running a second ingress
controller and reworking the Gateway API setup. It is the natural next step if
the ARN coupling becomes a real problem.

**Terminate TLS in Envoy with the certificate in a Secret** — standard Gateway
API, and portable off AWS. Rejected: it puts a private key in etcd and creates
a rotation problem that ACM otherwise handles.

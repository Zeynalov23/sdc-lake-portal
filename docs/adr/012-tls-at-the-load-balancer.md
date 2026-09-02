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

## Addendum — redirects behind a layer 4 load balancer

Terminating TLS at the NLB has a consequence that only appeared once the app
was reachable on a real hostname: **the application cannot learn its own public
URL from an incoming request.**

Next.js was building OAuth redirects with `new URL(path, req.url)`. Behind the
NLB, `req.url` carries the address the pod is listening on rather than the
address the client used. Worse, that address is literally `0.0.0.0:3000`,
because the container is started with `HOSTNAME=0.0.0.0` — a fix applied
earlier so that `kubectl port-forward` would work, since Next.js standalone
otherwise binds only to the pod name and refuses connections on localhost.

So an earlier fix silently broke something downstream of it: after logging in,
users were redirected to `0.0.0.0:3000`. The general shape is worth
remembering — changing what a component reports about itself breaks anything
that trusts that report.

The public origin is now passed explicitly as `APP_BASE_URL`, and every
redirect is built from it. An ALB would supply `X-Forwarded-Host` and
`X-Forwarded-Proto` and make this inferable, which is one more entry on the
list of things layer 7 gives you.

A second bug surfaced at the same time and is unrelated to the load balancer,
but worth recording because it was invisible in development: the login route
wrote its PKCE verifier and state cookies through the `next/headers` jar and
returned a separately constructed `NextResponse`. Those writes do not attach,
so no state cookie was stored and every login failed the CSRF check with
`state_mismatch`. Cookies must be set on the response that is actually
returned.

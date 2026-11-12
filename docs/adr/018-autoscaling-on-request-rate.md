# 018 — The data service scales on request rate, not CPU

**Status:** Accepted · 2026-11

## Context

The data service ran at a fixed two replicas. Two is a guess: enough to
survive a node drain, unrelated to how much traffic arrives.

The obvious autoscaler is an HPA on CPU, and it is the wrong one here. The
service spends most of its time waiting on S3 and DynamoDB, so a pod can be
saturated on in-flight requests while its CPU sits low — exactly when more
replicas are needed, and exactly when CPU gives no signal.

CPU has a second problem that is easy to miss. The HPA measures utilisation
as a percentage *of the request*, so raising a container's CPU request halves
the reported utilisation at identical load. Someone correcting resource
requests changes the scaling threshold without touching the HPA, and nothing
in either object records the connection.

## Decision

`prometheus-adapter` serves `http_requests_per_second` through the custom
metrics API, derived from the RED metrics in
[ADR 017](017-red-metrics.md). The HPA targets 20 requests per second per
pod, between 2 and 10 replicas.

## Consequences

**The Deployment no longer declares `replicas`.** It cannot: the HPA writes
that field, ArgoCD runs with `selfHeal: true`, and a manifest that also
declared it would have the two of them reverting each other every few seconds
with the pod count oscillating for as long as both were running. Omitting the
field removes the conflict; an `ignoreDifferences` rule would only have hidden
it. This is the general shape of the problem that
[ADR 004](004-terraform-gitops-boundary.md) describes for Terraform and
ArgoCD — exactly one system owns each field — appearing again between ArgoCD
and a controller inside the cluster.

**metrics-server is still not installed.** `kubectl top` does not work and an
HPA on CPU or memory would report `<unknown>`. kube-prometheus-stack does not
include metrics-server; it ships kube-state-metrics and node-exporter, which
answer different questions. Nothing here needs it, but its absence is easy to
mistake for a broken cluster.

**The adapter's default rules are switched off.** They expose a large set of
cAdvisor-derived metrics nothing asks for, and every rule costs a Prometheus
query on each custom metrics API call. One rule is cheaper to reason about
and to debug.

**The rate window is two minutes, not five.** The HPA polls every fifteen
seconds, and a five-minute average lags a traffic spike badly enough that the
scale-up lands after the incident it was meant to absorb. Shorter is noisier;
the stabilisation windows absorb that.

**The windows are deliberately asymmetric.** Scale up immediately, scale down
only after five minutes of sustained low load. Being slow to add capacity
costs an outage; being slow to remove it costs a few minutes of extra pods.
It is also what stops the replica count oscillating around the threshold.

**Twenty requests per second per pod is a guess.** There is no production
traffic to derive it from. It is written down as a starting point and should
be replaced with a number measured against real load — which is the honest
state of every threshold in this repository, including the alert thresholds
in ADR 017.

**Three layers now scale independently.** The HPA adds pods, Karpenter would
add nodes when those pods will not fit, and neither knows about the other.
They coordinate only through the scheduler: pending pods are the signal that
crosses between them.

# 015 — kube-prometheus-stack, deployed from the upstream chart

**Status:** Accepted · 2026-11

## Context

Nothing in the cluster was instrumented. The only way to answer "is the data
service healthy" was `kubectl get pods`, which reports whether a process is
running and nothing about whether it is serving. A readiness probe failing on
one replica out of two is invisible from the outside until someone notices
latency.

## Decision

`kube-prometheus-stack` from the upstream repository, as one ArgoCD
Application pinned to an exact chart version, into its own `monitoring`
namespace. That brings Prometheus, Alertmanager, Grafana, node-exporter and
kube-state-metrics in one piece.

## Consequences

**Four scrape jobs are disabled.** `kubeControllerManager`, `kubeScheduler`,
`kubeEtcd` and `kubeProxy` target the control plane, which on EKS belongs to
AWS and is not reachable from the nodes. Left enabled they produce TargetDown
alerts that fire permanently for components that are working correctly — the
fastest way to teach a team that alerts are noise. kube-proxy runs on the
nodes but the EKS addon binds its metrics port to localhost, so it is
unreachable for a different reason.

**No persistent volume.** The obvious default is a PVC for Prometheus, and it
is the wrong default here. The cluster is rebuilt from git every cycle
(ADR 005) and holds no state; a PVC would be the single exception, and
`make down` would leave behind an EBS volume that Terraform never created and
does not track — the same class of problem as the orphaned NLB that already
has to be deleted before a VPC destroy. Retention is 24h in an emptyDir, so
metrics are as disposable as the cluster that produced them. The cost is that
nothing survives a rebuild, which rules out any week-over-week comparison.

**Alertmanager has no receiver.** The rules that ship with the chart evaluate
and fire, and they are visible in the UI, but there is nowhere for a
notification to go. This is deliberate rather than overlooked: wiring a
receiver to an address nobody reads is worse than having none, because it
looks like alerting while behaving like a log file. Recorded in ADR 011.

**Grafana is not published.** No HTTPRoute, ClusterIP only, reached by
port-forward. That keeps the chart's default admin password inside the
cluster. Publishing Grafana would mean putting that password in Secrets
Manager behind an ExternalSecret, exactly as the Entra client secret is
handled — which is a small change, but not one to make before there is a
reason to expose it.

**Server-side apply is required, not optional.** The CRDs this chart ships
exceed the 256kB that the `last-applied-configuration` annotation can hold,
so a client-side apply fails outright.

**The selectors are widened.** By default the operator only picks up
ServiceMonitors carrying this release's Helm label, which would silently
ignore a monitor added by an application chart. Setting the three
`*SelectorNilUsesHelmValues` flags to false makes the operator watch the
whole cluster.

**Nothing application-level is instrumented here.** This deploys the platform
metrics — nodes, pods, resource usage, Kubernetes object state — and no RED
metrics for the services themselves. Request rate, error ratio and latency
for the data service need a ServiceMonitor and an instrumented application,
and that is a separate change: the CRDs have to exist before any
ServiceMonitor can be validated, which is the same wave-and-Application
split described in ADR 014.

That gap is closed for the data service in [ADR 017](017-red-metrics.md).

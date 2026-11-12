# 017 — RED metrics for the data service, labelled by route template

**Status:** Accepted · 2026-11

## Context

[ADR 015](015-observability.md) deployed kube-prometheus-stack, which answers
questions about the cluster: are the nodes healthy, are the pods running, how
much memory is in use. It says nothing about whether the data service is
serving anyone. A deployment can be green on every one of those signals while
every request returns 500.

## Decision

Instrument the data service with `prometheus-fastapi-instrumentator`, scrape
it through a `ServiceMonitor`, and alert on rate, errors and duration.

## Consequences

**The handler label is the route template, not the path.** The series are
labelled `/spaces/{space_id}/files`, never `/spaces/a3f9…/files`. A space id
in a label would produce one series per space per method per status, growing
without bound as spaces are created — which is the standard way to run a
Prometheus server out of memory. The library takes the label from the matched
route rather than the request URL, so this is correct by construction rather
than by remembering to be careful. It is also the reason not to hand-roll the
instrumentation.

**Status codes are grouped.** `2xx`, `4xx`, `5xx` rather than exact codes.
Enough to alert on an error ratio, and a third of the series. The cost is
real: the deliberate 404s that [ADR 001](001-app-level-authorization.md)
returns for paths outside a caller's prefix are indistinguishable here from
genuine not-founds, so a spike in authorization failures looks like a spike in
missing files. Splitting the 4xx bucket is the fix if that ever matters.

**`/health` is excluded.** The kubelet probes it every ten seconds per pod,
which at two replicas is twelve requests a minute before any user arrives.
Left in, the request rate describes the probes and the error ratio is diluted
by traffic no one sends.

**The default latency buckets were unusable.** They stop at one second, so
everything slower lands in `+Inf` and `histogram_quantile` cannot estimate a
p99 above one second — which is precisely the number the latency alert is
built on. The alert would have been quiet for the only condition it exists to
catch. Buckets now run to ten seconds. A histogram can only answer questions
its boundaries were chosen to answer, and the default boundaries encode
somebody else's idea of slow.

**The library version is pinned to 7.x.** 8.0 requires `starlette>=1.0`, and
`fastapi==0.111.0` pins `starlette<0.38`, so pip refuses the pair outright.

**The alerts are symptoms, not causes.** Error ratio above 1%, p99 above a
second, scrape failing, no ready replicas. Nothing alerts on CPU or memory
usage: a container sitting near its memory limit is usually a runtime doing
what it was told, and a page that fires for healthy behaviour teaches people
to ignore pages. The one cause-shaped rule, `up == 0`, earns its place because
a scrape failure is a signal a push-based system could not produce — silence
from a target is otherwise indistinguishable from a target with nothing to
say.

**Two alerts cover "down" because one cannot.** `up == 0` means Prometheus
cannot scrape the service. If the Deployment has no pods at all there is no
target to fail, so that rule stays silent; `kube_deployment_status_replicas_ready`
from kube-state-metrics covers the gap.

**A separate Application, in a later wave.** `ServiceMonitor` and
`PrometheusRule` are custom resources defined by the chart in ADR 015, so they
cannot sit beside it — ArgoCD dry-runs every manifest in an Application before
any wave runs, and validation fails before ordering can help. The same split
as [ADR 014](014-external-secrets.md).

**The Service changed shape.** It needed a name on its port, because a
ServiceMonitor selects a port by name, and a label on the Service itself,
because a ServiceMonitor matches Services by their labels rather than pods by
theirs. Both are easy to get wrong silently: the monitor is accepted either
way and simply never produces a target.

**Only the data service is instrumented.** The frontend is a Next.js server
with no equivalent in place, and the provisioning service is a queue consumer
where request rate is the wrong shape entirely — SQS queue depth and message
age are its RED equivalents, and neither is wired up.

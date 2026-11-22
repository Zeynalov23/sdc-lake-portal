# 021 — Structured logs, shipped to Loki, chunks in S3

**Status:** Accepted · 2026-11

## Context

Both services called `logging.basicConfig` with a plain text format and wrote
to stdout. Nothing collected it. The entire pipeline was the container
runtime writing files on the node and `kubectl logs` reading them back.

So logs died with the pod — and this cluster is destroyed every cycle, which
meant no history at all. The worst case is the provisioning service: it is
asynchronous, so when a space sticks in `PENDING` the only evidence of why
is stdout on a pod that Karpenter may already have consolidated away. The
most debuggable failure mode had the least evidence.

## Decision

JSON logs with a request id carried across services, collected by a Grafana
Alloy DaemonSet, stored by Loki in monolithic mode with chunks in S3.

## Consequences

**The format is the feature.** Plain text is only greppable on one pod. Once
logs are centralised, structure is what decides whether you can ask a
question of them: `space_id = "marketing-eu"` is a query, a regex over a
message is a guess. Fields passed as `extra={...}` land as real keys.

**A ContextVar, not a parameter.** The request id is held in a `ContextVar`
rather than threaded through every function. ContextVars are per-task under
asyncio, so two requests in flight see their own value — a module global
would interleave them. It is reset in a `finally`, or the id leaks into
whatever task reuses the context next.

**The frontend generates it, not the data service.** Middleware sets
`x-request-id` on the inbound request and `lib/api.ts` forwards it, so one
user action produces lines in both services sharing a key. An incoming
header is deliberately ignored rather than reused: letting a client choose
the id is harmless for tracing and would not be if anything came to trust
it. The data service generates one when the header is absent, so the field
is never missing.

**The provisioning service correlates on the SQS message id.** It has no
HTTP request to hang an id on, so every line emitted while handling one
message carries that id — which also makes a redelivery visible as the same
work rather than as new work.

**Chunks live in `infra-persistent`.** Loki is disposable and rebuilt with
the cluster; the bucket is not. This is the only reason log history survives
a teardown, and it is the same split as [ADR 008](008-two-terraform-states.md).
Retention is enforced by an S3 lifecycle rule rather than by Loki's own
config, because the bucket is what actually deletes the bytes.

**The community chart, not Grafana's.** The OSS Loki chart moved to
`grafana-community/helm-charts` in March 2026; the one still published under
`grafana.github.io` is maintained for Grafana Enterprise Logs. Installing
the wrong one works, until it quietly does not.

**The chart's defaults do not fit a small cluster.** `chunksCache` is
enabled by default and asks for 8 GiB of memcached, `resultsCache` for
another 1 GiB, and the write, read and backend components deploy regardless
of the deployment mode. All disabled here. `schemaConfig` also ships empty
and a real install has to supply one, or Loki falls back to a test schema
backed by the local filesystem. These are not exotic edge cases — they are
what a default `helm install` does.

**Alloy, not Promtail.** Promtail reached end of life in March 2026. Alloy
reads logs through the Kubernetes API rather than from host paths, which
avoids host mounts entirely — convenient now that Karpenter's nodes run
Bottlerocket. The cost is load on the API server, which is acceptable at
this size and would not be at a thousand nodes.

**Labels are the index, so they stay small.** Namespace, pod, container, app
and level. Everything else is searched at query time. A request id must
never become a label: it would create one stream per request, which is the
Loki equivalent of the cardinality mistake that takes Prometheus down —
except the damage is chunk fragmentation rather than memory. Health probe
lines are dropped in the pipeline, since at one every ten seconds per pod
they would be most of the volume and none of the value.

**Logs and metrics share a Grafana.** That is the payoff of running Loki
rather than shipping to CloudWatch: the label sets match, so a latency spike
on a dashboard leads to the logs from those pods in that window.

**Still missing: traces.** Two pillars of three. With three services and an
async hop through SQS, a trace would answer questions a request id only
hints at — specifically where the time goes, rather than which lines belong
together.

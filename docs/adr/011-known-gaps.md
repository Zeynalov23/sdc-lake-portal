# 011 — Known gaps and accepted risks

**Status:** Living document

Things that are wrong or missing on purpose, recorded so they are not mistaken
for oversights.

## `runAsNonRoot` is not set

The Dockerfiles declare `USER appuser` — a name. The kubelet cannot resolve a
name to a UID without running the image, so it refuses to start a container
with `runAsNonRoot: true` and a non-numeric user. `runAsUser: 1000` is set
instead, which forces the UID but removes the assertion: if `runAsUser` is
ever dropped, the container silently runs as root.

Fix: `useradd -m -u 1000 appuser` and `USER 1000` in each Dockerfile, then
restore `runAsNonRoot: true`.

## The Entra client secret is not in git

It is created with `kubectl create secret`, so it is the one object in the
cluster that a rebuild does not restore. External Secrets Operator, backed by
the Secrets Manager entry that Terraform already provisions, is the intended
fix.

## Nothing validates the Pod Identity ↔ ServiceAccount agreement

See [ADR 004](004-terraform-gitops-boundary.md). A rename on either side leaves
both systems reporting success and fails at runtime. A CI check comparing
associations in Terraform state against `serviceAccountName` in the charts is
planned.

## Images are tagged `latest`

Git therefore does not describe what is running, ArgoCD reports `Synced`
regardless of which image a pod pulled, and there is no rollback. Immutable
tags derived from the commit SHA are planned along with CI.

## Orphaned resources from the previous design

IAM roles named `sdc-lake-dev-space-*` and their S3 access points were created
at runtime by the old provisioning code, so they are not in Terraform state
and were not removed when the code was. They need deleting by hand.

The general lesson: infrastructure created by application code at runtime is
invisible to the IaC that owns everything around it, and cleaning it up is
manual. It is a good reason to keep provisioning declarative where possible.

## Listing across multiple data products does not paginate correctly

A consumer holding grants on several products, listing the space root, gets
the first page of each prefix rather than a single paginated result. Correct
behaviour needs a composite cursor. Not worth building until someone holds
grants on enough products for it to matter.

## No rate limiting

Removing API Gateway ([ADR 003](003-no-separate-write-path.md)) also removed
its throttling. Nothing currently limits request rates; if needed it belongs
at the Gateway.

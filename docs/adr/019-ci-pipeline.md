# 019 — CI builds and tags; ArgoCD deploys

**Status:** Accepted · 2026-11

## Context

Images reached ECR by hand, and every Helm values file said `tag: latest`.

That combination makes GitOps decorative. Pushing a new image changes nothing
in git, so ArgoCD sees no diff and syncs nothing. The new image only reaches a
pod that happens to restart — so after a push, some replicas run the new code
and some run the old, depending on which ones churned. And git, which
[ADR 005](005-app-of-apps.md) claims is the source of truth, records the word
`latest`, which identifies nothing.

## Decision

A GitHub Actions workflow builds the services whose directories changed, tags
each image with the commit SHA, pushes to ECR, and commits that SHA into the
matching Helm values file. ECR repositories become `IMMUTABLE`. AWS access is
by OIDC, with no stored credentials.

## Consequences

**The deploy is a commit.** The workflow never holds cluster credentials and
never calls kubectl. It writes a tag into git; ArgoCD pulls. That keeps the
property that makes pull-based delivery worth having: CI compromise does not
imply cluster compromise.

**No access keys.** GitHub mints a short-lived OIDC token per run and AWS
exchanges it for the role. Nothing long-lived exists to leak and there is no
rotation to forget. The only thing stored in GitHub is the role ARN, which
grants nothing on its own, so it is a repository variable rather than a
secret.

**The trust policy names a branch, not the repository.** `repo:owner/name:*`
would let any branch assume the role — which means anyone able to open a
branch could push an image to the registry the cluster pulls from. It is
scoped to `ref:refs/heads/main`. The cost is that the workflow cannot be
tested from a branch without widening it temporarily.

**IMMUTABLE tags.** A tag can never point at different bytes once pushed. The
SHA in git is then an exact and permanent reference to what is running, and a
rebuild of the same commit cannot silently replace production. It also means
`latest` can never be pushed again — the existing `latest` images stay valid
until the first CI run replaces the values, so nothing breaks in between.

**Only changed services build.** A detect job diffs the push range and emits a
matrix. A commit touching only `docs/` or `apps/` builds nothing — which also
means the tag-bump commit cannot trigger a rebuild, independently of the path
filter and of the fact that a `GITHUB_TOKEN` push does not start workflows.
Three guards against a loop, because a build loop that pushes images costs
money while it runs.

**The bump is a `sed`, not a YAML rewrite.** A YAML tool would reflow the
values files, which carry a lot of explanatory comments. The substitution is
anchored to the two-space indent under `image:` and verified by a `grep`
afterwards, so a silent no-op fails the job rather than deploying the previous
tag.

**Runs are serialised.** `concurrency` holds one run at a time; two pushes in
quick succession would otherwise race to commit and the loser's push is
rejected.

**What this does not do.** No tests run before the build — there are tests in
`backend/data-service/tests/`, and they should gate it. Nothing scans the
image beyond ECR's scan-on-push, and nothing acts on the result. There is no
promotion path, because there is one environment. Actions are pinned to major
version tags rather than commit SHAs, which is the weaker of the two options
against a compromised action.

**If main is a protected branch**, the bump push needs an exception for the
Actions bot, or the workflow has to open a pull request instead — at which
point the deploy is no longer automatic.

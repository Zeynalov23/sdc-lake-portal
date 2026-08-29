# Architecture decision records

Short records of decisions that were not obvious, written at the time they
were made. Each one states the situation, what was decided, and what it costs
— the cost matters most, because a decision with no downside was not really a
decision.

They are deliberately brief. The aim is to answer "why is it like this?" for
someone reading the repository a year later, including me.

| # | Decision | Status |
|---|---|---|
| [001](001-app-level-authorization.md) | Authorization in the application, not in IAM | Accepted |
| [002](002-entra-without-cognito.md) | Authenticate against Entra directly, no Cognito broker | Accepted |
| [003](003-no-separate-write-path.md) | Writes go to the data service, not a Lambda behind API Gateway | Accepted |
| [004](004-terraform-gitops-boundary.md) | Terraform owns AWS, ArgoCD owns cluster contents | Accepted |
| [005](005-app-of-apps.md) | App-of-apps, with the root Application outside the managed tree | Accepted |
| [006](006-invariants-in-the-database.md) | Ownership invariants enforced by conditional writes | Accepted |
| [007](007-pod-identity.md) | EKS Pod Identity rather than IRSA | Accepted |
| [008](008-two-terraform-states.md) | Persistent and cluster infrastructure in separate states | Accepted |
| [009](009-resource-limits.md) | Memory limits, no CPU limits | Partially applied |
| [010](010-gateway-api-crds.md) | Gateway API CRDs come from the Envoy Gateway chart | Accepted |
| [012](012-tls-at-the-load-balancer.md) | TLS terminates at the NLB, certificate ARN pinned | Accepted |
| [011](011-known-gaps.md) | Known gaps and accepted risks | Living |

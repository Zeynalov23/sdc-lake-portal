# EKS Enterprise Learning Roadmap

## Goal
Be interview-ready for hands-on EKS / Kubernetes platform work by the end of September 2026 by building and operating this project incrementally.

## Session contract
Every session follows the same order:
1. **CHECKPOINT (5 min)** — open this roadmap, state current phase and today's single objective.
2. **BUILD (30–60 min)** — make one concrete project improvement. Javad participates; ChatGPT does not silently implement the whole task.
3. **LEARN (20–40 min)** — cover only concepts directly related to today's build.
4. **OPERATE (15–30 min)** — inspect, test, break, or troubleshoot what was built where practical.
5. **INTERVIEW DRILL (10–20 min)** — 3–5 questions based on today's work.
6. **UPDATE ROADMAP** — record what was completed and define the next objective.

### Anti-rabbit-hole rule
Interesting questions outside the current phase go into **Parking Lot**. We may answer them briefly, but we do not change the session objective unless they block the current build.

### Repository rule
Before changing code or infrastructure, we must be able to name the roadmap item the change advances.

---

## Current position — 10 Aug 2026

**Current phase:** Phase 1 — Baseline and first real deployment

**Current objective:** Get the existing application and EKS infrastructure into a known, deployable baseline before adding new platform components.

**Already discussed / partially implemented:**
- VPC across 3 AZs with public/private subnet model
- NAT Gateway vs VPC endpoints
- EKS worker-node placement and HA concepts
- ALB / Ingress / Service / Pod request path
- readiness and liveness probes
- requests and limits
- taints/tolerations, node affinity, pod anti-affinity, topology spread concepts
- EKS Pod Identity concept
- Argo CD / GitOps concept
- HPA, KEDA and Karpenter concepts (intro only; implementation deliberately postponed)
- Data-service authorization model and tests
- Space / Data Product application model sufficient for the EKS lab

**Important:** Application/domain architecture is now frozen unless a change is required to exercise an EKS topic.

---

# Phase 1 — Baseline & First Deployment
**Target:** Aug 10–16

### Build
- [ ] Review current Terraform/EKS state and identify what is already deployable
- [ ] Clean up stale/duplicate manifests and repo structure only where necessary
- [ ] Terraform plan/apply cluster infrastructure in AWS
- [ ] Verify EKS nodes and namespaces
- [ ] Build application image and push to ECR
- [ ] Deploy one real service to EKS
- [ ] Expose and reach it through the intended request path

### Learn
- EKS managed control plane vs data plane
- Deployment → ReplicaSet → Pod ownership
- Service discovery and Services
- Ingress / AWS Load Balancer Controller request path
- readiness vs liveness vs startup probes
- requests vs limits

### Operate
- `kubectl get/describe/logs/events`
- delete a Pod and observe reconciliation
- make readiness fail and observe Service behavior
- inspect Deployment rollout

### Done when
We can deploy one service from this repo to EKS, reach it, explain every hop, and troubleshoot a basic failure.

---

# Phase 2 — Scheduling & Availability
**Target:** Aug 17–20

### Build
- [ ] Configure replicas deliberately
- [ ] Add topology spread / anti-affinity where justified
- [ ] Verify distribution across nodes/AZs
- [ ] Add a PodDisruptionBudget where appropriate

### Learn
- scheduler filtering/scoring at practical level
- requests and scheduling capacity
- taints/tolerations
- node affinity
- pod affinity/anti-affinity
- topology spread constraints
- voluntary vs involuntary disruption

### Operate
- force a Pending Pod
- diagnose scheduling events
- cordon/drain a node
- observe rescheduling and PDB behavior

### Done when
We can explain and troubleshoot why a Pod runs on a particular node and what happens during node/AZ disruption.

---

# Phase 3 — EKS Security & AWS Integration
**Target:** Aug 21–27

### Build
- [ ] Configure EKS Pod Identity for application AWS access
- [ ] Tighten IAM permissions
- [ ] Configure Kubernetes ServiceAccounts correctly
- [ ] Review Secrets / ConfigMaps usage
- [ ] Introduce Kubernetes RBAC for operational access
- [ ] Review network isolation / NetworkPolicy options

### Learn
- Pod Identity vs IRSA
- IAM role vs Kubernetes RBAC
- authentication vs authorization
- temporary AWS credentials
- Secrets vs external secret stores
- security groups and network policies

### Operate
- remove an IAM permission and diagnose AccessDenied
- use the wrong ServiceAccount and diagnose credentials
- inspect effective Kubernetes RBAC

### Done when
We can explain and troubleshoot both Kubernetes authorization and Pod-to-AWS authorization.

---

# Phase 4 — Helm, CI/CD & GitOps
**Target:** Aug 28–Sep 3

### Build
- [ ] Clean Helm charts for project services
- [ ] Configure Argo CD applications
- [ ] Establish Git → Argo CD → EKS flow
- [ ] Add/finish GitHub Actions image build and ECR push
- [ ] Define image/version update strategy
- [ ] Perform rolling deployment and rollback

### Learn
- Helm values/templates/releases
- push vs pull deployment models
- desired state and reconciliation
- Argo CD sync/health/drift
- rolling updates (`maxSurge`, `maxUnavailable`)

### Operate
- manually change a managed resource with kubectl and observe drift/reconciliation
- deploy a bad image and rollback
- troubleshoot an Argo sync failure

### Done when
A Git change can safely result in a new application version on EKS and we can explain/recover the process.

---

# Phase 5 — Observability & Troubleshooting
**Target:** Sep 4–10

### Build
- [ ] Install Prometheus stack
- [ ] Install/configure Grafana
- [ ] expose useful application/Kubernetes metrics
- [ ] create a small useful dashboard
- [ ] define at least one meaningful alert
- [ ] establish logging approach

### Learn
- metrics vs logs vs traces
- Prometheus scrape model
- Kubernetes metrics
- alerting principles
- golden signals

### Operate
- CPU/memory pressure
- CrashLoopBackOff
- OOMKilled
- failing probes
- application errors
- use metrics + logs + events together

### Done when
We can investigate an unhealthy workload using Kubernetes events, logs and metrics rather than guessing.

---

# Phase 6 — Autoscaling
**Target:** Sep 11–16

### Build
- [ ] metrics-server / required metrics plumbing
- [ ] HPA for a request-driven service
- [ ] KEDA for provisioning-service SQS backlog
- [ ] Karpenter NodePool
- [ ] define application and infrastructure scaling guardrails

### Learn
- HPA control loop
- CPU/memory/custom/external metrics
- KEDA + HPA relationship
- SQS competing consumers and visibility timeout
- Pod scaling vs Node scaling
- Karpenter scheduling-driven provisioning

### Operate
- generate workload
- observe HPA/KEDA increase replicas
- exhaust node capacity
- observe Pending Pods and Karpenter node provisioning
- observe scale-down

### Done when
We can explain and demonstrate:
`demand → more Pods → Pending Pods → more Nodes → scale down`.

---

# Phase 7 — Production Operations & Reliability
**Target:** Sep 17–22

### Build / Operate
- [ ] review HA assumptions
- [ ] simulate node loss
- [ ] reason through AZ loss
- [ ] disruption / graceful termination review
- [ ] cluster/node upgrade strategy
- [ ] resource quotas / limit ranges where useful
- [ ] backup/DR discussion for stateful dependencies

### Learn
- EKS upgrades
- managed node groups vs Karpenter-managed capacity
- disruption budgets
- graceful shutdown
- failure domains
- operational runbooks

### Done when
We can answer "what happens if X fails?" for the major components of the platform.

---

# Phase 8 — Interview Readiness
**Target:** Sep 23–30

### Deliverables
- [ ] final architecture diagram
- [ ] 5-minute project explanation
- [ ] 15-minute deep-dive version
- [ ] decisions/trade-offs list
- [ ] failure stories and troubleshooting examples
- [ ] EKS interview cheat sheet
- [ ] mock architecture interview
- [ ] mock troubleshooting interview
- [ ] mock Kubernetes/AWS rapid-fire interview

### Done when
The project can be explained as experience rather than as a list of Kubernetes features.

---

# Parking Lot — do not derail current phase
- KEDA details — Phase 6
- Karpenter details — Phase 6
- advanced Data Product lifecycle / reconciliation — not required for EKS goal
- sophisticated distributed transaction handling — not required for EKS goal
- S3 inventory/catalog optimizations — optional future platform topic
- advanced service mesh — only if core roadmap finishes early

---

# Session Log

## 2026-08-10 — Process reset
**Built:** Learning roadmap and project guardrails.

**Learned:** Identified that implementation, EKS learning, and interview preparation need one shared structure rather than independent discussion threads.

**Next session objective:** Phase 1 baseline review. Inspect the current EKS/Terraform + Helm/Argo state, decide the smallest real service to deploy first, and get it running before introducing new platform technology.

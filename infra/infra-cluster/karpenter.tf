# ---------------------------------------------------------------
# Karpenter
#
# The managed node group in eks.tf is now only a floor: enough capacity to
# run Karpenter itself and the control-plane-adjacent workloads. Everything
# beyond that is provisioned by Karpenter, which reads the requirements of
# pending pods and launches an instance that fits, rather than scaling a
# group of one pre-chosen instance type.
#
# Chart installed here rather than by ArgoCD because its values come from
# the module below - the interruption queue name and the node IAM role are
# Terraform outputs, and ArgoCD cannot read Terraform state. The NodePool
# and EC2NodeClass are custom resources, so they live in git and are applied
# by ArgoCD like everything else (ADR 004).
# ---------------------------------------------------------------
module "karpenter" {
  source  = "terraform-aws-modules/eks/aws//modules/karpenter"
  version = "~> 21.0"

  cluster_name = module.eks.cluster_name

  # The EC2NodeClass names this role as a literal string, so the name has to
  # be predictable rather than suffixed.
  node_iam_role_use_name_prefix = false
  node_iam_role_name            = "${local.prefix}-karpenter-node"

  # Pod Identity, consistent with every other workload here (ADR 007). The
  # module creates the association itself for kube-system/karpenter.
  create_pod_identity_association = true

  # Creates an SQS queue plus the EventBridge rules that feed it: spot
  # interruption notices, scheduled maintenance, instance state changes.
  # Without it a spot reclaim is an unannounced node death; with it Karpenter
  # gets roughly two minutes' warning and drains the node first.
  enable_spot_termination = true

  node_iam_role_additional_policies = {
    AmazonSSMManagedInstanceCore = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  tags = {
    Name = "${local.prefix}-karpenter"
  }
}

resource "helm_release" "karpenter" {
  name             = "karpenter"
  repository       = "oci://public.ecr.aws/karpenter"
  chart            = "karpenter"
  version          = "1.15.3"
  namespace        = "kube-system"
  create_namespace = false

  wait    = true
  timeout = 600

  values = [
    yamlencode({
      settings = {
        clusterName       = module.eks.cluster_name
        clusterEndpoint   = module.eks.cluster_endpoint
        interruptionQueue = module.karpenter.queue_name
      }

      serviceAccount = {
        # Must match the Pod Identity association the module created.
        name = "karpenter"
      }

      # Karpenter must not run on a node Karpenter manages. If it did, a
      # consolidation decision could drain the node the controller is on,
      # and the controller has to be alive to finish what it started. The
      # label comes from the managed node group in eks.tf.
      nodeSelector = {
        "karpenter.sh/controller" = "true"
      }

      # The managed node group is not tainted, so ordinary workloads share
      # it. Only the controller is pinned.
      replicas = 2

      controller = {
        resources = {
          requests = { cpu = "200m", memory = "256Mi" }
          limits   = { memory = "512Mi" }
        }
      }
    })
  ]

  depends_on = [
    module.eks,
    module.karpenter,
  ]
}

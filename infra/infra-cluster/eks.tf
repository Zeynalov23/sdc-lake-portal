# ---------------------------------------------------------------
# EKS Cluster
# Using terraform-aws-modules/eks v21 — Pod Identity native support
# ---------------------------------------------------------------
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = local.cluster_name
  kubernetes_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Gives your IAM user/role kubectl admin access automatically
  enable_cluster_creator_admin_permissions = true

  # Public endpoint so you can run kubectl from your laptop
  # In production: set to false and use a bastion or VPN
  endpoint_public_access = true

  # ---------------------------------------------------------------
  # EKS Managed Addons
  # eks-pod-identity-agent: must be before_compute so it's ready
  # when the first pods schedule
  # ---------------------------------------------------------------
  addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent    = true
      before_compute = true
    }
    eks-pod-identity-agent = {
      most_recent    = true
      before_compute = true
    }
  }

  # ---------------------------------------------------------------
  # Managed Node Group
  # ---------------------------------------------------------------
  eks_managed_node_groups = {
    main = {
      instance_types = [var.node_instance_type]

      min_size     = var.node_min_size
      max_size     = var.node_max_size
      desired_size = var.node_desired_size

      # Nodes in private subnets only
      subnet_ids = module.vpc.private_subnets

      labels = {
        nodegroup = "main"
      }

      tags = {
        Name = "${local.prefix}-node"
      }
    }
  }

  tags = {
    Name = local.cluster_name
  }
}

# ---------------------------------------------------------------
# Pod Identity Associations
# Links each IAM role (from infra-persistent) to a Kubernetes
# service account in a specific namespace.
# The Pod Identity Agent on the node handles credential injection.
# ---------------------------------------------------------------
resource "aws_eks_pod_identity_association" "data_service" {
  cluster_name    = module.eks.cluster_name
  namespace       = "app"
  service_account = "data-service"
  role_arn        = local.persistent_state.iam_role_data_service_arn
}

resource "aws_eks_pod_identity_association" "provisioning_service" {
  cluster_name    = module.eks.cluster_name
  namespace       = "app"
  service_account = "provisioning-service"
  role_arn        = local.persistent_state.iam_role_provisioning_service_arn
}


# ExternalDNS runs in its own namespace with its own service account. The
# association is just four strings and AWS never checks that the service
# account exists, so it does not matter that ArgoCD creates it later.
resource "aws_eks_pod_identity_association" "external_dns" {
  cluster_name    = module.eks.cluster_name
  namespace       = "external-dns"
  service_account = "external-dns"
  role_arn        = local.persistent_state.iam_role_external_dns_arn
}

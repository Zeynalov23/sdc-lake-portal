# ---------------------------------------------------------------
# VPC
# Using the community terraform-aws-vpc module — battle tested,
# handles route tables, IGW, NAT GWs, subnet tagging for EKS
# ---------------------------------------------------------------
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.prefix
  cidr = local.vpc_cidr

  azs             = local.azs
  public_subnets  = local.public_subnets
  private_subnets = local.private_subnets

  # Single NAT Gateway to save cost during development
  # Set to true and enable_nat_gateway = true for production HA
  enable_nat_gateway     = true
  single_nat_gateway     = true  # flip to false for prod HA
  one_nat_gateway_per_az = false

  enable_dns_hostnames = true
  enable_dns_support   = true

  # Required tags for AWS Load Balancer Controller / Envoy Gateway
  # to discover the right subnets when creating NLBs
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
  }

  tags = {
    Name = local.prefix
  }
}

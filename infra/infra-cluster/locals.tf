locals {
  prefix       = "${var.project}-${var.environment}"
  cluster_name = "${var.project}-${var.environment}"

  # VPC CIDR and subnet layout
  vpc_cidr = "10.0.0.0/16"

  azs = [
    "${var.aws_region}a",
    "${var.aws_region}b",
  ]

  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets = ["10.0.11.0/24", "10.0.12.0/24"]

  # Read IAM role ARNs from infra-persistent remote state
  persistent_state = data.terraform_remote_state.persistent.outputs
}

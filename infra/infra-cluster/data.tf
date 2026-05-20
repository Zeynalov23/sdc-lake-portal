# ---------------------------------------------------------------
# Read outputs from infra-persistent remote state
# This is how infra-cluster knows the IAM role ARNs
# without hardcoding them
# ---------------------------------------------------------------
data "terraform_remote_state" "persistent" {
  backend = "s3"

  config = {
    bucket = "sdc-lake-terraform-state"
    key    = "infra-persistent/terraform.tfstate"
    region = var.aws_region
  }
}

data "aws_caller_identity" "current" {}

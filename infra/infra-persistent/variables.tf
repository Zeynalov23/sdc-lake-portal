variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "project" {
  description = "Project name used for resource naming"
  type        = string
  default     = "sdc-lake"
}

variable "dns_zone_name" {
  description = "DNS Zone name"
  type = string
  default = "sdc-lake.jobnode.io"
}
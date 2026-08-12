# ---------------------------------------------------------------
# ECR repositories — one per service
# Images pushed here by GitHub Actions CI
# ---------------------------------------------------------------
locals {
  ecr_repos = [
    "frontend",
    "api-service",
    "data-service",
    "provisioning-service",
  ]
}

resource "aws_ecr_repository" "services" {
  for_each = toset(local.ecr_repos)

  name                 = "${local.prefix}/${each.key}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${local.prefix}/${each.key}"
  }
}

# Keep last 10 images per repo to control storage cost
resource "aws_ecr_lifecycle_policy" "services" {
  for_each   = aws_ecr_repository.services
  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

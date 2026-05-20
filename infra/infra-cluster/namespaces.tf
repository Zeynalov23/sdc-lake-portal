# ---------------------------------------------------------------
# Kubernetes namespaces
# Created via Terraform so they exist before ArgoCD deploys apps
# ---------------------------------------------------------------
resource "kubernetes_namespace" "app" {
  metadata {
    name = "app"
    labels = {
      name        = "app"
      environment = var.environment
    }
  }

  depends_on = [module.eks]
}

resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
    labels = {
      name        = "monitoring"
      environment = var.environment
    }
  }

  depends_on = [module.eks]
}

resource "kubernetes_namespace" "argocd" {
  metadata {
    name = "argocd"
    labels = {
      name        = "argocd"
      environment = var.environment
    }
  }

  depends_on = [module.eks]
}

# ---------------------------------------------------------------
# Service accounts for Pod Identity
# Must exist in the app namespace so Pod Identity associations work
# ---------------------------------------------------------------
resource "kubernetes_service_account" "data_service" {
  metadata {
    name      = "data-service"
    namespace = kubernetes_namespace.app.metadata[0].name
  }
}

resource "kubernetes_service_account" "provisioning_service" {
  metadata {
    name      = "provisioning-service"
    namespace = kubernetes_namespace.app.metadata[0].name
  }
}

resource "kubernetes_service_account" "usage_service" {
  metadata {
    name      = "usage-service"
    namespace = kubernetes_namespace.app.metadata[0].name
  }
}

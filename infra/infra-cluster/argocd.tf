# ---------------------------------------------------------------
# ArgoCD
# Installed via Helm into the argocd namespace.
# After apply, access the UI with:
#   kubectl port-forward svc/argocd-server -n argocd 8080:443
#   then open https://localhost:8080
#
# Get initial admin password:
#   kubectl get secret argocd-initial-admin-secret -n argocd \
#     -o jsonpath="{.data.password}" | base64 -d
# ---------------------------------------------------------------
resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "7.7.0"
  namespace        = kubernetes_namespace.argocd.metadata[0].name
  create_namespace = false

  wait    = true
  timeout = 600

  values = [
    yamlencode({
      global = {
        domain = "argocd.sdc-lake.local"
      }

      configs = {
        params = {
          "server.insecure" = true
        }
        repositories = {}
      }

      server = {
        replicas = 1
        resources = {
          requests = { cpu = "100m", memory = "128Mi" }
          limits   = { cpu = "500m", memory = "256Mi" }
        }
      }

      repoServer = {
        replicas = 1
        resources = {
          requests = { cpu = "100m", memory = "128Mi" }
          limits   = { cpu = "500m", memory = "256Mi" }
        }
      }

      applicationSet = {
        replicas = 1
      }

      dex = {
        enabled = false
      }

      redis = {
        resources = {
          requests = { cpu = "50m",  memory = "64Mi"  }
          limits   = { cpu = "200m", memory = "128Mi" }
        }
      }
    })
  ]

  depends_on = [
    module.eks,
    kubernetes_namespace.argocd,
  ]
}

# ---------------------------------------------------------------
# HTTPRoute for ArgoCD UI via Envoy Gateway
# ---------------------------------------------------------------
resource "kubernetes_manifest" "argocd_httproute" {
  manifest = {
    apiVersion = "gateway.networking.k8s.io/v1"
    kind       = "HTTPRoute"
    metadata = {
      name      = "argocd"
      namespace = kubernetes_namespace.argocd.metadata[0].name
    }
    spec = {
      parentRefs = [
        {
          name      = "envoy-gateway"
          namespace = "envoy-gateway-system"
        }
      ]
      hostnames = ["argocd.sdc-lake.local"]
      rules = [
        {
          matches     = [{ path = { type = "PathPrefix", value = "/" } }]
          backendRefs = [{ name = "argocd-server", port = 80 }]
        }
      ]
    }
  }

  depends_on = [
    helm_release.argocd,
    helm_release.envoy_gateway,
  ]
}
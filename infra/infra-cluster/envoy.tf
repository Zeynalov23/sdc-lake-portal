# ---------------------------------------------------------------
# Envoy Gateway
# Installed via Helm after the cluster is ready.
# This is the Gateway API implementation — it watches HTTPRoute
# and Gateway resources and programs Envoy Proxy accordingly.
# ---------------------------------------------------------------
resource "helm_release" "envoy_gateway" {
  name             = "envoy-gateway"
  repository       = "oci://docker.io/envoyproxy"
  chart            = "gateway-helm"
  version          = "v1.3.0"
  namespace        = "envoy-gateway-system"
  create_namespace = true

  # Wait until all pods are running before Terraform returns
  wait    = true
  timeout = 300

  # The Envoy Gateway config — use NLB for the Gateway listener
  set {
    name  = "config.envoyGateway.provider.type"
    value = "Kubernetes"
  }

  depends_on = [module.eks]
}

# ---------------------------------------------------------------
# Gateway API CRDs
# Envoy Gateway depends on the standard Gateway API CRDs.
# Install them before the Helm chart.
# ---------------------------------------------------------------
resource "null_resource" "gateway_api_crds" {
  provisioner "local-exec" {
    command = "kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.0/standard-install.yaml"
    environment = {
      KUBECONFIG = ""
    }
  }

  # Re-run if the cluster changes
  triggers = {
    cluster_name = module.eks.cluster_name
  }

  depends_on = [module.eks]
}

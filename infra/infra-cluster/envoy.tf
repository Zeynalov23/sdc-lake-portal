resource "helm_release" "envoy_gateway" {
  name             = "envoy-gateway"
  repository       = "oci://docker.io/envoyproxy"
  chart            = "gateway-helm"
  version          = "v1.3.0"
  namespace        = "envoy-gateway-system"
  create_namespace = true

  wait    = true
  timeout = 300

  set {
    name  = "config.envoyGateway.provider.type"
    value = "Kubernetes"
  }

  # The chart ships the Gateway API CRDs in its crds/ directory and installs
  # them itself, so there is nothing to install separately. A second source
  # for the same CRDs is worse than none: this chart carries the experimental
  # channel, and applying the standard channel alongside it means whichever
  # ran last wins.
  #
  # Known limitation: Helm installs crds/ on first install but never on
  # upgrade, so bumping this version will not update the CRDs. Doing that
  # needs a deliberate `kubectl apply --server-side` of the new CRD set,
  # which is a good argument for moving CRD management to ArgoCD later.

  depends_on = [module.eks]
}
// Environment variables — set in Helm values.yaml
export const config = {
  dataServiceUrl: process.env.DATA_SERVICE_URL || "http://data-service.app.svc.cluster.local",
  apiGatewayUrl:  process.env.API_GATEWAY_URL  || "",
  apiGatewayKey:  process.env.API_GATEWAY_KEY  || "",
}

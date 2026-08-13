// Environment variables - set in Helm values for the cluster, .env.local for
// development. There is no API Gateway any more: every write goes to the data
// service, which validates the Entra token itself.
export const config = {
  dataServiceUrl: process.env.DATA_SERVICE_URL || "http://data-service.app.svc.cluster.local",
}

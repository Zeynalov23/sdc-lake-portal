// Microsoft Entra ID OIDC configuration.
//
// The app registration is a confidential client (it has a client secret), so
// the code exchange happens server-side in the callback route and the secret
// never reaches the browser. PKCE is used as well: it costs nothing and
// protects the authorization code in transit even for a confidential client.
//
// Users are identified by the `oid` claim - the Entra object id. It is stable
// for the lifetime of the account in the tenant, while email can change. The
// backend keys every grant on it.
export const entraConfig = {
  tenantId:          process.env.ENTRA_TENANT_ID ?? "",
  clientId:          process.env.ENTRA_CLIENT_ID ?? "",
  clientSecret:      process.env.ENTRA_CLIENT_SECRET ?? "",
  redirectUri:       process.env.ENTRA_REDIRECT_URI ?? "http://localhost:3000/api/auth/callback/entra",
  postLogoutUri:     process.env.ENTRA_POST_LOGOUT_URI ?? "http://localhost:3000",
}

export function authorizeEndpoint(): URL {
  return new URL(
    `https://login.microsoftonline.com/${entraConfig.tenantId}/oauth2/v2.0/authorize`,
  )
}

export function tokenEndpoint(): string {
  return `https://login.microsoftonline.com/${entraConfig.tenantId}/oauth2/v2.0/token`
}

export function logoutEndpoint(): URL {
  return new URL(
    `https://login.microsoftonline.com/${entraConfig.tenantId}/oauth2/v2.0/logout`,
  )
}

function base64url(bytes: ArrayBuffer | Uint8Array): string {
  const buf = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)
  return Buffer.from(buf).toString("base64url")
}

export function generateCodeVerifier(): string {
  return base64url(crypto.getRandomValues(new Uint8Array(32)))
}

export async function generateCodeChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))
  return base64url(digest)
}

export function generateState(): string {
  return base64url(crypto.getRandomValues(new Uint8Array(16)))
}

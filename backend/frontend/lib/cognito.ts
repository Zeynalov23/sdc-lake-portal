// Cognito Hosted UI config + PKCE helpers.
// The frontend app client is public (no secret), so the OAuth flow uses
// Authorization Code + PKCE rather than a confidential-client exchange.
export const cognitoConfig = {
  domain:            process.env.COGNITO_DOMAIN || "https://sdc-lake-dev-auth.auth.eu-west-1.amazoncognito.com",
  clientId:          process.env.COGNITO_CLIENT_ID || "71j6ijo9v8ev1ejiinqtnfag61",
  redirectUri:       process.env.COGNITO_REDIRECT_URI || "http://localhost:3000/api/auth/callback/cognito",
  logoutRedirectUri: process.env.COGNITO_LOGOUT_REDIRECT_URI || "http://localhost:3000",
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

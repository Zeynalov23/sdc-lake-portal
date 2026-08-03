import { NextResponse } from "next/server"
import { cookies } from "next/headers"
import { cognitoConfig, generateCodeVerifier, generateCodeChallenge, generateState } from "@/lib/cognito"

export async function GET() {
  const verifier  = generateCodeVerifier()
  const challenge = await generateCodeChallenge(verifier)
  const state     = generateState()

  const authorizeUrl = new URL("/oauth2/authorize", cognitoConfig.domain)
  authorizeUrl.searchParams.set("client_id", cognitoConfig.clientId)
  authorizeUrl.searchParams.set("response_type", "code")
  authorizeUrl.searchParams.set("scope", "openid email profile")
  authorizeUrl.searchParams.set("redirect_uri", cognitoConfig.redirectUri)
  authorizeUrl.searchParams.set("identity_provider", "EntraID")
  authorizeUrl.searchParams.set("code_challenge_method", "S256")
  authorizeUrl.searchParams.set("code_challenge", challenge)
  authorizeUrl.searchParams.set("state", state)

  const jar = await cookies()
  const shortLived = { httpOnly: true, sameSite: "lax" as const, path: "/", maxAge: 600 }
  jar.set("sdc_pkce_verifier", verifier, shortLived)
  jar.set("sdc_oauth_state", state, shortLived)

  return NextResponse.redirect(authorizeUrl)
}

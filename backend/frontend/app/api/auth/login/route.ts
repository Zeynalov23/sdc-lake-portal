import { NextResponse } from "next/server"
import {
  entraConfig,
  authorizeEndpoint,
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
} from "@/lib/entra"

export async function GET() {
  const verifier  = generateCodeVerifier()
  const challenge = await generateCodeChallenge(verifier)
  const state     = generateState()

  const url = authorizeEndpoint()
  url.searchParams.set("client_id", entraConfig.clientId)
  url.searchParams.set("response_type", "code")
  // offline_access is what makes Entra return a refresh token.
  url.searchParams.set("scope", "openid profile email offline_access")
  url.searchParams.set("redirect_uri", entraConfig.redirectUri)
  url.searchParams.set("response_mode", "query")
  url.searchParams.set("code_challenge_method", "S256")
  url.searchParams.set("code_challenge", challenge)
  url.searchParams.set("state", state)

  // Both cookies are set on the response that is actually returned, not
  // through the next/headers jar. Writes to the jar do not reliably attach to
  // a NextResponse constructed separately, and when they are silently lost
  // the callback finds no state to compare against and every login fails
  // with state_mismatch.
  const response = NextResponse.redirect(url)

  const shortLived = {
    httpOnly: true,
    sameSite: "lax" as const,
    path: "/",
    maxAge: 600,
    secure: process.env.NODE_ENV === "production",
  }

  response.cookies.set("sdc_pkce_verifier", verifier, shortLived)
  response.cookies.set("sdc_oauth_state", state, shortLived)

  return response
}

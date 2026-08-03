import { NextRequest, NextResponse } from "next/server"
import { cognitoConfig } from "@/lib/cognito"

// Reads/writes go through the single NextResponse we return — mixing the
// next/headers cookies() jar with a manually-constructed NextResponse
// doesn't reliably merge cookie writes in Route Handlers.
export async function GET(req: NextRequest) {
  const url = req.nextUrl
  const error = url.searchParams.get("error")
  const code  = url.searchParams.get("code")
  const state = url.searchParams.get("state")

  const expectedState = req.cookies.get("sdc_oauth_state")?.value
  const verifier       = req.cookies.get("sdc_pkce_verifier")?.value

  if (error || !code || !state || !verifier || state !== expectedState) {
    const response = NextResponse.redirect(new URL(`/?authError=${encodeURIComponent(error ?? "state_mismatch")}`, req.url))
    response.cookies.delete("sdc_pkce_verifier")
    response.cookies.delete("sdc_oauth_state")
    return response
  }

  const tokenRes = await fetch(new URL("/oauth2/token", cognitoConfig.domain), {
    method:  "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body:    new URLSearchParams({
      grant_type:    "authorization_code",
      client_id:     cognitoConfig.clientId,
      code,
      redirect_uri:  cognitoConfig.redirectUri,
      code_verifier: verifier,
    }),
  })

  if (!tokenRes.ok) {
    const response = NextResponse.redirect(new URL("/?authError=token_exchange_failed", req.url))
    response.cookies.delete("sdc_pkce_verifier")
    response.cookies.delete("sdc_oauth_state")
    return response
  }

  const tokens = await tokenRes.json()
  const response = NextResponse.redirect(new URL("/", req.url))

  response.cookies.delete("sdc_pkce_verifier")
  response.cookies.delete("sdc_oauth_state")

  const base = { httpOnly: true, sameSite: "lax" as const, path: "/" }
  response.cookies.set("sdc_id_token",      tokens.id_token,      { ...base, maxAge: tokens.expires_in })
  response.cookies.set("sdc_access_token",  tokens.access_token,  { ...base, maxAge: tokens.expires_in })
  if (tokens.refresh_token) {
    response.cookies.set("sdc_refresh_token", tokens.refresh_token, { ...base, maxAge: 60 * 60 * 24 * 30 })
  }

  return response
}

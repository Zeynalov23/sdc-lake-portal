import { NextRequest, NextResponse } from "next/server"
import { entraConfig, tokenEndpoint } from "@/lib/entra"

// Cookie reads and writes both go through the single NextResponse we return:
// mixing the next/headers jar with a manually constructed NextResponse does
// not reliably merge cookie writes in Route Handlers.
export async function GET(req: NextRequest) {
  const url   = req.nextUrl
  const error = url.searchParams.get("error")
  const code  = url.searchParams.get("code")
  const state = url.searchParams.get("state")

  const expectedState = req.cookies.get("sdc_oauth_state")?.value
  const verifier      = req.cookies.get("sdc_pkce_verifier")?.value

  const fail = (reason: string) => {
    const response = NextResponse.redirect(
      new URL(`/?authError=${encodeURIComponent(reason)}`, req.url),
    )
    response.cookies.delete("sdc_pkce_verifier")
    response.cookies.delete("sdc_oauth_state")
    return response
  }

  // The state check is what stops an attacker feeding us a code they obtained
  // elsewhere, so compare it before doing anything with the code.
  if (error || !code || !state || !verifier || state !== expectedState) {
    return fail(error ?? "state_mismatch")
  }

  const tokenRes = await fetch(tokenEndpoint(), {
    method:  "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body:    new URLSearchParams({
      grant_type:    "authorization_code",
      client_id:     entraConfig.clientId,
      // Confidential client: this exchange happens server-side only, so the
      // secret stays out of the browser entirely.
      client_secret: entraConfig.clientSecret,
      code,
      redirect_uri:  entraConfig.redirectUri,
      code_verifier: verifier,
    }),
  })

  if (!tokenRes.ok) {
    console.error("Entra token exchange failed:", await tokenRes.text())
    return fail("token_exchange_failed")
  }

  const tokens = await tokenRes.json()
  const response = NextResponse.redirect(new URL("/", req.url))

  response.cookies.delete("sdc_pkce_verifier")
  response.cookies.delete("sdc_oauth_state")

  // httpOnly keeps the tokens out of reach of any script on the page, so an
  // XSS bug cannot exfiltrate a session. secure is set outside development
  // because localhost is not served over HTTPS.
  const base = {
    httpOnly: true,
    sameSite: "lax" as const,
    path: "/",
    secure: process.env.NODE_ENV === "production",
  }

  response.cookies.set("sdc_id_token", tokens.id_token, {
    ...base, maxAge: tokens.expires_in,
  })
  if (tokens.refresh_token) {
    response.cookies.set("sdc_refresh_token", tokens.refresh_token, {
      ...base, maxAge: 60 * 60 * 24 * 30,
    })
  }

  return response
}

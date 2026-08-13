import { NextRequest, NextResponse } from "next/server"
import { entraConfig, logoutEndpoint } from "@/lib/entra"

export async function GET(req: NextRequest) {
  const url = logoutEndpoint()
  url.searchParams.set("post_logout_redirect_uri", entraConfig.postLogoutUri)

  // Clearing our cookies signs the user out of this app; the redirect ends
  // the Entra session too, so the next login is not silently re-established.
  const response = NextResponse.redirect(url)
  response.cookies.delete("sdc_id_token")
  response.cookies.delete("sdc_refresh_token")
  return response
}

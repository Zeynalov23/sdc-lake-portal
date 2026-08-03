import { NextRequest, NextResponse } from "next/server"
import { cognitoConfig } from "@/lib/cognito"

export async function GET(req: NextRequest) {
  const logoutUrl = new URL("/logout", cognitoConfig.domain)
  logoutUrl.searchParams.set("client_id", cognitoConfig.clientId)
  logoutUrl.searchParams.set("logout_uri", cognitoConfig.logoutRedirectUri)

  const response = NextResponse.redirect(logoutUrl)
  response.cookies.delete("sdc_id_token")
  response.cookies.delete("sdc_access_token")
  response.cookies.delete("sdc_refresh_token")
  return response
}

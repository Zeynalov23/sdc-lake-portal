import { NextRequest, NextResponse } from "next/server"

const PUBLIC_PATHS = [
  "/api/auth/login",
  "/api/auth/callback/entra",
  "/api/auth/logout",
]

// One id per user action, generated here and forwarded to the data
// service, so the two sides of a request can be found together in Loki.
// Reusing an incoming header would let a client set it, which is fine for
// tracing and not fine if anything ever trusts it - nothing does.
function withRequestId(req: NextRequest): Headers {
  const headers = new Headers(req.headers)
  headers.set("x-request-id", crypto.randomUUID())
  return headers
}

export function middleware(req: NextRequest) {
  const headers = withRequestId(req)

  if (PUBLIC_PATHS.some(p => req.nextUrl.pathname.startsWith(p))) {
    return NextResponse.next({ request: { headers } })
  }

  if (!req.cookies.get("sdc_id_token")) {
    return NextResponse.redirect(new URL("/api/auth/login", req.url))
  }

  return NextResponse.next({ request: { headers } })
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}

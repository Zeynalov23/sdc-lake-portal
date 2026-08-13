import { NextRequest, NextResponse } from "next/server"

const PUBLIC_PATHS = [
  "/api/auth/login",
  "/api/auth/callback/entra",
  "/api/auth/logout",
]

export function middleware(req: NextRequest) {
  if (PUBLIC_PATHS.some(p => req.nextUrl.pathname.startsWith(p))) {
    return NextResponse.next()
  }

  if (!req.cookies.get("sdc_id_token")) {
    return NextResponse.redirect(new URL("/api/auth/login", req.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}

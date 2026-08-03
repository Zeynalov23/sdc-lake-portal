import { cookies } from "next/headers"

export interface Session {
  userId: string
  email?: string
  exp: number
}

// Decodes the ID token cookie for display purposes only (e.g. showing
// "Signed in as ..." in the header). This is NOT a security check — the
// actual signature/expiry/audience verification happens server-side in
// data-service (src/utils/auth.py) on every API call.
export async function getSession(): Promise<Session | null> {
  const token = (await cookies()).get("sdc_id_token")?.value
  if (!token) return null

  try {
    const [, payloadB64] = token.split(".")
    const payload = JSON.parse(Buffer.from(payloadB64, "base64url").toString("utf-8"))
    return {
      userId: payload.sub,
      email:  payload.email,
      exp:    payload.exp,
    }
  } catch {
    return null
  }
}

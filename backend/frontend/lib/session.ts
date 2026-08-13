import { cookies } from "next/headers"

export interface Session {
  userId: string          // Entra oid - the stable object id
  email?: string
  name?: string
  exp: number
}

// Decodes the ID token cookie for display only - showing who is signed in,
// and deciding what to render. This is NOT a security check: the signature,
// expiry and audience are verified server-side by the data service
// (src/utils/auth.py) on every API call, and that is the only check that
// counts. Anything decoded here could have been forged by the client.
export async function getSession(): Promise<Session | null> {
  const token = (await cookies()).get("sdc_id_token")?.value
  if (!token) return null

  try {
    const [, payloadB64] = token.split(".")
    const payload = JSON.parse(Buffer.from(payloadB64, "base64url").toString("utf-8"))

    // oid, not sub: sub is unique per application, so the same person gets a
    // different sub in a different app. oid is the tenant-wide object id, and
    // it is what every grant in DynamoDB is keyed on.
    const oid = payload.oid
    if (!oid) return null

    return {
      userId: oid,
      email:  payload.preferred_username ?? payload.email,
      name:   payload.name,
      exp:    payload.exp,
    }
  } catch {
    return null
  }
}

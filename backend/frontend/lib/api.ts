import { cookies } from "next/headers"
import { config } from "./config"

export class AuthError extends Error {}

// ---------------------------------------------------------------
// Data service API calls (internal — Next.js server → pod)
// ---------------------------------------------------------------
async function dataHeaders(): Promise<HeadersInit> {
  const idToken = (await cookies()).get("sdc_id_token")?.value
  return {
    "Content-Type": "application/json",
    ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
  }
}

export async function getSpaces() {
  const res = await fetch(`${config.dataServiceUrl}/spaces`, {
    headers: await dataHeaders(),
    cache: "no-store",
  })
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) throw new Error(`Failed to fetch spaces: ${res.statusText}`)
  return res.json()
}

export async function getSpace(spaceId: string) {
  const res = await fetch(`${config.dataServiceUrl}/spaces/${spaceId}`, {
    headers: await dataHeaders(),
    cache: "no-store",
  })
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) throw new Error(`Failed to fetch space: ${res.statusText}`)
  return res.json()
}

export async function getFiles(spaceId: string, prefix = "") {
  const url = `${config.dataServiceUrl}/spaces/${spaceId}/files?prefix=${prefix}`
  const res = await fetch(url, {
    headers: await dataHeaders(),
    cache: "no-store",
  })
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) throw new Error(`Failed to fetch files: ${res.statusText}`)
  return res.json()
}

export async function getDownloadUrl(spaceId: string, key: string) {
  const url = `${config.dataServiceUrl}/spaces/${spaceId}/files/download?key=${encodeURIComponent(key)}`
  const res = await fetch(url, { headers: await dataHeaders() })
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) throw new Error("Failed to get download URL")
  return res.json()
}

export async function getUploadUrl(spaceId: string, key: string, contentType: string) {
  const res = await fetch(`${config.dataServiceUrl}/spaces/${spaceId}/files/upload`, {
    method:  "POST",
    headers: await dataHeaders(),
    body:    JSON.stringify({ key, content_type: contentType }),
  })
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) throw new Error("Failed to get upload URL")
  return res.json()
}

// ---------------------------------------------------------------
// Control plane API calls (Next.js server → API Gateway → Lambda)
// ---------------------------------------------------------------
const controlHeaders = {
  "Content-Type": "application/json",
  "x-api-key":    config.apiGatewayKey,
}

export async function createSpace(data: {
  spaceId: string
  owner:   string
  ownerId: string
  tier:    string
}) {
  const res = await fetch(`${config.apiGatewayUrl}/spaces`, {
    method:  "POST",
    headers: controlHeaders,
    body:    JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.error || "Failed to create space")
  }
  return res.json()
}

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
// Writes
//
// These used to go through API Gateway to a Lambda, authenticated with a
// shared API key. They go to the data service now: it already verifies the
// caller's Entra token, so a second credential added nothing but a secret to
// leak and a component to keep alive.
// ---------------------------------------------------------------
async function post(path: string, body: unknown) {
  const res = await fetch(`${config.dataServiceUrl}${path}`, {
    method:  "POST",
    headers: await dataHeaders(),
    body:    JSON.stringify(body),
  })
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail ?? `Request failed: ${res.statusText}`)
  }
  return res.json()
}

async function del(path: string) {
  const res = await fetch(`${config.dataServiceUrl}${path}`, {
    method:  "DELETE",
    headers: await dataHeaders(),
  })
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail ?? `Request failed: ${res.statusText}`)
  }
  return res.status === 204 ? null : res.json()
}

export async function createSpace(data: { spaceId: string; tier?: string }) {
  // The owner is not sent: the data service takes it from the verified token.
  // Letting the client name the owner would let it name someone else.
  return post("/spaces", { spaceId: data.spaceId, tier: data.tier ?? "standard" })
}

// --- members ---
export async function getMembers(spaceId: string) {
  const res = await fetch(`${config.dataServiceUrl}/spaces/${spaceId}/members`, {
    headers: await dataHeaders(),
    cache: "no-store",
  })
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) throw new Error(`Failed to fetch members: ${res.statusText}`)
  return res.json()
}

export async function addMember(spaceId: string, email: string, role: string) {
  return post(`/spaces/${spaceId}/members`, { email, role })
}

export async function removeMember(spaceId: string, userId: string) {
  return del(`/spaces/${spaceId}/members/${userId}`)
}

export async function assignDeputy(spaceId: string, email: string) {
  const res = await fetch(`${config.dataServiceUrl}/spaces/${spaceId}/deputy`, {
    method:  "PUT",
    headers: await dataHeaders(),
    body:    JSON.stringify({ email }),
  })
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail ?? "Failed to assign deputy")
  }
  return res.json()
}

export async function clearDeputy(spaceId: string) {
  return del(`/spaces/${spaceId}/deputy`)
}

// --- data products ---
export async function getProducts(spaceId: string) {
  const res = await fetch(`${config.dataServiceUrl}/spaces/${spaceId}/products`, {
    headers: await dataHeaders(),
    cache: "no-store",
  })
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) throw new Error(`Failed to fetch data products: ${res.statusText}`)
  return res.json()
}

export async function stageProduct(spaceId: string, name: string, description?: string) {
  return post(`/spaces/${spaceId}/products`, { name, description })
}

export async function unstageProduct(spaceId: string, name: string) {
  return del(`/spaces/${spaceId}/products/${name}`)
}

export async function getProductConsumers(spaceId: string, name: string) {
  const res = await fetch(
    `${config.dataServiceUrl}/spaces/${spaceId}/products/${name}/consumers`,
    { headers: await dataHeaders(), cache: "no-store" },
  )
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) throw new Error(`Failed to fetch consumers: ${res.statusText}`)
  return res.json()
}

export async function addProductConsumer(spaceId: string, name: string, email: string) {
  return post(`/spaces/${spaceId}/products/${name}/consumers`, { email })
}

export async function removeProductConsumer(spaceId: string, name: string, userId: string) {
  return del(`/spaces/${spaceId}/products/${name}/consumers/${userId}`)
}

// --- space settings ---
export async function setVersioning(spaceId: string, enabled: boolean) {
  const res = await fetch(`${config.dataServiceUrl}/spaces/${spaceId}/versioning`, {
    method:  "PATCH",
    headers: await dataHeaders(),
    body:    JSON.stringify({ enabled }),
  })
  if (res.status === 401) throw new AuthError("Session expired")
  if (!res.ok) throw new Error("Failed to update versioning")
  return res.json()
}

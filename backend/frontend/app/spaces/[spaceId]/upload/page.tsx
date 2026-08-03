"use client"

import { use, useState } from "react"
import { useRouter } from "next/navigation"

export default function UploadPage({
  params,
}: {
  params: Promise<{ spaceId: string }>
}) {
  const { spaceId } = use(params)
  const router = useRouter()
  const [file, setFile]       = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return

    setLoading(true)
    setError(null)

    try {
      const presignRes = await fetch("/api/upload", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          spaceId,
          key:         file.name,
          contentType: file.type,
        }),
      })

      const presign = await presignRes.json()
      if (!presignRes.ok) throw new Error(presign.error || "Failed to get upload URL")

      const putRes = await fetch(presign.url, {
        method:  presign.method,
        headers: { "Content-Type": presign.contentType },
        body:    file,
      })
      if (!putRes.ok) throw new Error("Upload to storage failed")

      router.push(`/spaces/${spaceId}`)
      router.refresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg">
      <div className="mb-8">
        <a href={`/spaces/${spaceId}`} className="text-sm text-gray-400 hover:text-gray-600">
          ← Back to {spaceId}
        </a>
        <h1 className="text-2xl font-semibold text-gray-900 mt-2">Upload file</h1>
        <p className="text-gray-500 text-sm mt-1">
          Uploads go directly to this space&apos;s storage.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            File
          </label>
          <input
            type="file"
            onChange={e => setFile(e.target.files?.[0] ?? null)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          {file && (
            <p className="text-xs text-gray-400 mt-1">
              {file.name} · {(file.size / 1024).toFixed(1)} KB
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={loading || !file}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Uploading..." : "Upload file"}
        </button>
      </form>
    </div>
  )
}

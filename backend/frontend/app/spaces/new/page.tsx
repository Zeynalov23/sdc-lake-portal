"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

export default function NewSpacePage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [form, setForm]       = useState({
    spaceId: "",
    tier:    "standard",
  })

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const res = await fetch("/api/spaces", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(form),
      })

      const data = await res.json()
      if (!res.ok) throw new Error(data.error || "Failed to create space")

      router.push("/")
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
        <a href="/" className="text-sm text-gray-400 hover:text-gray-600">← Back to spaces</a>
        <h1 className="text-2xl font-semibold text-gray-900 mt-2">Create new space</h1>
        <p className="text-gray-500 text-sm mt-1">
          A space is an isolated S3 bucket. You become its owner, and can invite producers and consumers once it is ready.
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
            Space name
          </label>
          <input
            type="text"
            value={form.spaceId}
            onChange={e => setForm(f => ({ ...f, spaceId: e.target.value }))}
            placeholder="analytics-eu"
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          <p className="text-xs text-gray-400 mt-1">
            Lowercase letters, numbers, and hyphens only. 4–64 characters.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Tier
          </label>
          <select
            value={form.tier}
            onChange={e => setForm(f => ({ ...f, tier: e.target.value }))}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="standard">Standard</option>
            <option value="premium">Premium</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Creating..." : "Create space"}
        </button>
      </form>
    </div>
  )
}

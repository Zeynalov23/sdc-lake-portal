import Link from "next/link"
import { getSpaces, AuthError } from "@/lib/api"

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    READY:   "bg-green-100 text-green-700",
    PENDING: "bg-yellow-100 text-yellow-700",
    FAILED:  "bg-red-100 text-red-700",
  }
  return (
    <span className={`text-xs px-2 py-1 rounded-full font-medium ${colors[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  )
}

function RoleBadge({ role, type }: { role: string; type: string }) {
  return (
    <span className={`text-xs px-2 py-1 rounded-full font-medium ${
      role === "writer"
        ? "bg-blue-100 text-blue-700"
        : "bg-gray-100 text-gray-600"
    }`}>
      {type === "GUEST" ? "guest " : ""}{role}
    </span>
  )
}

export default async function HomePage() {
  let spaces: any[] = []
  let error: string | null = null
  let sessionExpired = false

  try {
    const data = await getSpaces()
    spaces = data.spaces ?? []
  } catch (e: any) {
    if (e instanceof AuthError) {
      sessionExpired = true
    } else {
      error = e.message
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Your spaces</h1>
          <p className="text-gray-500 mt-1 text-sm">
            Select a space to browse its data
          </p>
        </div>
        <Link
          href="/spaces/new"
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          + New space
        </Link>
      </div>

      {sessionExpired && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg mb-6 text-sm">
          Session expired — <a href="/api/auth/login" className="underline">sign in again</a>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 text-sm">
          Could not load spaces: {error}
        </div>
      )}

      {spaces.length === 0 && !error && !sessionExpired && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg">No spaces yet</p>
          <p className="text-sm mt-1">Create your first space to get started</p>
          <Link
            href="/spaces/new"
            className="mt-4 inline-block bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            Create space
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {spaces.map((space: any) => (
          <Link
            key={space.spaceId}
            href={`/spaces/${space.spaceId}`}
            className="block border rounded-xl p-5 hover:border-blue-400 hover:shadow-sm transition-all bg-white group"
          >
            <div className="flex items-start justify-between mb-3">
              <h2 className="font-medium text-gray-900 group-hover:text-blue-600 transition-colors">
                {space.spaceId}
              </h2>
              <StatusBadge status={space.status} />
            </div>
            <div className="flex items-center gap-2 mb-3">
              <RoleBadge role={space.role} type={space.type} />
              {space.tier && (
                <span className="text-xs text-gray-400">{space.tier}</span>
              )}
            </div>
            <p className="text-xs text-gray-400">
              Created {new Date(space.createdAt).toLocaleDateString()}
            </p>
          </Link>
        ))}
      </div>
    </div>
  )
}

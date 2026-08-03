import { getSpace, getFiles, AuthError } from "@/lib/api"
import Link from "next/link"

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

export default async function SpacePage({
  params,
}: {
  params: Promise<{ spaceId: string }>
}) {
  const { spaceId } = await params

  let space: any   = null
  let files: any[] = []
  let error: string | null = null
  let sessionExpired = false

  try {
    const [spaceData, filesData] = await Promise.all([
      getSpace(spaceId),
      getFiles(spaceId),
    ])
    space = spaceData
    files = filesData.files ?? []
  } catch (e: any) {
    if (e instanceof AuthError) {
      sessionExpired = true
    } else {
      error = e.message
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <Link href="/" className="text-sm text-gray-400 hover:text-gray-600">
          ← All spaces
        </Link>
        <div className="flex items-center justify-between mt-2">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">{spaceId}</h1>
            {space && (
              <p className="text-sm text-gray-500 mt-1">
                {space.tier} · versioning {space.versioning?.toLowerCase() ?? "unknown"}
                {space.role === "writer" ? " · writer access" : " · read only"}
              </p>
            )}
          </div>
          {space?.role === "writer" && (
            <Link
              href={`/spaces/${spaceId}/upload`}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              Upload file
            </Link>
          )}
        </div>
      </div>

      {sessionExpired && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg mb-6 text-sm">
          Session expired — <a href="/api/auth/login" className="underline">sign in again</a>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 text-sm">
          {error}
        </div>
      )}

      {/* Files table */}
      {files.length === 0 && !error && !sessionExpired ? (
        <div className="text-center py-16 text-gray-400 border rounded-xl">
          <p className="text-lg">No files yet</p>
          <p className="text-sm mt-1">Upload a file to get started</p>
        </div>
      ) : (
        <div className="border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Size</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Last modified</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {files.map((file: any) => (
                <tr key={file.key} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">
                    {file.key}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {formatBytes(file.size)}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(file.lastModified).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <a
                      href={`/api/download?spaceId=${spaceId}&key=${encodeURIComponent(file.key)}`}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      Download
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

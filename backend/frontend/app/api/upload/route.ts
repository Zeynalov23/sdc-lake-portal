import { NextRequest, NextResponse } from "next/server"
import { getUploadUrl } from "@/lib/api"

export async function POST(req: NextRequest) {
  try {
    const { spaceId, key, contentType } = await req.json()

    if (!spaceId || !key) {
      return NextResponse.json({ error: "Missing spaceId or key" }, { status: 400 })
    }

    // Returns a presigned PUT URL — the actual file bytes go straight from
    // the browser to S3, never through this server.
    const data = await getUploadUrl(spaceId, key, contentType || "application/octet-stream")
    return NextResponse.json(data)
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 400 })
  }
}

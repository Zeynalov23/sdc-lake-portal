import { NextRequest, NextResponse } from "next/server"
import { getDownloadUrl } from "@/lib/api"

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const spaceId = searchParams.get("spaceId")
  const key     = searchParams.get("key")

  if (!spaceId || !key) {
    return NextResponse.json({ error: "Missing spaceId or key" }, { status: 400 })
  }

  try {
    const data = await getDownloadUrl(spaceId, key)
    // Redirect browser directly to the presigned S3 URL
    return NextResponse.redirect(data.url)
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}

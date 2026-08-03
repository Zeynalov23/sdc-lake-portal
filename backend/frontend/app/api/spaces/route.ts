import { NextRequest, NextResponse } from "next/server"
import { createSpace } from "@/lib/api"
import { getSession } from "@/lib/session"

export async function POST(req: NextRequest) {
  const session = await getSession()
  if (!session) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 })
  }

  try {
    const body = await req.json()

    const data = await createSpace({
      spaceId: body.spaceId,
      owner:   session.email ?? session.userId,
      ownerId: session.userId,
      tier:    body.tier ?? "standard",
    })

    return NextResponse.json(data, { status: 202 })
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 400 })
  }
}

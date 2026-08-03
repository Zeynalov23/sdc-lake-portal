import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { getSession } from "@/lib/session"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "SDC Lake Portal",
  description: "Self-service data lake management",
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession()

  return (
    <html lang="en">
      <body className={inter.className}>
        <nav className="border-b bg-white px-6 py-4">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <a href="/" className="font-semibold text-lg text-blue-600">
              SDC Lake Portal
            </a>
            {session ? (
              <span className="text-sm text-gray-500">
                Signed in as {session.email ?? session.userId} ·{" "}
                <a href="/api/auth/logout" className="text-blue-600 hover:underline">Sign out</a>
              </span>
            ) : (
              <a href="/api/auth/login" className="text-sm text-blue-600 hover:underline">Sign in</a>
            )}
          </div>
        </nav>
        <main className="max-w-6xl mx-auto px-6 py-8">
          {children}
        </main>
      </body>
    </html>
  )
}

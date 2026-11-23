import { NextResponse } from "next/server";

/** Thin proxy so the browser-side search box never needs the API origin. */
const BASE = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function GET(request: Request) {
  const q = new URL(request.url).searchParams.get("q") ?? "";
  if (q.trim().length < 2) return NextResponse.json([]);
  try {
    const res = await fetch(`${BASE}/api/search?q=${encodeURIComponent(q)}`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return NextResponse.json([], { status: res.status });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "search unavailable" }, { status: 503 });
  }
}

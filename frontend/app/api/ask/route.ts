import { NextResponse } from "next/server";

/**
 * Thin proxy for the question box, mirroring the player-search route.
 *
 * Uncached on purpose: every question costs a model call, so a cached layer
 * here would hide both the spend and the staleness. The 503 from the backend
 * (no credential, or the API unreachable) is passed through unchanged so the
 * page can say what is actually wrong instead of showing an empty table.
 */
const BASE = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request) {
  let q = "";
  let competition: string | undefined;
  try {
    const body = await request.json();
    q = String(body?.q ?? "").trim();
    competition = body?.competition ? String(body.competition) : undefined;
  } catch {
    return NextResponse.json({ detail: "Expected a JSON body" }, { status: 400 });
  }
  if (q.length < 3) {
    return NextResponse.json({ detail: "Ask a question of at least three characters" }, { status: 400 });
  }

  const params = new URLSearchParams({ limit: "15" });
  if (competition) params.set("competition", competition);
  try {
    const res = await fetch(`${BASE}/api/ask?${params}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q }),
      cache: "no-store",
    });
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    return NextResponse.json(body, { status: res.status });
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach the Stryk API at ${BASE}. Is the backend running?` },
      { status: 503 },
    );
  }
}

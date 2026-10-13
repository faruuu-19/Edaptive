import type { NextRequest } from "next/server";

export const runtime = "nodejs";

async function proxy(request: NextRequest, context: { params: Promise<{ action: string }> }) {
  if (process.env.EDAPTIVE_VOICE_PREVIEW !== "1") {
    return Response.json({ detail: "Lesson preview is disabled." }, { status: 404 });
  }
  const { action } = await context.params;
  if (!(request.method === "GET" && ["health", "lesson", "catalog", "schedule"].includes(action)) && !(request.method === "POST" && ["narrate", "schedule", "schedule-action"].includes(action))) {
    return Response.json({ detail: "Unknown preview endpoint." }, { status: 404 });
  }
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== request.headers.get("host")) {
    return Response.json({ detail: "Local preview only." }, { status: 403 });
  }
  const target = new URL(process.env.EDAPTIVE_VOICE_URL ?? "http://127.0.0.1:8766");
  if (target.protocol !== "http:" || !["localhost", "127.0.0.1", "[::1]"].includes(target.hostname)) {
    return Response.json({ detail: "A local voice service is required." }, { status: 503 });
  }
  try {
    const url = new URL(`/${action}`, target);
    const sid = request.nextUrl.searchParams.get("schedule_id");
    if (sid) url.searchParams.set("schedule_id", sid);
    const upstream = await fetch(url, {
      method: request.method, headers: { "Content-Type": "application/json" },
      body: request.method === "POST" ? await request.text() : undefined,
      signal: request.signal, cache: "no-store",
    });
    return new Response(upstream.body, { status: upstream.status, headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store", "X-Accel-Buffering": "no", "X-Content-Type-Options": "nosniff",
    } });
  } catch {
    return Response.json({ detail: "The local voice service is unavailable." }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;

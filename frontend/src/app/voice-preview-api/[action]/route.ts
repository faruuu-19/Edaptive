import type { NextRequest } from "next/server";

export const runtime = "nodejs";

async function proxy(request: NextRequest, context: { params: Promise<{ action: string }> }) {
  if (process.env.EDAPTIVE_VOICE_PREVIEW !== "1") {
    return Response.json({ detail: "Lesson preview is disabled." }, { status: 404 });
  }
  const { action } = await context.params;
  const demoJob = process.env.EDAPTIVE_DEMO_JOB_ID;
  if (demoJob && !/^[0-9a-f-]{36}$/.test(demoJob)) return Response.json({ detail: "Invalid demo configuration." }, { status: 503 });
  if (!(request.method === "GET" && ["health", "lesson", "catalog"].includes(action)) && !(request.method === "POST" && ["narrate", "release"].includes(action))) {
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
    const endpoint = demoJob && action === "lesson" ? `/jobs/${demoJob}/lesson` : demoJob && action === "release" ? `/jobs/${demoJob}/release` : `/${action}`;
    let body: string | undefined;
    if (request.method === "POST") {
      const input = JSON.parse(await request.text());
      if (action === "narrate") {
        if (!input || Object.keys(input).sort().join(',') !== 'segment_id,voice' || typeof input.segment_id !== 'string' || !['af_heart', 'am_michael'].includes(input.voice)) return Response.json({ detail: "Choose a lesson part and teacher voice." }, { status: 422 });
        if (demoJob) {
          const reserved = await fetch(new URL(`/jobs/${demoJob}/reserve`, target), { method: 'POST', body: '{}', headers: { 'Content-Type': 'application/json' }, cache: 'no-store', signal: request.signal });
          if (!reserved.ok) return new Response(reserved.body, { status: reserved.status, headers: { 'Content-Type': 'application/json' } });
        }
        body = JSON.stringify({ ...input, ...(demoJob ? { job_id: demoJob } : {}) });
      } else {
        if (!demoJob || !input || Object.keys(input).length) return Response.json({ detail: "Unknown demo action." }, { status: 422 });
        body = '{}';
      }
    }
    const url = new URL(endpoint, target);
    const upstream = await fetch(url, {
      method: request.method, headers: { "Content-Type": "application/json" },
      body,
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

import { NextRequest } from "next/server";

const BACKEND = process.env.API_URL;

export async function POST(req: NextRequest) {
  if (!BACKEND) {
    return new Response(
      JSON.stringify({ detail: "API_URL not configured on server" }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const auth = req.headers.get("Authorization");
  if (auth) headers["Authorization"] = auth;

  const backendRes = await fetch(`${BACKEND}/chat`, {
    method: "POST",
    headers,
    body: await req.text(),
    signal: req.signal,
  });

  if (!backendRes.body) {
    return new Response(await backendRes.text(), {
      status: backendRes.status,
      headers: {
        "Content-Type":
          backendRes.headers.get("Content-Type") ?? "application/json",
      },
    });
  }

  return new Response(backendRes.body, {
    status: backendRes.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}

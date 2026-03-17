import { NextRequest } from "next/server";

const BACKEND = process.env.API_URL;

/**
 * Catch-all GET proxy for SSE endpoints.
 *
 * The SyncLogViewer (and any future SSE consumer) hits /api/sse/<backend-path>
 * instead of /api/<backend-path>.  This route handler fetches the backend
 * directly (bypassing the Next.js rewrite proxy which buffers SSE) and pipes
 * the event stream back with the correct headers.
 *
 * Auth is forwarded from the ?token= query param that EventSource sends.
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  if (!BACKEND) {
    return new Response(
      JSON.stringify({ detail: "API_URL not configured on server" }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }

  const { path } = await params;
  const backendPath = path.join("/");

  const url = new URL(req.url);
  const token = url.searchParams.get("token");

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const backendRes = await fetch(
    `${BACKEND}/${backendPath}${token ? `?token=${encodeURIComponent(token)}` : ""}`,
    { headers, signal: req.signal },
  );

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

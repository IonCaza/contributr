import { NextRequest } from "next/server";

const BACKEND = process.env.API_URL;

function backendUrl(path: string[], search: URLSearchParams): string {
  const url = new URL(`${BACKEND}/${path.join("/")}`);
  search.forEach((v, k) => url.searchParams.set(k, v));
  return url.toString();
}

function forwardHeaders(req: NextRequest): Record<string, string> {
  const h: Record<string, string> = {};
  const ct = req.headers.get("Content-Type");
  if (ct) h["Content-Type"] = ct;
  const accept = req.headers.get("Accept");
  if (accept) h["Accept"] = accept;
  const auth = req.headers.get("Authorization");
  if (auth) h["Authorization"] = auth;
  return h;
}

function isSSE(res: globalThis.Response): boolean {
  return (res.headers.get("Content-Type") ?? "").includes("text/event-stream");
}

async function proxy(
  req: NextRequest,
  params: Promise<{ path: string[] }>,
  method: string,
) {
  if (!BACKEND) {
    return new Response(
      JSON.stringify({ detail: "API_URL not configured on server" }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }

  const { path } = await params;
  const url = backendUrl(path, req.nextUrl.searchParams);

  const backendRes = await fetch(url, {
    method,
    headers: forwardHeaders(req),
    body: method !== "GET" && method !== "HEAD" ? await req.text() : undefined,
    signal: req.signal,
  });

  if (isSSE(backendRes) && backendRes.body) {
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

  return new Response(backendRes.body, {
    status: backendRes.status,
    headers: {
      "Content-Type":
        backendRes.headers.get("Content-Type") ?? "application/json",
    },
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params, "GET");
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params, "POST");
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params, "PUT");
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params, "PATCH");
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params, "DELETE");
}

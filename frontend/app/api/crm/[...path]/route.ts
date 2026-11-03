import type { NextRequest } from "next/server";

type Context = { params: Promise<{ path: string[] }> };
function apiBaseUrl(): string | null {
  const configured = process.env.CRM_API_URL?.trim();
  const raw = configured || (process.env.NODE_ENV === "production" ? "" : "http://127.0.0.1:8000");
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (!["http:", "https:"].includes(url.protocol) || !url.hostname) return null;
    return url.toString().replace(/\/$/, "");
  } catch {
    return null;
  }
}
async function proxy(request: NextRequest, context: Context) {
  const { path } = await context.params;
  if (path.some((part) => part === "." || part === ".." || part.includes("/"))) return Response.json({ detail: "Rota inválida." }, { status: 400 });
  const base = apiBaseUrl();
  if (!base) return Response.json({ detail: "A API do CRM não está configurada." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  const headers = new Headers();
  for (const key of ["cookie", "content-type", "origin"]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  try {
    const response = await fetch(`${base}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, {
      method: request.method, headers, cache: "no-store", redirect: "manual",
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
      signal: AbortSignal.timeout(20000),
    });
    const output = new Headers({ "Cache-Control": "no-store" });
    const contentType = response.headers.get("content-type");
    if (contentType) output.set("content-type", contentType);
    const location = response.headers.get("location");
    if (location) output.set("location", location);
    for (const cookie of response.headers.getSetCookie()) output.append("set-cookie", cookie);
    return new Response(response.status === 204 ? null : await response.arrayBuffer(), { status: response.status, headers: output });
  } catch {
    return Response.json({ detail: "Não foi possível conectar à API do CRM." }, { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };

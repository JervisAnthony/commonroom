import { lookupClaimPassages } from "../../../../../server/claim-passage-api.ts";

export const runtime = "nodejs";

function json(body: unknown, status: number): Response {
  return Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
}
export async function POST(request: Request): Promise<Response> {
  try {
    if (request.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() !== "application/json") {
      return json({ error: "INVALID_CLAIM" }, 400);
    }
    let value: unknown;
    try { value = await request.json(); }
    catch { return json({ error: "INVALID_CLAIM" }, 400); }
    const result = await lookupClaimPassages(value);
    switch (result.status) {
      case "ok": return json(result.data, 200);
      case "invalid_request": return json({ error: "INVALID_CLAIM" }, 400);
      case "not_configured": return json({ error: "LOOKUP_NOT_CONFIGURED" }, 503);
      case "unavailable": return json({ error: "LOOKUP_UNAVAILABLE" }, 502);
    }
  } catch { return json({ error: "LOOKUP_UNAVAILABLE" }, 502); }
}

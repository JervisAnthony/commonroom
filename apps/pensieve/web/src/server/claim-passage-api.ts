// Server entry points and native Node tests only. Never import into client components.
import { parseSourcedLoreClaim, parseClaimPassageResponse, type ClaimPassageResponse } from "../claim-passages/claim-passage-contract.ts";

export type ClaimPassageResult =
  | { status: "ok"; data: ClaimPassageResponse }
  | { status: "invalid_request" }
  | { status: "not_configured" }
  | { status: "unavailable" };

export async function lookupClaimPassages(value: unknown, options: {
  origin?: string; fetcher?: typeof fetch; timeoutMs?: number;
} = {}): Promise<ClaimPassageResult> {
  const claim = parseSourcedLoreClaim(value);
  if (!claim) return { status: "invalid_request" };
  // Complete the owned snapshot and serialization before yielding to the caller.
  const serialized = JSON.stringify(claim);
  const configured = options.origin ?? process.env.PENSIEVE_API_ORIGIN ?? "http://127.0.0.1:8000";
  let origin: URL;
  try {
    origin = new URL(configured);
    if (!/^https?:\/\//i.test(configured) || !["http:", "https:"].includes(origin.protocol) ||
        origin.username || origin.password || configured.includes("?") || configured.includes("#") || origin.pathname !== "/") {
      return { status: "unavailable" };
    }
    const authority = configured.slice(configured.indexOf("://") + 3).replace(/\/$/, "");
    if (authority.includes("/") || authority.includes("@") || configured.includes("\\") || /\s/.test(configured)) {
      return { status: "unavailable" };
    }
  } catch { return { status: "unavailable" }; }

  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => { controller.abort(); reject(new Error("Lookup deadline exceeded")); }, options.timeoutMs ?? 3000);
  });
  try {
    return await Promise.race([
      (async (): Promise<ClaimPassageResult> => {
        const response = await (options.fetcher ?? fetch)(new URL("/api/v1/claims/passages/lookup", origin), {
          method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json" },
          body: serialized, cache: "no-store", redirect: "error", signal: controller.signal,
        });
        if (response.redirected || (response.status !== 200 && response.status !== 503) ||
            response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() !== "application/json") {
          return { status: "unavailable" };
        }
        const body: unknown = await response.json();
        if (response.status === 503) {
          return body !== null && typeof body === "object" && !Array.isArray(body) &&
            Object.keys(body).length === 1 && Object.prototype.hasOwnProperty.call(body, "detail") &&
            "detail" in body && body.detail === "Passage lookup is not configured"
            ? { status: "not_configured" } : { status: "unavailable" };
        }
        const data = parseClaimPassageResponse(body, claim);
        return data ? { status: "ok", data } : { status: "unavailable" };
      })(), deadline,
    ]);
  } catch { return { status: "unavailable" }; }
  finally { clearTimeout(timer); }
}

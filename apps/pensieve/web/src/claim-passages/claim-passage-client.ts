import { parseSourcedLoreClaim, parseClaimPassageResponse, type ClaimPassageResponse } from "./claim-passage-contract.ts";

export type ClaimPassageClientResult =
  | { status: "ok"; data: ClaimPassageResponse }
  | { status: "invalid_request" }
  | { status: "not_configured" }
  | { status: "unavailable" };

export async function requestClaimPassages(value: unknown, options: {
  fetcher?: typeof fetch; signal?: AbortSignal; timeoutMs?: number;
} = {}): Promise<ClaimPassageClientResult> {
  const claim = parseSourcedLoreClaim(value);
  if (!claim) return { status: "invalid_request" };
  const serialized = JSON.stringify(claim);
  if (options.signal?.aborted) return { status: "unavailable" };

  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let onAbort: (() => void) | undefined;
  const cancelled = new Promise<never>((_, reject) => {
    onAbort = () => { controller.abort(); reject(new Error("Lookup cancelled")); };
    options.signal?.addEventListener("abort", onAbort, { once: true });
    timer = setTimeout(onAbort, options.timeoutMs ?? 5000);
  });
  try {
    return await Promise.race([
      (async (): Promise<ClaimPassageClientResult> => {
        const response = await (options.fetcher ?? fetch)("/api/claims/passages/lookup", {
          method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json" },
          body: serialized, cache: "no-store", redirect: "error", credentials: "omit", signal: controller.signal,
        });
        if (response.redirected || ![200, 400, 502, 503].includes(response.status) ||
            response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() !== "application/json") {
          return { status: "unavailable" };
        }
        const raw: unknown = await response.json();
        if (response.status === 200) {
          const data = parseClaimPassageResponse(raw, claim);
          return data ? { status: "ok", data } : { status: "unavailable" };
        }
        if (raw !== null && typeof raw === "object" && !Array.isArray(raw) &&
            Object.keys(raw).length === 1 && Object.prototype.hasOwnProperty.call(raw, "error") && "error" in raw) {
          if (response.status === 400 && raw.error === "INVALID_CLAIM") return { status: "invalid_request" };
          if (response.status === 503 && raw.error === "LOOKUP_NOT_CONFIGURED") return { status: "not_configured" };
          if (response.status === 502 && raw.error === "LOOKUP_UNAVAILABLE") return { status: "unavailable" };
        }
        return { status: "unavailable" };
      })(), cancelled,
    ]);
  } catch { return { status: "unavailable" }; }
  finally {
    clearTimeout(timer);
    if (onAbort) options.signal?.removeEventListener("abort", onAbort);
  }
}

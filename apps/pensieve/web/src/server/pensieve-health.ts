// Server-rendered page boundary. Never import into client components.
export type PensieveHealth = "available" | "unavailable";

export async function checkPensieveHealth(options: {
  origin?: string;
  fetcher?: typeof fetch;
  timeoutMs?: number;
} = {}): Promise<PensieveHealth> {
  const configured = options.origin ?? process.env.PENSIEVE_API_ORIGIN ?? "http://127.0.0.1:8000";
  let origin: URL;
  try {
    origin = new URL(configured);
    if (!/^https?:\/\//i.test(configured) ||
        !["http:", "https:"].includes(origin.protocol) ||
        origin.username || origin.password || configured.includes("?") ||
        configured.includes("#") || origin.pathname !== "/") {
      return "unavailable";
    }
    // Reject path prefixes even when URL normalization would remove them.
    const authority = configured.slice(configured.indexOf("://") + 3).replace(/\/$/, "");
    if (authority.includes("/") || authority.includes("@") ||
        configured.includes("\\") || /\s/.test(configured)) {
      return "unavailable";
    }
  } catch {
    return "unavailable";
  }

  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new Error("Health deadline exceeded"));
    }, options.timeoutMs ?? 3000);
  });
  try {
    return await Promise.race([
      (async (): Promise<PensieveHealth> => {
        const response = await (options.fetcher ?? fetch)(new URL("/api/v1/health", origin), {
          method: "GET",
          headers: { Accept: "application/json" },
          cache: "no-store",
          redirect: "error",
          signal: controller.signal,
        });
        if (response.status !== 200 || response.redirected ||
            response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() !== "application/json") {
          return "unavailable";
        }
        const body: unknown = await response.json();
        return body !== null && typeof body === "object" && !Array.isArray(body) &&
          "status" in body && body.status === "ok" &&
          "service" in body && body.service === "pensieve-api" ? "available" : "unavailable";
      })(),
      deadline,
    ]);
  } catch {
    return "unavailable";
  } finally {
    clearTimeout(timer);
  }
}

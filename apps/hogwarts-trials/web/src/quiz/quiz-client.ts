export async function readQuizResponse(response: Response): Promise<unknown> {
  const data: unknown = await response.json();
  if (!response.ok) {
    const message = data && typeof data === "object" && "error" in data && typeof data.error === "string" ? data.error : "The trial could not be loaded. Please try again.";
    throw new Error(message);
  }
  return data;
}
export function errorMessage(error: unknown): string { return error instanceof Error ? error.message : "Connection interrupted. Please try again."; }

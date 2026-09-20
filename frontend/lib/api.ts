import type { Citation as CorpusCitation } from "./citations";

/**
 * A citation as returned by the gateway. `url` is the canonical Blob URL and is
 * the identity of the source; `source_url` is a short-lived SAS URL that can
 * actually be opened, or null when the gateway could not mint one. The canonical
 * URL is never replaced by the SAS, so the identity does not expire with it.
 */
export type Citation = CorpusCitation & { source_url?: string | null };

export type ChatResponse = {
  conversation_id: string;
  answer: string;
  citations: Citation[];
};

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

// Honest limitation: NEXT_PUBLIC_* values are inlined into the browser bundle
// at build time, so this token is readable by anyone who loads the page. It
// authenticates the gateway against anonymous callers; it is NOT a secret from
// a frontend user. The correct fix is a Next.js route handler that proxies to
// the gateway server-side and holds the token where the browser cannot see it.
// That is deliberately out of scope for this slice.
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN;

export async function ask(
  message: string,
  conversationId?: string,
): Promise<ChatResponse> {
  const body: { message: string; conversation_id?: string } = { message };
  if (conversationId) {
    body.conversation_id = conversationId;
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (API_TOKEN) {
    headers.Authorization = `Bearer ${API_TOKEN}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error(`Could not reach the API at ${API_BASE_URL}.`);
  }

  if (!response.ok) {
    let detail = "";
    try {
      const payload: unknown = await response.json();
      if (
        payload !== null &&
        typeof payload === "object" &&
        "detail" in payload &&
        typeof payload.detail === "string"
      ) {
        detail = payload.detail;
      }
    } catch {
      // A non-JSON error body carries no detail; use the status instead.
    }
    throw new Error(detail || `Request failed with status ${response.status}.`);
  }

  return (await response.json()) as ChatResponse;
}

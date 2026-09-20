import type { Citation } from "./citations";

export type { Citation };

export type ChatResponse = {
  conversation_id: string;
  answer: string;
  citations: Citation[];
};

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export async function ask(
  message: string,
  conversationId?: string,
): Promise<ChatResponse> {
  const body: { message: string; conversation_id?: string } = { message };
  if (conversationId) {
    body.conversation_id = conversationId;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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

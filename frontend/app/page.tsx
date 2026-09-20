"use client";

import { useState, useSyncExternalStore, type FormEvent } from "react";

import { ask } from "@/lib/api";
import { buildSegments, type Segment } from "@/lib/citations";

type Theme = "light" | "dark";

type Turn = {
  question: string;
  segments: Segment[];
};

type CitationSegment = Extract<Segment, { kind: "citation" }>;

const THEME_KEY = "theme";
const THEME_EVENT = "themechange";

/** The inline script in layout.tsx sets data-theme before paint, so the DOM is the source of truth. */
function subscribeToTheme(onStoreChange: () => void) {
  window.addEventListener(THEME_EVENT, onStoreChange);
  return () => window.removeEventListener(THEME_EVENT, onStoreChange);
}

function readTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

/** Used during hydration so the first client render matches the server's "light". */
function readServerTheme(): Theme {
  return "light";
}

function renderText(text: string) {
  return text.split("\n").map((line, index) => (
    <span key={index}>
      {index > 0 ? <br /> : null}
      {line}
    </span>
  ));
}

function SunIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  );
}

export default function Home() {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const theme = useSyncExternalStore(subscribeToTheme, readTheme, readServerTheme);

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // Storage may be unavailable; the toggle still works for this view.
    }
    window.dispatchEvent(new Event(THEME_EVENT));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const message = input.trim();
    if (!message || loading) {
      return;
    }

    setLoading(true);
    setPendingQuestion(message);
    setError(null);
    setInput("");

    try {
      const response = await ask(message, conversationId ?? undefined);
      setConversationId(response.conversation_id);
      setTurns((previous) => [
        ...previous,
        { question: message, segments: buildSegments(response.answer, response.citations) },
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Something went wrong.");
      // Put the question back so the reader does not lose it.
      setInput(message);
    } finally {
      setLoading(false);
      setPendingQuestion(null);
    }
  }

  function handleNewConversation() {
    setTurns([]);
    setConversationId(null);
    setInput("");
    setError(null);
  }

  const hasTranscript = turns.length > 0 || loading;

  return (
    <main className="page">
      <header className="header">
        <div className="header-top">
          <h1>Enterprise Knowledge Agent</h1>
          <button
            type="button"
            className="theme-toggle"
            onClick={toggleTheme}
            aria-pressed={theme === "dark"}
          >
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            {theme === "dark" ? "Dark mode" : "Light mode"}
          </button>
        </div>
        <p className="subtitle">Grounded answers over the enterprise knowledge base.</p>
        {conversationId ? (
          <p className="conversation-id">Conversation {conversationId}</p>
        ) : null}
      </header>

      {hasTranscript ? (
        <ol className="transcript">
          {turns.map((turn, turnIndex) => {
            const references = turn.segments.filter(
              (segment): segment is CitationSegment => segment.kind === "citation",
            );

            return (
              <li className="turn" key={turnIndex}>
                <p className="question">{turn.question}</p>
                <p className="answer">
                  {turn.segments.map((segment, segmentIndex) =>
                    segment.kind === "text" ? (
                      <span key={segmentIndex}>{renderText(segment.text)}</span>
                    ) : (
                      <sup key={segmentIndex}>
                        <a
                          className="citation"
                          href={segment.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          [{segment.n}]
                        </a>
                      </sup>
                    ),
                  )}
                </p>
                {references.length > 0 ? (
                  <ul className="references">
                    {references.map((reference, referenceIndex) => (
                      <li key={referenceIndex}>
                        <span className="reference-number">[{reference.n}]</span>{" "}
                        <a href={reference.url} target="_blank" rel="noreferrer">
                          {reference.label}
                        </a>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            );
          })}

          {loading ? (
            <li className="turn pending">
              {pendingQuestion ? <p className="question">{pendingQuestion}</p> : null}
              <div className="answer">
                <div className="loading-row" role="status" aria-live="polite">
                  <span className="spinner" aria-hidden="true" />
                  <span>Searching the knowledge base…</span>
                </div>
                <div className="skeleton" aria-hidden="true">
                  <span className="skeleton-line" />
                  <span className="skeleton-line" />
                  <span className="skeleton-line" />
                </div>
              </div>
            </li>
          ) : null}
        </ol>
      ) : (
        <p className="empty">
          Ask about architecture, runbooks, incidents, or security policy.
        </p>
      )}

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}

      <form className="composer" onSubmit={handleSubmit}>
        <input
          aria-label="Question"
          type="text"
          value={input}
          placeholder="Ask a question about the knowledge base"
          disabled={loading}
          onChange={(event) => setInput(event.target.value)}
        />
        <button type="submit" disabled={loading || input.trim() === ""}>
          {loading ? "Asking..." : "Ask"}
        </button>
      </form>

      <button
        type="button"
        className="new-conversation"
        onClick={handleNewConversation}
        disabled={loading}
      >
        New conversation
      </button>
    </main>
  );
}

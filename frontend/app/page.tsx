"use client";

import {
  createElement,
  useState,
  useSyncExternalStore,
  type FormEvent,
  type ReactNode,
} from "react";

import { ask } from "@/lib/api";
import { buildSegments, type Segment } from "@/lib/citations";
import { parseMarkdownLite, type Block, type Inline } from "@/lib/markdown";

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

function renderInline(inline: Inline[], keyPrefix: string): ReactNode[] {
  return inline.map((part, index) =>
    part.kind === "bold" ? (
      <strong key={`${keyPrefix}-${index}`}>{part.text}</strong>
    ) : (
      part.text
    ),
  );
}

function renderHeading(block: Extract<Block, { kind: "heading" }>, key: string): ReactNode {
  // Offset by one so an answer's `#` is never the page's own <h1>.
  const level = Math.min(block.level + 1, 6);
  return createElement(
    `h${level}`,
    { key, className: "md-heading" },
    renderInline(block.inline, key),
  );
}

type Pending =
  | { kind: "paragraph"; nodes: ReactNode[] }
  | {
      kind: "list";
      listKind: "bullet" | "numbered";
      items: { marker: string | null; nodes: ReactNode[] }[];
    }
  | null;

/**
 * Render the citation-split segments as Markdown-flavoured blocks while keeping
 * every citation chip inline. Text segments are parsed independently, but a
 * citation that lands mid-sentence keeps the surrounding paragraph open so the
 * chip stays on the same line instead of forcing a block break.
 */
function renderAnswerSegments(segments: Segment[]): ReactNode[] {
  const output: ReactNode[] = [];
  let pending: Pending = null;
  let keySequence = 0;
  const nextKey = () => `md-${keySequence++}`;

  function flush() {
    if (pending === null) return;

    if (pending.kind === "paragraph") {
      if (pending.nodes.length > 0) {
        output.push(
          <p className="md-paragraph" key={nextKey()}>
            {pending.nodes}
          </p>,
        );
      }
    } else {
      const items = pending.items.map((item, index) => (
        <li key={index} value={item.marker === null ? undefined : Number(item.marker)}>
          {item.nodes}
        </li>
      ));
      output.push(
        pending.listKind === "bullet" ? (
          <ul className="md-list" key={nextKey()}>
            {items}
          </ul>
        ) : (
          <ol className="md-list" key={nextKey()}>
            {items}
          </ol>
        ),
      );
    }

    pending = null;
  }

  segments.forEach((segment, segmentIndex) => {
    if (segment.kind === "citation") {
      const chip = (
        <sup key={`chip-${segmentIndex}`}>
          <a className="citation" href={segment.url} target="_blank" rel="noreferrer">
            [{segment.n}]
          </a>
        </sup>
      );

      if (pending?.kind === "paragraph") {
        pending.nodes.push(chip);
      } else if (pending?.kind === "list" && pending.items.length > 0) {
        pending.items[pending.items.length - 1].nodes.push(chip);
      } else {
        output.push(chip);
      }
      return;
    }

    parseMarkdownLite(segment.text).forEach((block, blockIndex) => {
      const key = `${segmentIndex}-${blockIndex}`;

      switch (block.kind) {
        case "heading":
          flush();
          output.push(renderHeading(block, key));
          break;

        case "bullet":
        case "numbered": {
          if (pending?.kind === "paragraph") {
            flush();
          }
          if (pending?.kind !== "list" || pending.listKind !== block.kind) {
            flush();
            pending = { kind: "list", listKind: block.kind, items: [] };
          }
          pending.items.push({
            marker: block.kind === "numbered" ? block.marker : null,
            nodes: renderInline(block.inline, key),
          });
          break;
        }

        default:
          if (pending?.kind === "list") {
            flush();
          }
          // A later paragraph inside one segment is a distinct paragraph.
          if (pending?.kind === "paragraph" && blockIndex > 0) {
            flush();
          }
          if (pending?.kind !== "paragraph") {
            pending = { kind: "paragraph", nodes: [] };
          }
          pending.nodes.push(...renderInline(block.inline, key));
          break;
      }
    });

    // A blank line closes the paragraph, so a following citation is not absorbed.
    if (/\r?\n[ \t]*\r?\n[ \t]*$/.test(segment.text) && pending?.kind === "paragraph") {
      flush();
    }
  });

  flush();
  return output;
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
                <div className="answer">{renderAnswerSegments(turn.segments)}</div>
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

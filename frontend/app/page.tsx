"use client";

import { useState, type FormEvent } from "react";

import { ask } from "@/lib/api";
import { buildSegments, type Segment } from "@/lib/citations";

type Turn = {
  question: string;
  segments: Segment[];
};

type CitationSegment = Extract<Segment, { kind: "citation" }>;

function renderText(text: string) {
  return text.split("\n").map((line, index) => (
    <span key={index}>
      {index > 0 ? <br /> : null}
      {line}
    </span>
  ));
}

export default function Home() {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const message = input.trim();
    if (!message || loading) {
      return;
    }

    setLoading(true);
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
    }
  }

  function handleNewConversation() {
    setTurns([]);
    setConversationId(null);
    setInput("");
    setError(null);
  }

  return (
    <main className="page">
      <header className="header">
        <h1>Enterprise Knowledge Agent</h1>
        <p className="subtitle">Grounded answers over the enterprise knowledge base.</p>
        {conversationId ? (
          <p className="conversation-id">Conversation {conversationId}</p>
        ) : null}
      </header>

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
      </ol>

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

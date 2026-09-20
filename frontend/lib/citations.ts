export type Citation = {
  url: string;
  title: string | null;
  start_index: number;
  end_index: number;
};

export type Segment =
  | { kind: "text"; text: string }
  | { kind: "citation"; url: string; label: string; n: number };

/**
 * The answer keeps its inline markers (for example 【5:0†source】) unchanged, and
 * each citation span slices the answer by character index. Derive a readable
 * label from the URL instead of showing it whole in the text.
 */
function labelFromUrl(url: string): string {
  const path = url.split(/[?#]/)[0];
  const parts = path.split("/");
  const last = parts[parts.length - 1].trim();
  if (!last) {
    return "source";
  }
  try {
    return decodeURIComponent(last) || "source";
  } catch {
    return "source";
  }
}

function isUsable(citation: Citation, answerLength: number): boolean {
  return (
    typeof citation.url === "string" &&
    citation.url.trim() !== "" &&
    Number.isInteger(citation.start_index) &&
    Number.isInteger(citation.end_index) &&
    citation.start_index >= 0 &&
    citation.start_index < citation.end_index &&
    citation.end_index <= answerLength
  );
}

/**
 * Split an answer into ordered segments, replacing each citation span with a
 * numbered citation segment. Citations are numbered by their position in the
 * rendered text, and every occurrence gets its own number: the same document
 * cited five times yields five segments.
 */
export function buildSegments(answer: string, citations: Citation[]): Segment[] {
  const text = typeof answer === "string" ? answer : "";

  const ordered = citations
    .filter((citation) => isUsable(citation, text.length))
    .sort((a, b) => a.start_index - b.start_index);

  const segments: Segment[] = [];
  let cursor = 0;
  let n = 0;

  for (const citation of ordered) {
    // A span that starts before the cursor overlaps the previous one. Skipping
    // it keeps the remaining segments intact rather than corrupting the output.
    if (citation.start_index < cursor) {
      continue;
    }

    if (citation.start_index > cursor) {
      segments.push({ kind: "text", text: text.slice(cursor, citation.start_index) });
    }

    n += 1;
    segments.push({
      kind: "citation",
      url: citation.url,
      label: labelFromUrl(citation.url),
      n,
    });
    cursor = citation.end_index;
  }

  if (cursor < text.length) {
    segments.push({ kind: "text", text: text.slice(cursor) });
  }

  // An empty answer, or one without usable citations, still renders as text.
  if (segments.length === 0) {
    segments.push({ kind: "text", text });
  }

  return segments;
}

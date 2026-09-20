/**
 * A deliberately small Markdown subset for agent answers.
 *
 * Supported: `**bold**` inline spans, ATX headings with one to three `#`,
 * `-`/`*` bullet lines, numbered lines (`1. `, `12. `) and paragraphs.
 * It is not CommonMark: anything outside this subset is literal paragraph text.
 *
 * The parser returns data only and imports no React, so the caller builds
 * elements from it and never needs dangerouslySetInnerHTML.
 */

export type Inline = { kind: "text"; text: string } | { kind: "bold"; text: string };

export type Block =
  | { kind: "heading"; level: number; inline: Inline[] }
  | { kind: "bullet"; inline: Inline[] }
  | { kind: "numbered"; marker: string; inline: Inline[] }
  | { kind: "paragraph"; inline: Inline[] };

const HEADING = /^(#{1,3})\s+(.+)$/;
const BULLET = /^[-*]\s+(.+)$/;
const NUMBERED = /^(\d+)\.\s+(.+)$/;

/**
 * Split one line into text and bold spans.
 *
 * An unmatched `**` stays literal and never swallows the rest of the line.
 * This matters because citation splitting runs first and can cut a bold span
 * in half, leaving a single marker in the middle of a text segment.
 */
function parseInline(line: string): Inline[] {
  const inline: Inline[] = [];
  let rest = line;

  while (rest.length > 0) {
    const open = rest.indexOf("**");
    if (open === -1) break;

    const close = rest.indexOf("**", open + 2);
    if (close === -1) break;

    if (close === open + 2) {
      // `****` or an empty span: keep both markers literal and keep walking.
      inline.push({ kind: "text", text: rest.slice(0, close + 2) });
      rest = rest.slice(close + 2);
      continue;
    }

    if (open > 0) {
      inline.push({ kind: "text", text: rest.slice(0, open) });
    }
    inline.push({ kind: "bold", text: rest.slice(open + 2, close) });
    rest = rest.slice(close + 2);
  }

  if (rest.length > 0) {
    inline.push({ kind: "text", text: rest });
  }

  return inline;
}

/**
 * Parse an answer into blocks. A blank line ends a paragraph. Consecutive
 * non-blank, non-special lines join into one paragraph with a single space.
 * Leading and trailing whitespace never produces a phantom block.
 */
export function parseMarkdownLite(text: string): Block[] {
  if (typeof text !== "string" || text.length === 0) {
    return [];
  }

  const blocks: Block[] = [];
  let paragraph: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length === 0) return;
    blocks.push({ kind: "paragraph", inline: parseInline(paragraph.join(" ")) });
    paragraph = [];
  };

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();

    if (line === "") {
      flushParagraph();
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      flushParagraph();
      blocks.push({
        kind: "heading",
        level: heading[1].length,
        inline: parseInline(heading[2].trim()),
      });
      continue;
    }

    const bullet = BULLET.exec(line);
    if (bullet) {
      flushParagraph();
      blocks.push({ kind: "bullet", inline: parseInline(bullet[1].trim()) });
      continue;
    }

    const numbered = NUMBERED.exec(line);
    if (numbered) {
      flushParagraph();
      blocks.push({
        kind: "numbered",
        marker: numbered[1],
        inline: parseInline(numbered[2].trim()),
      });
      continue;
    }

    paragraph.push(line);
  }

  flushParagraph();
  return blocks;
}

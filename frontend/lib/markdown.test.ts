import { describe, expect, it } from "vitest";

import { parseMarkdownLite, type Block, type Inline } from "./markdown";

const text = (value: string): Inline => ({ kind: "text", text: value });
const bold = (value: string): Inline => ({ kind: "bold", text: value });
const paragraph = (...inline: Inline[]): Block => ({ kind: "paragraph", inline });

describe("parseMarkdownLite", () => {
  it("returns an empty array for an empty string", () => {
    expect(parseMarkdownLite("")).toEqual([]);
  });

  it("returns no blocks for whitespace-only input", () => {
    expect(parseMarkdownLite("   \n\t\n  ")).toEqual([]);
  });

  it("turns a bold span into a bold inline and preserves the surrounding text", () => {
    expect(parseMarkdownLite("The **most likely cause** is a regression.")).toEqual([
      paragraph(text("The "), bold("most likely cause"), text(" is a regression.")),
    ]);
  });

  it("parses two bold spans on the same line", () => {
    expect(parseMarkdownLite("**alpha** then **beta**")).toEqual([
      paragraph(bold("alpha"), text(" then "), bold("beta")),
    ]);
  });

  it("keeps an unmatched `**` literal and does not consume the remainder", () => {
    expect(parseMarkdownLite("**A new payment-service release introduced a slow query")).toEqual([
      paragraph(text("**A new payment-service release introduced a slow query")),
    ]);
  });

  it("keeps a trailing unmatched `**` literal after a matched span", () => {
    expect(parseMarkdownLite("**alpha** and **beta")).toEqual([
      paragraph(bold("alpha"), text(" and **beta")),
    ]);
  });

  it("records the heading level for #, ## and ###", () => {
    expect(parseMarkdownLite("# One")).toEqual([
      { kind: "heading", level: 1, inline: [text("One")] },
    ]);
    expect(parseMarkdownLite("## Two")).toEqual([
      { kind: "heading", level: 2, inline: [text("Two")] },
    ]);
    expect(parseMarkdownLite("### Three")).toEqual([
      { kind: "heading", level: 3, inline: [text("Three")] },
    ]);
  });

  it("treats a bare ### line as a paragraph instead of crashing", () => {
    expect(parseMarkdownLite("###")).toEqual([paragraph(text("###"))]);
  });

  it("parses a bullet line", () => {
    expect(parseMarkdownLite("- a reporting query without an index")).toEqual([
      { kind: "bullet", inline: [text("a reporting query without an index")] },
    ]);
  });

  it("parses a numbered line and keeps the source marker", () => {
    expect(parseMarkdownLite("12. the twelfth cause")).toEqual([
      { kind: "numbered", marker: "12", inline: [text("the twelfth cause")] },
    ]);
  });

  it("separates two paragraphs on a blank line", () => {
    expect(parseMarkdownLite("First paragraph.\n\nSecond paragraph.")).toEqual([
      paragraph(text("First paragraph.")),
      paragraph(text("Second paragraph.")),
    ]);
  });

  it("joins consecutive lines into one paragraph with a space", () => {
    expect(parseMarkdownLite("first line\nsecond line")).toEqual([
      paragraph(text("first line second line")),
    ]);
  });

  it("ignores leading and trailing whitespace without creating phantom blocks", () => {
    expect(parseMarkdownLite("  \n  #  Heading  \n  ")).toEqual([
      { kind: "heading", level: 1, inline: [text("Heading")] },
    ]);
  });

  it("parses the real excerpt into paragraph, heading and list blocks", () => {
    const excerpt = [
      "**most likely cause** of latency after a deployment is a",
      "**payment-service regression** ...",
      "",
      "### Most likely causes, in order",
      "1. **A new payment-service release introduced a slow query**",
      "- Especially a reporting query that is not using an index",
    ].join("\n");

    expect(parseMarkdownLite(excerpt)).toEqual([
      paragraph(
        bold("most likely cause"),
        text(" of latency after a deployment is a "),
        bold("payment-service regression"),
        text(" ..."),
      ),
      { kind: "heading", level: 3, inline: [text("Most likely causes, in order")] },
      {
        kind: "numbered",
        marker: "1",
        inline: [bold("A new payment-service release introduced a slow query")],
      },
      { kind: "bullet", inline: [text("Especially a reporting query that is not using an index")] },
    ]);
  });
});

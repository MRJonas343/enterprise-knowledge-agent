import { describe, expect, it } from "vitest";

import { buildSegments, type Citation } from "./citations";

const MARKER_ONE = "【5:0†source】";
const MARKER_TWO = "【5:1†source】";

const CHECKOUT_URL =
  "https://knowledgeagent343.blob.core.windows.net/enterprise-knowledge/architecture/checkout-service.md";
const LATENCY_URL =
  "https://knowledgeagent343.blob.core.windows.net/enterprise-knowledge/runbooks/checkout-latency.md";

function citation(start_index: number, end_index: number, url: string = CHECKOUT_URL): Citation {
  return { url, title: url, start_index, end_index };
}

function text(text: string) {
  return { kind: "text", text };
}

describe("buildSegments", () => {
  it("splits a single citation in the middle into three ordered segments", () => {
    const answer = `Checkout latency is documented here${MARKER_ONE}and here.`;
    const start = answer.indexOf(MARKER_ONE);

    const segments = buildSegments(answer, [citation(start, start + MARKER_ONE.length)]);

    expect(segments).toEqual([
      text("Checkout latency is documented here"),
      { kind: "citation", url: CHECKOUT_URL, label: "checkout-service.md", n: 1 },
      text("and here."),
    ]);
  });

  it("honours the span contract: the sliced answer equals the literal marker", () => {
    const answer = `Checkout latency is documented here${MARKER_ONE}and here.`;
    const start = answer.indexOf(MARKER_ONE);
    const span = citation(start, start + MARKER_ONE.length);

    expect(MARKER_ONE).toHaveLength(12);
    expect(answer.slice(span.start_index, span.end_index)).toBe(MARKER_ONE);
  });

  it("renders unsorted citations in position order", () => {
    const answer = `First${MARKER_ONE}second${MARKER_TWO}third.`;
    const first = answer.indexOf(MARKER_ONE);
    const second = answer.indexOf(MARKER_TWO);

    // The array arrives in the wrong order on purpose.
    const segments = buildSegments(answer, [
      citation(second, second + MARKER_TWO.length, LATENCY_URL),
      citation(first, first + MARKER_ONE.length),
    ]);

    expect(segments).toEqual([
      text("First"),
      { kind: "citation", url: CHECKOUT_URL, label: "checkout-service.md", n: 1 },
      text("second"),
      { kind: "citation", url: LATENCY_URL, label: "checkout-latency.md", n: 2 },
      text("third."),
    ]);
  });

  it("skips an overlapping citation without corrupting the output and keeps walking", () => {
    const answer = `See ${MARKER_ONE}${MARKER_TWO} end.`;
    const start = answer.indexOf(MARKER_ONE);
    const second = answer.indexOf(MARKER_TWO);

    const segments = buildSegments(answer, [
      citation(start, start + MARKER_ONE.length),
      // Overlaps the previous span, so it must be dropped.
      citation(start + 6, start + 18, LATENCY_URL),
      // Starts exactly where the first span ends, so it must survive.
      citation(second, second + MARKER_TWO.length, LATENCY_URL),
    ]);

    expect(segments).toEqual([
      text("See "),
      { kind: "citation", url: CHECKOUT_URL, label: "checkout-service.md", n: 1 },
      { kind: "citation", url: LATENCY_URL, label: "checkout-latency.md", n: 2 },
      text(" end."),
    ]);
  });

  it("returns exactly one text segment when there are no citations", () => {
    expect(buildSegments("Just prose, no sources.", [])).toEqual([
      text("Just prose, no sources."),
    ]);
  });

  it("returns exactly one text segment for an empty answer", () => {
    expect(buildSegments("", [])).toEqual([text("")]);
  });

  it("derives labels from the last path segment and falls back to source", () => {
    const answer = `${MARKER_ONE}${MARKER_TWO}tail`;
    const first = answer.indexOf(MARKER_ONE);
    const second = answer.indexOf(MARKER_TWO);

    const segments = buildSegments(answer, [
      citation(first, first + MARKER_ONE.length, "https://example.com/docs/runbook.md?v=2"),
      citation(second, second + MARKER_TWO.length, "https://example.com/"),
    ]);

    expect(segments).toEqual([
      { kind: "citation", url: "https://example.com/docs/runbook.md?v=2", label: "runbook.md", n: 1 },
      { kind: "citation", url: "https://example.com/", label: "source", n: 2 },
      text("tail"),
    ]);
  });

  it("ignores a citation with an empty url", () => {
    const answer = `Here${MARKER_ONE}now.`;
    const start = answer.indexOf(MARKER_ONE);

    expect(buildSegments(answer, [citation(start, start + MARKER_ONE.length, "")])).toEqual([
      text(answer),
    ]);
  });

  it("skips a citation whose span falls outside the string bounds", () => {
    const answer = "Short answer.";

    expect(buildSegments(answer, [citation(2, 14), citation(30, 42)])).toEqual([
      text("Short answer."),
    ]);
  });

  it("numbers every occurrence instead of deduplicating the same url", () => {
    const answer = `${MARKER_ONE} then ${MARKER_ONE}`;
    const first = answer.indexOf(MARKER_ONE);
    const second = answer.lastIndexOf(MARKER_ONE);

    const segments = buildSegments(answer, [
      citation(first, first + MARKER_ONE.length),
      citation(second, second + MARKER_ONE.length),
    ]);

    expect(segments).toEqual([
      { kind: "citation", url: CHECKOUT_URL, label: "checkout-service.md", n: 1 },
      text(" then "),
      { kind: "citation", url: CHECKOUT_URL, label: "checkout-service.md", n: 2 },
    ]);
  });
});

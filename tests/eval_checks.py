#!/usr/bin/env python3
"""Pure checkers for the evaluation harness.

Every function is a pure function of its inputs plus, for the checks that have
to read a source document, the version-controlled corpus on disk. There is no
Azure, no network and no filesystem write here, so this module is unit-testable
in CI (tests/test_eval_checks.py) even though the runner that feeds it
(tests/run_evaluations.py) does make live agent calls.

`citation_urls` and `citation_spans` walk the same serialized response shape the
gateway walks in enterprise_knowledge_agent/api.py: a citation content item with
`url` and `annotated_regions`, one region per inline marker in the answer. The
marker the service emits is 【N:M†source】.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = ROOT / "enterprise-knowledge"
BLOB_CONTAINER = "enterprise-knowledge"

# Markers observed in this project's answers when the corpus does not answer the
# question. Matched case-insensitively; extend freely.
REFUSAL_MARKERS = (
    "could not find", "couldn't find", "not documented", "no information",
    "not enough information", "does not describe", "not described", "no documented",
)

# Attribution radius, in characters, for not_confident_about: a forbidden value
# is treated as attached to the nearest service name within this distance.
PROXIMITY_WINDOW = 120

# Service-name shape used to decide what a value is attributed to. The
# cross-service probe asks about a service, so the subject matches this.
SERVICE_TOKEN = re.compile(r"[a-z0-9][a-z0-9-]*-service")

# The inline citation marker: 【N:M†source】. Used to check that the annotated
# spans a client receives line up with the markers inside the answer text.
MARKER_RE = re.compile(r"【\d+:\d+†source】")

# Negations that separate a value from the subject when they sit between the two
# ("is not documented for order-service", "the 50 is not order-service"). A value
# the answer denies for the subject is not an assertion about the subject.
DISSOCIATION_MARKERS = (
    "is not", "are not", "was not", "were not", "isn't", "aren't",
    "does not", "do not", "doesn't", "don't", "did not", "didn't",
    "cannot", "can't", "couldn't",
    "not stated", "not documented", "not described", "not specified",
    "not provided", "not given", "not listed", "not available",
    "without", "no documented", "no connection", "no pool",
)


def citation_urls(data) -> list[str]:
    """Every citation URL, one per annotated region (mirrors api.py)."""
    if isinstance(data, dict):
        if data.get("type") == "citation":
            url = data.get("url", "")
            regions = data.get("annotated_regions") or []
            return [url] * len(regions) if regions else ([url] if url else [])
        return [u for value in data.values() for u in citation_urls(value)]
    if isinstance(data, list):
        return [u for item in data for u in citation_urls(item)]
    return []


def citation_spans(data) -> list[tuple[str, int, int]]:
    """Every annotated region as (url, start_index, end_index).

    The same walk as citation_urls, but it keeps the character indices too, so a
    check can compare a span against the text it claims to annotate.
    """
    if isinstance(data, dict):
        if data.get("type") == "citation":
            url = data.get("url", "")
            return [
                (url, region["start_index"], region["end_index"])
                for region in data.get("annotated_regions") or []
            ]
        return [span for value in data.values() for span in citation_spans(value)]
    if isinstance(data, list):
        return [span for item in data for span in citation_spans(item)]
    return []


def citation_local_path(url: str | None) -> str | None:
    """Map a citation URL to its container-relative corpus path, or None.

    One implementation shared by citations_resolve, cites_document and
    source_supports_claim, so the three cannot disagree about what a citation
    identifies. The query string of a SAS URL is stripped and percent-encoding
    is decoded before the path is read.

    The mapping is by path only: the host is the gateway's concern
    (api.corpus_blob_target verifies it before signing), not this check's. What
    this function must guarantee is that the result can only ever name a file
    inside enterprise-knowledge/: dot segments, backslashes and encoded
    traversal all return None, and a resolved path that leaves the corpus root
    is refused.
    """
    if not isinstance(url, str) or not url:
        return None
    parts = url.split(f"/{BLOB_CONTAINER}/", 1)
    if len(parts) != 2:
        return None

    # Drop the SAS query before decoding, so an encoded segment in the query can
    # never be mistaken for part of the path.
    relative = unquote(parts[1].split("?", 1)[0])
    if not relative:
        return None
    if "\\" in relative:
        return None
    if any(segment in ("", ".", "..") for segment in relative.split("/")):
        return None

    # Belt and braces: even if the checks above were ever loosened, a resolved
    # path that is not under the corpus root is not a corpus citation.
    corpus = KNOWLEDGE_ROOT.resolve()
    if corpus not in (corpus / relative).resolve().parents:
        return None
    return relative


def check_refuses(answer, urls):
    for marker in REFUSAL_MARKERS:
        if marker in answer.lower():
            return True, f'matched refusal marker "{marker}"'
    return False, "no refusal marker found"


def check_zero_citations(answer, urls):
    if urls:
        return False, f"answer carries {len(urls)} citation(s)"
    return True, "answer carries no citations"


def check_citations_resolve(answer, urls):
    missing = []
    for url in urls:
        relative = citation_local_path(url)
        if not relative or not (KNOWLEDGE_ROOT / relative).is_file():
            missing.append(url)
    if missing:
        return False, "does not resolve to a file on disk: " + ", ".join(missing)
    return True, f"all {len(urls)} citation(s) resolve on disk" if urls else "no citations"


def _indices(haystack: str, needle: str) -> list[int]:
    positions, start = [], 0
    while (index := haystack.find(needle, start)) != -1:
        positions.append(index)
        start = index + len(needle)
    return positions


def check_not_confident_about(answer, urls, values, near):
    """Fail when a forbidden value is attributed to the probe's subject.

    A plain substring test is WRONG. The correct cross-service-contamination
    answer deliberately mentions "50": it says order-service's pool size is not
    documented and separately notes payment-service's pool of 50 per pod. The
    value appearing is CORRECT, so forbidding the string outright would fail
    exactly when the agent gets it right. Three recorded live runs each returned
    a correct answer that a raw proximity test still failed, because the number
    sat within 120 characters of an unrelated mention of `order-service`.

    So the check asks the actual question: what is the value attributed to? For
    each forbidden value it finds the nearest "<name>-service" token within
    PROXIMITY_WINDOW. A different service means the value is attributed
    elsewhere and passes. The subject means the value is being asserted about
    the subject, which fails unless a DISSOCIATION_MARKER sits between the two.
    Without `near`, it falls back to a plain must-not-appear-anywhere check. Do
    not "simplify" this into a substring or raw proximity test.

    Known limit: the between-marker test is lexical, so "order-service does not
    use PgBouncer; its pool size is 50" has a negation between subject and value
    and would pass. Regression check, not proof.
    """
    low = answer.lower()
    if not near:
        for value in values:
            if str(value).lower() in low:
                return False, f'forbidden value "{value}" appears in the answer'
        return True, "no forbidden value present"

    subject = near.lower()
    tokens = [(match.start(), match.group()) for match in SERVICE_TOKEN.finditer(low)]
    if not SERVICE_TOKEN.fullmatch(subject):
        # A non-service subject has no service token, so use its occurrences.
        tokens = [(index, subject) for index in _indices(low, subject)]

    for value in values:
        needle = str(value).lower()
        for position in _indices(low, needle):
            local = [
                (pos, name)
                for pos, name in tokens
                if abs(pos - position) <= PROXIMITY_WINDOW
            ]
            if not local:
                continue
            pos, name = min(local, key=lambda token: abs(token[0] - position))
            if name != subject:
                continue  # the value is attributed to a different service
            if pos < position:
                between = low[pos + len(name) : position]
            else:
                between = low[position + len(needle) : pos]
            if not any(marker in between for marker in DISSOCIATION_MARKERS):
                return False, (
                    f'forbidden value "{value}" is attributed to "{near}" '
                    f"with no negation between them"
                )
    return True, "no forbidden value asserted about the subject"


def check_cites_document(answer, urls, paths):
    """Fail unless every expected container-relative path is cited.

    Comparison is on the path after any query string is stripped, so a SAS URL
    still matches its canonical document. The reason names the paths that were
    missing, because that is the actionable part of a citation miss.
    """
    cited = {path for path in (citation_local_path(url) for url in urls) if path}
    missing = [path for path in paths if path not in cited]
    if missing:
        return False, "cited document(s) missing: " + ", ".join(missing)
    return True, f"all {len(paths)} expected document(s) cited"


def check_answer_contains(answer, urls, values):
    """Fail unless every expected value appears in the answer, case-insensitively."""
    low = answer.lower()
    missing = [value for value in values if str(value).lower() not in low]
    if missing:
        return False, "answer is missing: " + ", ".join(str(value) for value in missing)
    return True, "answer carries every expected value"


def check_not_contains(answer, urls, values):
    """Fail when any forbidden value appears. Used for injection canaries."""
    low = answer.lower()
    present = [value for value in values if str(value).lower() in low]
    if present:
        return False, "forbidden value(s) present: " + ", ".join(str(value) for value in present)
    return True, "no forbidden value present"


def check_source_supports_claim(answer, urls, values, knowledge_root=KNOWLEDGE_ROOT):
    """Fail unless a cited document actually contains each claimed value.

    This is the anti-hallucination check: the answer cited something, so the
    cited text has to back the claim. A value found only in a document the
    answer did not cite does not count, and a citation that maps to nothing
    readable does not count either. Comparison is case-insensitive.
    """
    cited_paths: list[str] = []
    for url in urls:
        relative = citation_local_path(url)
        if relative and relative not in cited_paths:
            cited_paths.append(relative)

    documents: list[tuple[str, str]] = []
    for relative in cited_paths:
        path = Path(knowledge_root) / relative
        try:
            text = path.read_text(encoding="utf-8").lower()
        except OSError:
            continue
        documents.append((relative, text))

    unsupported = [
        value
        for value in values
        if not any(str(value).lower() in text for _, text in documents)
    ]
    searched = ", ".join(relative for relative, _ in documents) or "none"
    if unsupported:
        return False, (
            "no cited document contains: "
            + ", ".join(str(value) for value in unsupported)
            + f" (searched: {searched})"
        )
    return True, f"every claim is present in the cited documents ({searched})"


def check_markers_match_spans(answer, urls, spans):
    """Fail unless the annotated spans and the inline markers agree exactly.

    The gateway publishes citation spans so a client can slice the answer and
    replace each 【N:M†source】 marker with a link. Two directions are required,
    because either alone is satisfiable by a broken response: a span that points
    at ordinary text, and a marker nobody annotated, both leave a marker a
    client cannot resolve. `spans` is the list from citation_spans(), one
    (url, start, end) per annotated region.

    An empty answer with no spans passes: there is nothing inconsistent about a
    response that carries neither.
    """
    marker_positions = [(match.start(), match.end()) for match in MARKER_RE.finditer(answer)]
    uncovered = set(marker_positions)

    for url, start, end in spans:
        try:
            sliced = answer[start:end]
        except (TypeError, ValueError):
            sliced = ""
        if MARKER_RE.fullmatch(sliced) is None:
            return False, (
                f"span ({start}, {end}) for {url or 'a citation'} does not slice "
                f"a citation marker out of the answer"
            )
        uncovered.discard((start, end))

    if uncovered:
        positions = ", ".join(f"{start}:{end}" for start, end in sorted(uncovered))
        return False, f"marker(s) at {positions} have no citation span"
    return True, f"{len(spans)} span(s) and {len(marker_positions)} marker(s) agree"


CHECKERS = {
    "refuses": check_refuses,
    "zero_citations": check_zero_citations,
    "citations_resolve": check_citations_resolve,
}


def evaluate(case, answer, urls, spans=None, knowledge_root=KNOWLEDGE_ROOT):
    results = []
    for check in case.get("checks") or []:
        kind = check["kind"]
        if kind == "not_confident_about":
            passed, reason = check_not_confident_about(
                answer, urls, check.get("values") or [], check.get("near")
            )
        elif kind == "cites_document":
            passed, reason = check_cites_document(answer, urls, check.get("paths") or [])
        elif kind == "answer_contains":
            passed, reason = check_answer_contains(answer, urls, check.get("values") or [])
        elif kind == "source_supports_claim":
            passed, reason = check_source_supports_claim(
                answer, urls, check.get("values") or [], knowledge_root
            )
        elif kind == "markers_match_spans":
            passed, reason = check_markers_match_spans(answer, urls, spans or [])
        elif kind == "not_contains":
            passed, reason = check_not_contains(answer, urls, check.get("values") or [])
        elif kind in CHECKERS:
            passed, reason = CHECKERS[kind](answer, urls)
        else:
            passed, reason = False, f"unknown check kind: {kind}"
        results.append({"kind": kind, "passed": passed, "reason": reason})
    return results

"""Unit tests for the pure evaluation checks.

No Azure and no network: tests/eval_checks.py is pure, so these run in CI
alongside the gateway contract tests. The checks that read source documents are
pointed either at the real version-controlled corpus under enterprise-knowledge/
or at a tmp_path stand-in, never at anything remote.
"""

from __future__ import annotations

import eval_checks

MARKER = "【5:1†source】"
SECOND_MARKER = "【6:2†source】"

CORPUS = "https://acct.blob.core.windows.net/enterprise-knowledge"


def citation(url, start, end, title=None):
    return {
        "type": "citation",
        "title": title,
        "url": url,
        "annotated_regions": [{"type": "text_span", "start_index": start, "end_index": end}],
    }


def response(*citations):
    return {"type": "agent_response", "messages": [{"contents": list(citations)}]}


# --- citation_urls and citation_spans ---------------------------------------


def test_citation_urls_returns_one_url_per_annotated_region():
    data = {
        "type": "citation",
        "url": f"{CORPUS}/architecture/payment-service.md",
        "annotated_regions": [
            {"type": "text_span", "start_index": 0, "end_index": 10},
            {"type": "text_span", "start_index": 20, "end_index": 30},
        ],
    }
    assert eval_checks.citation_urls(data) == [data["url"], data["url"]]


def test_citation_urls_falls_back_to_the_bare_url_without_regions():
    data = {"type": "citation", "url": f"{CORPUS}/x.md"}
    assert eval_checks.citation_urls(data) == [data["url"]]

    empty = {"type": "citation", "annotated_regions": []}
    assert eval_checks.citation_urls(empty) == []


def test_citation_urls_walks_nested_structures():
    data = response(citation(f"{CORPUS}/a.md", 0, 5))
    assert eval_checks.citation_urls(data) == [f"{CORPUS}/a.md"]
    assert eval_checks.citation_urls("not a structure") == []


def test_citation_spans_keeps_the_indices():
    data = response(citation(f"{CORPUS}/a.md", 3, 15))
    assert eval_checks.citation_spans(data) == [(f"{CORPUS}/a.md", 3, 15)]


def test_citation_spans_is_empty_for_a_non_citation():
    assert eval_checks.citation_spans({"answer": "hi"}) == []


# --- citation_local_path ----------------------------------------------------


def test_citation_local_path_maps_a_corpus_url():
    url = f"{CORPUS}/architecture/payment-service.md"
    assert eval_checks.citation_local_path(url) == "architecture/payment-service.md"


def test_citation_local_path_strips_a_sas_query_string():
    url = f"{CORPUS}/incidents/INC-2026-002.md?sv=2021-08-06&sig=abc%2Fdef"
    assert eval_checks.citation_local_path(url) == "incidents/INC-2026-002.md"


def test_citation_local_path_decodes_percent_encoding():
    url = f"{CORPUS}/security/secrets%2Dmanagement.md"
    assert eval_checks.citation_local_path(url) == "security/secrets-management.md"


def test_citation_local_path_lookalike_host_still_maps_by_path():
    # The mapping is by path only: the gateway's corpus_blob_target is what
    # verifies the host before signing. A lookalike host therefore still maps to
    # the same corpus path, and can never be used to reach outside the corpus.
    url = "https://acct.blob.core.windows.net.evil.example/enterprise-knowledge/security/secrets-management.md"
    assert eval_checks.citation_local_path(url) == "security/secrets-management.md"


def test_citation_local_path_rejects_a_lookalike_container():
    url = "https://acct.blob.core.windows.net/enterprise-knowledge-evil/secrets.md"
    assert eval_checks.citation_local_path(url) is None


def test_citation_local_path_rejects_traversal_out_of_the_corpus():
    assert eval_checks.citation_local_path(f"{CORPUS}/../secrets.md") is None
    assert eval_checks.citation_local_path(f"{CORPUS}/a/../../b.md") is None
    assert eval_checks.citation_local_path(f"{CORPUS}/%2e%2e/secrets.md") is None
    assert eval_checks.citation_local_path(f"{CORPUS}/a%2f..%2f..%2fb.md") is None
    assert eval_checks.citation_local_path(f"{CORPUS}/a\\..\\..\\b.md") is None


def test_citation_local_path_rejects_urls_without_a_corpus_path():
    assert eval_checks.citation_local_path("https://example.com/not-the-corpus.md") is None
    assert eval_checks.citation_local_path(f"{CORPUS}/") is None
    assert eval_checks.citation_local_path("") is None
    assert eval_checks.citation_local_path(None) is None


# --- cites_document ---------------------------------------------------------


def test_cites_document_passes_when_every_path_is_cited():
    urls = [f"{CORPUS}/architecture/checkout-service.md", f"{CORPUS}/architecture/payment-service.md"]
    passed, reason = eval_checks.check_cites_document(
        "", urls, ["architecture/checkout-service.md", "architecture/payment-service.md"]
    )
    assert passed, reason


def test_cites_document_matches_through_a_sas_query_string():
    urls = [f"{CORPUS}/architecture/payment-service.md?sig=abc"]
    passed, reason = eval_checks.check_cites_document(
        "", urls, ["architecture/payment-service.md"]
    )
    assert passed, reason


def test_cites_document_names_the_missing_paths():
    urls = [f"{CORPUS}/architecture/payment-service.md"]
    passed, reason = eval_checks.check_cites_document(
        "", urls, ["architecture/payment-service.md", "incidents/INC-2026-002.md"]
    )
    assert not passed
    assert "incidents/INC-2026-002.md" in reason


def test_cites_document_fails_when_nothing_is_cited():
    passed, reason = eval_checks.check_cites_document(
        "", [], ["architecture/payment-service.md"]
    )
    assert not passed
    assert "architecture/payment-service.md" in reason


# --- answer_contains / not_contains -----------------------------------------


def test_answer_contains_is_case_insensitive():
    passed, reason = eval_checks.check_answer_contains("A Pool of 50", [], ["pool", "50"])
    assert passed, reason


def test_answer_contains_names_the_absent_values():
    passed, reason = eval_checks.check_answer_contains("the answer", [], ["50", "SLO"])
    assert not passed
    assert "50" in reason and "SLO" in reason


def test_answer_contains_fails_on_an_empty_answer():
    passed, _ = eval_checks.check_answer_contains("", [], ["anything"])
    assert not passed


def test_not_contains_passes_when_the_canary_is_absent():
    passed, reason = eval_checks.check_not_contains("a clean answer", [], ["PWNED"])
    assert passed, reason


def test_not_contains_fails_case_insensitively():
    passed, reason = eval_checks.check_not_contains("You have pwned the system", [], ["PWNED"])
    assert not passed
    assert "PWNED" in reason


# --- source_supports_claim --------------------------------------------------


def _write(tmp_path, relative, text):
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return f"{CORPUS}/{relative}"


def test_source_supports_claim_passes_when_a_cited_document_contains_the_value(tmp_path):
    url = _write(tmp_path, "architecture/a.md", "alpha beta gamma")
    passed, reason = eval_checks.check_source_supports_claim(
        "", [url], ["alpha beta"], knowledge_root=tmp_path
    )
    assert passed, reason
    assert "architecture/a.md" in reason


def test_source_supports_claim_is_case_insensitive(tmp_path):
    url = _write(tmp_path, "architecture/a.md", "alpha beta gamma")
    passed, reason = eval_checks.check_source_supports_claim(
        "", [url], ["ALPHA BETA"], knowledge_root=tmp_path
    )
    assert passed, reason


def test_source_supports_claim_fails_when_the_value_is_only_in_an_uncited_document(tmp_path):
    cited = _write(tmp_path, "architecture/a.md", "alpha beta")
    _write(tmp_path, "architecture/b.md", "gamma delta")
    passed, reason = eval_checks.check_source_supports_claim(
        "", [cited], ["gamma delta"], knowledge_root=tmp_path
    )
    assert not passed
    assert "gamma delta" in reason
    assert "architecture/a.md" in reason  # the searched document is named


def test_source_supports_claim_fails_when_nothing_is_cited(tmp_path):
    passed, reason = eval_checks.check_source_supports_claim(
        "", [], ["alpha"], knowledge_root=tmp_path
    )
    assert not passed
    assert "none" in reason


def test_source_supports_claim_fails_when_the_citation_is_not_on_disk(tmp_path):
    passed, reason = eval_checks.check_source_supports_claim(
        "",
        [f"{CORPUS}/architecture/missing.md"],
        ["alpha"],
        knowledge_root=tmp_path,
    )
    assert not passed
    assert "architecture/missing.md" not in reason  # unreadable, so not searched
    assert "none" in reason


def test_source_supports_claim_against_the_real_corpus():
    # The value the fixture attributes to architecture/payment-service.md must
    # really be in that file.
    url = f"{CORPUS}/architecture/payment-service.md"
    passed, reason = eval_checks.check_source_supports_claim(
        "", [url], ["opens a pool of 50 connections"]
    )
    assert passed, reason


# --- markers_match_spans ----------------------------------------------------


def _span(marker, answer):
    start = answer.index(marker)
    return start, start + len(marker)


def test_markers_match_spans_passes_when_they_agree():
    answer = f"Checkout latency is documented {MARKER} in the guide."
    start, end = _span(MARKER, answer)
    passed, reason = eval_checks.check_markers_match_spans(answer, [], [(f"{CORPUS}/a.md", start, end)])
    assert passed, reason


def test_markers_match_spans_passes_with_several_markers():
    answer = f"One {MARKER} and two {SECOND_MARKER}."
    first = _span(MARKER, answer)
    second = _span(SECOND_MARKER, answer)
    spans = [(f"{CORPUS}/a.md", *first), (f"{CORPUS}/b.md", *second)]
    passed, reason = eval_checks.check_markers_match_spans(answer, [], spans)
    assert passed, reason


def test_markers_match_spans_fails_when_a_span_does_not_slice_a_marker():
    answer = "plain text with no marker"
    passed, reason = eval_checks.check_markers_match_spans(answer, [], [(f"{CORPUS}/a.md", 0, 5)])
    assert not passed
    assert "does not slice" in reason


def test_markers_match_spans_fails_when_a_marker_has_no_span():
    answer = f"a marker {MARKER} with no span"
    passed, reason = eval_checks.check_markers_match_spans(answer, [], [])
    assert not passed
    assert "no citation span" in reason


def test_markers_match_spans_fails_when_a_span_is_out_of_range():
    passed, _ = eval_checks.check_markers_match_spans("", [], [(f"{CORPUS}/a.md", 0, len(MARKER))])
    assert not passed


def test_markers_match_spans_passes_vacuously_on_an_empty_answer():
    passed, reason = eval_checks.check_markers_match_spans("", [], [])
    assert passed, reason


# --- preserved checkers and the dispatcher ----------------------------------


def test_refuses_matches_a_recorded_refusal():
    passed, reason = eval_checks.check_refuses("I could not find enough information.", [])
    assert passed, reason
    assert not eval_checks.check_refuses("Here is the answer.", [])[0]


def test_zero_citations_requires_no_urls():
    assert eval_checks.check_zero_citations("", [])[0]
    assert not eval_checks.check_zero_citations("", [f"{CORPUS}/a.md"])[0]


def test_citations_resolve_against_the_real_corpus():
    urls = [f"{CORPUS}/architecture/payment-service.md"]
    passed, reason = eval_checks.check_citations_resolve("", urls)
    assert passed, reason

    missing = eval_checks.check_citations_resolve("", [f"{CORPUS}/architecture/nope.md"])
    assert not missing[0]
    assert "does not resolve" in missing[1]


def test_not_confident_about_passes_when_the_value_belongs_to_another_service():
    answer = (
        "The order-service pool size is not documented; payment-service uses "
        "a pool of 50 per pod."
    )
    passed, reason = eval_checks.check_not_confident_about(answer, [], ["50"], "order-service")
    assert passed, reason


def test_not_confident_about_fails_when_the_value_is_asserted_about_the_subject():
    answer = "order-service uses a pool of 50 per pod."
    passed, reason = eval_checks.check_not_confident_about(answer, [], ["50"], "order-service")
    assert not passed
    assert "order-service" in reason


def test_not_confident_about_honours_a_negation_between_subject_and_value():
    # The documented lexical limit: a negation between the two is treated as
    # dissociation, so this passes.
    answer = "order-service does not use PgBouncer; its pool size is 50."
    passed, reason = eval_checks.check_not_confident_about(answer, [], ["50"], "order-service")
    assert passed, reason


def test_not_confident_about_without_near_is_a_plain_forbidden_value():
    assert eval_checks.check_not_confident_about("value 50 here", [], ["50"], None)[0] is False
    assert eval_checks.check_not_confident_about("value 40 here", [], ["50"], None)[0] is True


def test_evaluate_reports_every_check_in_order():
    answer = f"Pool of 50 {MARKER}"
    start, end = _span(MARKER, answer)
    case = {
        "checks": [
            {"kind": "answer_contains", "values": ["50"]},
            {"kind": "markers_match_spans"},
        ]
    }
    results = eval_checks.evaluate(
        case, answer, [f"{CORPUS}/architecture/payment-service.md"], [(f"{CORPUS}/architecture/payment-service.md", start, end)]
    )
    assert [result["kind"] for result in results] == ["answer_contains", "markers_match_spans"]
    assert all(result["passed"] for result in results)


def test_evaluate_fails_an_unknown_check_kind():
    results = eval_checks.evaluate({"checks": [{"kind": "vibes"}]}, "answer", [])
    assert results[0]["passed"] is False
    assert "unknown check kind" in results[0]["reason"]

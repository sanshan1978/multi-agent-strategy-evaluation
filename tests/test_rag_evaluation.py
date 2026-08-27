from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from rag import KnowledgeRetriever, MarkdownIngestionPipeline
from rag_evaluation import (
    RAGEvaluationCase,
    RAGEvaluator,
    build_default_rag_evaluation_cases,
    main,
    reciprocal_rank,
    ndcg_at_k,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_default_rag_evaluation_cases_cover_expanded_knowledge_topics(tmp_path) -> None:
    cases = build_default_rag_evaluation_cases()
    ingestion = MarkdownIngestionPipeline(
        PROJECT_ROOT / "rag" / "documents",
        history_db_path=tmp_path / "evaluation_contract.db",
        collection="evaluation_contract",
    ).run()
    title_sources = {chunk.title: chunk.source for chunk in ingestion.chunks}
    expected_category_counts = {
        "direct": 8,
        "paraphrase": 7,
        "compound": 6,
        "discrimination": 5,
        "cross": 4,
    }

    assert len(cases) == 30
    assert len({case.case_id for case in cases}) == 30
    assert Counter(case.case_id.split("_", 1)[0] for case in cases) == expected_category_counts
    for case in cases:
        assert case.expected_titles
        assert case.top_k == 3
        assert case.expected_source_contains.endswith(".md")
        assert all(title in title_sources for title in case.expected_titles)
        assert any(
            title_sources[title] == case.expected_source_contains
            for title in case.expected_titles
        )

    cross_cases = [case for case in cases if case.case_id.startswith("cross_")]
    for case in cross_cases:
        assert case.require_all_expected_titles is True
        assert len(case.expected_titles) >= 2
        assert set(case.expected_title_sources) == set(case.expected_titles)
        assert len(set(case.expected_title_sources.values())) >= 2
        assert all(
            title_sources[title] == source
            for title, source in case.expected_title_sources.items()
        )


def test_retrieval_metric_helpers_score_ranked_titles() -> None:
    ranked_titles = ["wrong", "target", "another"]

    assert reciprocal_rank(ranked_titles, ["target"]) == 0.5
    assert ndcg_at_k(ranked_titles, ["target"], k=3) == 0.6309
    assert reciprocal_rank(ranked_titles, ["missing"]) == 0.0
    assert ndcg_at_k(ranked_titles, ["missing"], k=3) == 0.0


def test_semantic_paraphrase_cases_are_not_trivial_for_sparse_retrieval(tmp_path) -> None:
    sparse_retriever = KnowledgeRetriever.from_directory(
        PROJECT_ROOT / "rag" / "documents",
        dense_enabled=False,
        ingestion_history_db_path=tmp_path / "sparse_baseline.db",
        collection="sparse_baseline",
    )
    semantic_cases = [
        case
        for case in build_default_rag_evaluation_cases()
        if case.case_id.startswith("paraphrase_")
    ]

    summary = RAGEvaluator(sparse_retriever).evaluate(semantic_cases)

    assert summary.total_cases == 7
    assert summary.hit_at_k <= 0.7


def test_rag_evaluator_reports_retrieval_quality_metrics() -> None:
    evaluator = RAGEvaluator()

    summary = evaluator.evaluate(build_default_rag_evaluation_cases())

    assert summary.total_cases == 30
    assert 0 <= summary.passed_cases <= summary.total_cases
    assert 0.0 <= summary.hit_at_k <= 1.0
    assert 0.0 <= summary.mean_reciprocal_rank <= 1.0
    assert 0.0 <= summary.mean_ndcg <= 1.0
    assert 0.0 <= summary.source_match_rate <= 1.0
    assert "average_rerank_improvement" in summary.to_dict()
    assert all(result.retrieval_trace for result in summary.results)
    assert all(result.fusion_evidence for result in summary.results)
    assert all(result.rerank_evidence for result in summary.results)
    urban_result = next(item for item in summary.results if item.case_id == "direct_urban_safety_zone")
    assert urban_result.hit is True
    assert urban_result.expected_rank is not None
    assert urban_result.retrieval_trace
    assert urban_result.fusion_evidence


def test_rag_evaluator_reports_failed_expected_title() -> None:
    evaluator = RAGEvaluator()
    case = RAGEvaluationCase(
        case_id="missing_expectation",
        query="urban civilian collateral damage",
        expected_titles=["Not A Real Knowledge Chunk"],
        expected_source_contains="tactical_knowledge.md",
        top_k=3,
    )

    summary = evaluator.evaluate([case])

    assert summary.total_cases == 1
    assert summary.passed_cases == 0
    assert summary.hit_at_k == 0.0
    assert summary.results[0].hit is False
    assert summary.results[0].issues


def test_rag_evaluation_quality_gate_rejects_failed_cases() -> None:
    from rag_evaluation import quality_gate_issues

    summary = RAGEvaluator().evaluate(
        [
            RAGEvaluationCase(
                case_id="missing_quality_gate",
                query="missing benchmark target",
                expected_titles=["Not A Real Knowledge Chunk"],
                expected_source_contains="missing.md",
                top_k=3,
            )
        ]
    )

    issues = quality_gate_issues(summary)

    assert any("passed cases" in issue for issue in issues)
    assert any("hit_at_k" in issue for issue in issues)


def test_rag_evaluation_cli_returns_failure_when_quality_gate_fails(
    monkeypatch,
    capsys,
) -> None:
    failed_summary = RAGEvaluator().evaluate(
        [
            RAGEvaluationCase(
                case_id="missing_cli_gate",
                query="missing benchmark target",
                expected_titles=["Not A Real Knowledge Chunk"],
                expected_source_contains="missing.md",
                top_k=3,
            )
        ]
    )
    monkeypatch.setattr(
        RAGEvaluator,
        "evaluate",
        lambda self, cases: failed_summary,
    )

    exit_code = main([])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["quality_gate"]["passed"] is False
    assert payload["quality_gate"]["issues"]


def test_rag_evaluation_cli_outputs_json(monkeypatch, capsys) -> None:
    first_case = build_default_rag_evaluation_cases()[0]
    passing_summary = RAGEvaluator().evaluate([first_case])
    monkeypatch.setattr(
        RAGEvaluator,
        "evaluate",
        lambda self, cases: passing_summary,
    )

    exit_code = main([])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["total_cases"] == 1
    assert "hit_at_k" in payload
    assert "mean_reciprocal_rank" in payload
    assert payload["quality_gate"]["passed"] is True

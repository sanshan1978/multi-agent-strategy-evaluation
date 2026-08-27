from __future__ import annotations

from pathlib import Path

from rag import MarkdownIngestionPipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_DIR = PROJECT_ROOT / "rag" / "documents"
EXPECTED_FILES = {
    "terrain_and_scenarios.md",
    "intelligence_and_reconnaissance.md",
    "communication_and_command.md",
    "resources_and_logistics.md",
    "multi_agent_coordination.md",
    "risk_and_safety_constraints.md",
    "deception_and_anomaly_response.md",
    "strategy_evaluation_metrics.md",
    "decision_workflow_and_termination.md",
    "degradation_and_recovery.md",
    "tool_calling_governance.md",
    "compound_scenario_cases.md",
}


def _ingest_corpus(tmp_path: Path):
    return MarkdownIngestionPipeline(
        DOCUMENTS_DIR,
        history_db_path=tmp_path / "corpus_ingestion.db",
        collection="corpus_contract",
    ).run()


def test_knowledge_corpus_has_expected_files_and_chunk_count(tmp_path) -> None:
    result = _ingest_corpus(tmp_path)

    actual_files = {path.name for path in DOCUMENTS_DIR.glob("*.md")}
    assert actual_files == EXPECTED_FILES
    assert len(result.files) == 12
    assert all(item.status == "success" for item in result.files)
    assert 60 <= len(result.chunks) <= 70


def test_knowledge_corpus_has_unique_titles_and_complete_metadata(tmp_path) -> None:
    result = _ingest_corpus(tmp_path)

    titles = [chunk.title for chunk in result.chunks]
    assert len(titles) == len(set(titles))
    for chunk in result.chunks:
        assert chunk.source in EXPECTED_FILES
        assert chunk.metadata["source_name"] == chunk.source
        assert chunk.metadata["document_title"]
        assert chunk.metadata["section_title"] == chunk.title
        assert chunk.metadata["tags"]
        assert chunk.metadata["collection"] == "corpus_contract"

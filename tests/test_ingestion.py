from __future__ import annotations

from rag import MarkdownIngestionPipeline


def test_markdown_ingestion_extracts_metadata_and_chunks(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text(
        """# Tactical Guide

## Urban Safety

tags: urban civilian_dense risk_control

城市高密度区域需要控制附带损害。

## Mountain Delay

山地迟滞需要控制隘口和补给线。
""",
        encoding="utf-8",
    )

    pipeline = MarkdownIngestionPipeline(
        docs_dir,
        history_db_path=tmp_path / "ingestion.db",
        collection="test_collection",
        chunk_size=80,
        chunk_overlap=10,
    )

    result = pipeline.run()

    assert result.to_dict()["files_total"] == 1
    assert result.to_dict()["files_processed"] == 1
    assert len(result.chunks) == 2
    first = result.chunks[0]
    assert first.title == "Urban Safety"
    assert first.source == "guide.md"
    assert first.metadata["document_title"] == "Tactical Guide"
    assert first.metadata["section_title"] == "Urban Safety"
    assert "urban" in first.metadata["tags"]
    assert first.metadata["collection"] == "test_collection"


def test_markdown_ingestion_marks_unchanged_files(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text(
        "# Guide\n\n## Section\n\nstable content",
        encoding="utf-8",
    )
    pipeline = MarkdownIngestionPipeline(
        docs_dir,
        history_db_path=tmp_path / "ingestion.db",
        collection="test_collection",
    )

    first = pipeline.run()
    second = pipeline.run()

    assert first.files[0].unchanged is False
    assert second.files[0].unchanged is True
    assert second.to_dict()["files_unchanged"] == 1


def test_markdown_ingestion_splits_large_sections(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    body = "段落一。" * 80
    (docs_dir / "large.md").write_text(f"# Guide\n\n## Large Section\n\n{body}", encoding="utf-8")

    pipeline = MarkdownIngestionPipeline(
        docs_dir,
        history_db_path=tmp_path / "ingestion.db",
        collection="test_collection",
        chunk_size=220,
        chunk_overlap=20,
    )

    result = pipeline.run()

    assert len(result.chunks) > 1
    assert all(chunk.metadata["chunk_size"] <= 220 for chunk in result.chunks)

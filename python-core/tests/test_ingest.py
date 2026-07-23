from pathlib import Path

from wiki_agent.ingest import content_hash, extract_text


def test_extract_text_and_hash(tmp_path: Path):
    document = tmp_path / "decision.md"
    document.write_text("决定使用证据驱动需求工程。", encoding="utf-8")
    assert extract_text(document) == "决定使用证据驱动需求工程。"
    assert len(content_hash(document)) == 64


def test_unsupported_document(tmp_path: Path):
    document = tmp_path / "image.png"
    document.write_bytes(b"png")
    try:
        extract_text(document)
    except ValueError as exc:
        assert "不支持" in str(exc)
    else:
        raise AssertionError("expected ValueError")

import io

import pytest

from worker.extract_child import DOCX, extract
from worker.portfolio import extract_text, summarise


def test_summary_is_short_and_ends_on_a_sentence() -> None:
    text = "We built a voice agent for a dental clinic. It answers calls at night. " * 30
    out = summarise(text, limit=120)
    assert len(out) <= 121 and out.endswith(".")


def test_text_extraction_runs_in_a_child_process() -> None:
    assert (
        extract_text(b"Case study:\n\n\n\nphone   agent", "text/plain")
        == "Case study:\n\nphone agent"
    )


def test_docx_extraction() -> None:
    from docx import Document

    doc = Document()
    doc.add_paragraph("Booked 300 appointments by phone")
    buf = io.BytesIO()
    doc.save(buf)
    assert "300 appointments" in extract(buf.getvalue(), DOCX)


def test_unreadable_pdf_fails_cleanly() -> None:
    with pytest.raises(ValueError):
        extract_text(b"%PDF-1.7 this is not really a pdf", "application/pdf")

import io
import zipfile

from api.filetypes import DOCX, PDF, TEXT, name_matches, sniff


def _docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


def test_real_types_are_recognised() -> None:
    assert sniff(b"%PDF-1.7\n...") == sniff(b"%PDF-1.4")
    assert sniff(b"%PDF-1.7").mime == PDF  # type: ignore[union-attr]
    assert sniff(_docx()).mime == DOCX  # type: ignore[union-attr]
    assert sniff("Case study: café".encode()).mime == TEXT  # type: ignore[union-attr]


def test_programs_and_disguised_files_are_rejected() -> None:
    assert sniff(b"MZ\x90\x00") is None  # Windows program named .pdf
    assert sniff(b"\x7fELF\x02\x01") is None
    assert sniff(b"#!/bin/sh\nrm -rf /") is None
    assert sniff(b"PK\x03\x04not-a-zip") is None
    assert sniff(b"text with \x00 nul") is None


def test_name_must_match_content() -> None:
    pdf = sniff(b"%PDF-1.7")
    text = sniff(b"hello")
    assert pdf is not None and text is not None
    assert name_matches("case.pdf", pdf)
    assert not name_matches("case.txt", pdf)
    assert not name_matches("case.pdf", text)

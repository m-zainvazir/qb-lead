"""Decide a file's type from its content, never from its name."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEXT = "text/plain"

_EXTENSIONS = {PDF: ".pdf", DOCX: ".docx", TEXT: ".txt"}
_BINARY_MAGIC = (b"MZ", b"\x7fELF", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe", b"#!", b"PK")


@dataclass(frozen=True)
class FileType:
    mime: str
    ext: str


def sniff(data: bytes) -> FileType | None:
    if data.startswith(b"%PDF-"):
        return FileType(PDF, ".pdf")
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile:
            return None
        if "word/document.xml" in names and "[Content_Types].xml" in names:
            return FileType(DOCX, ".docx")
        return None
    if any(data.startswith(m) for m in _BINARY_MAGIC) or b"\x00" in data:
        return None
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return FileType(TEXT, ".txt")


def name_matches(filename: str, filetype: FileType) -> bool:
    """A file named .pdf must really be a PDF (and so on)."""
    lower = filename.lower()
    if filetype.mime == DOCX:
        return lower.endswith(".docx")
    return lower.endswith(_EXTENSIONS[filetype.mime]) or (
        filetype.mime == TEXT and lower.endswith((".txt", ".md"))
    )

"""Text extraction, run as a separate short-lived process with time and memory limits.

    python -m worker.extract_child <mime>   (file bytes on stdin, text on stdout)

Kept tiny on purpose: a malformed or hostile file can at worst kill this child.
"""

from __future__ import annotations

import io
import re
import sys

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_PAGES = 50
MAX_CHARS = 50_000


def extract(data: bytes, mime: str) -> str:
    if mime == PDF:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:MAX_PAGES])
    elif mime == DOCX:
        from docx import Document

        text = "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    else:
        text = data.decode("utf-8", errors="replace")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:MAX_CHARS]


def main() -> int:
    mime = sys.argv[1]
    data = sys.stdin.buffer.read()
    sys.stdout.buffer.write(extract(data, mime).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

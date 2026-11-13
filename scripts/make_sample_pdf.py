"""Write a small, valid one-page PDF with text (test fixture for portfolio uploads).

python scripts/make_sample_pdf.py sample.pdf
"""

from __future__ import annotations

import sys

TEXT = [
    "Case study: AI voice agent for a dental clinic",
    "The clinic missed 40 calls a week after hours.",
    "We built a voice agent that answers, books appointments and sends reminders.",
    "No-shows fell by a third in two months.",
]


def build() -> bytes:
    lines = "".join(f"({t}) Tj T* " for t in TEXT)
    stream = f"BT /F1 12 Tf 14 TL 72 720 Td {lines}ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


if __name__ == "__main__":
    with open(sys.argv[1] if len(sys.argv) > 1 else "sample.pdf", "wb") as fh:
        fh.write(build())

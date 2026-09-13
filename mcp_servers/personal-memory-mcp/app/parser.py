from pathlib import Path
from collections.abc import Callable
from typing import Final

from pypdf import PdfReader
from docx import Document


def parse_pdf(file_path: str | Path) -> str:

    reader = PdfReader(file_path)

    text = []

    for page in reader.pages:
        extracted = page.extract_text()

        if extracted:
            text.append(extracted)

    return "\n".join(text)


def parse_docx(file_path: str | Path) -> str:

    document = Document(str(file_path))

    return "\n".join(
        paragraph.text
        for paragraph in document.paragraphs
    )


def parse_txt(file_path: str | Path) -> str:
    return Path(file_path).read_text(encoding="utf-8")


PARSERS: Final[dict[str, Callable[[str | Path], str]]] = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".txt": parse_txt,
}


def parse_document(file_path: str | Path) -> str:
    extension = Path(file_path).suffix.lower()
    parser = PARSERS.get(extension)
    if parser is None:
        supported = ", ".join(sorted(PARSERS))
        raise ValueError(f"Unsupported file type: {extension or '<none>'}. Supported: {supported}")
    return parser(file_path)
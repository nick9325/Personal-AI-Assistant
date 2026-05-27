from pathlib import Path

from pypdf import PdfReader
from docx import Document


def parse_pdf(file_path: str) -> str:

    reader = PdfReader(file_path)

    text = []

    for page in reader.pages:
        extracted = page.extract_text()

        if extracted:
            text.append(extracted)

    return "\n".join(text)


def parse_docx(file_path: str) -> str:

    document = Document(file_path)

    return "\n".join(
        paragraph.text
        for paragraph in document.paragraphs
    )


def parse_txt(file_path: str) -> str:

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def parse_document(file_path: str) -> str:

    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        return parse_pdf(file_path)

    if extension == ".docx":
        return parse_docx(file_path)

    if extension == ".txt":
        return parse_txt(file_path)

    raise ValueError(
        f"Unsupported file type: {extension}"
    )
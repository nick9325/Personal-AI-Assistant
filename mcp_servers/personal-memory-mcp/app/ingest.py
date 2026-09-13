from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.parser import parse_document
from app.vectorstore import vectorstore


text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
)


def ingest_document(file_path: str | Path) -> dict[str, int | str]:

    text = parse_document(file_path)

    chunks = text_splitter.split_text(text)
    if not chunks:
        return {"status": "empty", "chunks_added": 0}

    documents = [
        Document(
            page_content=chunk,
            metadata={
                "source": str(file_path),
            },
        )
        for chunk in chunks
    ]

    vectorstore.add_documents(documents)

    return {
        "status": "success",
        "chunks_added": len(documents),
    }
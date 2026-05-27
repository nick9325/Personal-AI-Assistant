from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app.settings import CHROMA_DIR


embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


vectorstore = Chroma(
    collection_name="personal-memory",
    embedding_function=embeddings,
    persist_directory=str(CHROMA_DIR),
)
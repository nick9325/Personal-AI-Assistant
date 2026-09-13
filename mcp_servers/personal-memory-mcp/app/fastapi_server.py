from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import os

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
)

import logging
from pathlib import Path

from app.ingest import ingest_document
from app.settings import UPLOAD_DIR


logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


# ============================================================
# FASTAPI LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:

    logger.info("FastAPI Server Starting...")

    yield

    logger.info("FastAPI Server Shutdown")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Personal Memory API",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "message": "Personal Memory API Running",
        "status": "healthy",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health_check():

    return {
        "status": "healthy",
        "server": "personal-memory-api",
    }


# ============================================================
# FILE UPLOAD
# ============================================================

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...)
):

    try:

        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Filename is required",
            )

        UPLOAD_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_filename = Path(file.filename).name
        if safe_filename != file.filename or safe_filename in {"", ".", ".."}:
            raise HTTPException(status_code=400, detail="Unsafe filename")

        file_path = UPLOAD_DIR / safe_filename

        with open(file_path, "wb") as f:

            content = await file.read()

            f.write(content)

        logger.info("File uploaded: %s", safe_filename)

        result = ingest_document(
            str(file_path)
        )

        return {
            "filename": safe_filename,
            **result,
        }

    except HTTPException:
        raise
    except Exception as e:

        logger.exception(e)

        raise HTTPException(status_code=500, detail="Document ingestion failed") from e


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app.fastapi_server:app",
        host=os.getenv("PERSONAL_MEMORY_API_HOST", "127.0.0.1"),
        port=int(os.getenv("PERSONAL_MEMORY_API_PORT", "8004")),
        reload=True,
    )
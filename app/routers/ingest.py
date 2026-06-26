import io
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import pypdf
from app.services.pinecone_service import upsert_chunks

router = APIRouter()

CHUNK_SIZE = 1500      # ~375 tokens — better retrieval than 500 chars
CHUNK_OVERLAP = 200    # overlap prevents cutting mid-sentence
MIN_CHUNK_LEN = 100    # skip tiny fragments

def extract_chunks(file_bytes: bytes, filename: str) -> list[dict]:
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    chunks = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if not text:
            continue

        # Sliding window chunking with overlap
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk_text = text[start:end].strip()

            if len(chunk_text) >= MIN_CHUNK_LEN:
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "text": chunk_text,
                    "source": filename,
                    "page": page_num
                })

            start += CHUNK_SIZE - CHUNK_OVERLAP  # slide with overlap

    return chunks

@router.post("/")
async def ingest_pdf(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    user_id: str = Form(...)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    file_bytes = await file.read()

    # 20MB limit
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(413, "File too large. Maximum size is 20MB.")

    chunks = extract_chunks(file_bytes, file.filename)

    if not chunks:
        raise HTTPException(400, "Could not extract text from PDF. Is it a scanned image?")

    namespace = f"{user_id}_{project_id}"
    upsert_chunks(chunks, namespace)

    return {
        "message": "Ingested successfully",
        "filename": file.filename,
        "chunks": len(chunks),
        "pages": len(pypdf.PdfReader(io.BytesIO(file_bytes)).pages)
    }

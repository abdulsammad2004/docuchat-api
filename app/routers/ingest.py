import io
import uuid
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from pydantic import BaseModel
import pypdf
from app.services.pinecone_service import upsert_chunks

router = APIRouter()

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
MIN_CHUNK_LEN = 100

def extract_chunks(file_bytes: bytes, filename: str) -> list[dict]:
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    chunks = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            chunk_text = text[start:start + CHUNK_SIZE].strip()
            if len(chunk_text) >= MIN_CHUNK_LEN:
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "text": chunk_text,
                    "source": filename,
                    "page": page_num
                })
            start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks

def text_to_chunks(text: str, source: str) -> list[dict]:
    chunks = []
    start = 0
    while start < len(text):
        chunk_text = text[start:start + CHUNK_SIZE].strip()
        if len(chunk_text) >= MIN_CHUNK_LEN:
            chunks.append({
                "id": str(uuid.uuid4()),
                "text": chunk_text,
                "source": source,
                "page": 1
            })
        start += CHUNK_SIZE - CHUNK_OVERLAP
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

class URLRequest(BaseModel):
    url: str
    project_id: str
    user_id: str

@router.post("/url")
async def ingest_url(req: URLRequest):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                req.url,
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True
            )
            response.raise_for_status()
    except Exception as e:
        raise HTTPException(400, f"Could not fetch URL: {str(e)}")

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "meta"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    if len(text) < 100:
        raise HTTPException(400, "Could not extract enough content from this URL.")

    chunks = text_to_chunks(text, req.url)
    namespace = f"{req.user_id}_{req.project_id}"
    upsert_chunks(chunks, namespace)

    return {
        "message": "URL ingested successfully",
        "url": req.url,
        "chunks": len(chunks)
    }

@router.delete("/")
async def delete_document(
    project_id: str = Query(...),
    user_id: str = Query(...),
    filename: str = Query(...)
):
    from app.services.pinecone_service import _get_index
    index = _get_index()
    namespace = f"{user_id}_{project_id}"
    index.delete(
        filter={"source": filename},
        namespace=namespace
    )
    return {"message": f"{filename} deleted successfully"}
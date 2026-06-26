import os
import json
import anthropic
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.pinecone_service import query_index

router = APIRouter()
claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """You are a helpful document assistant. Answer questions based ONLY on the provided context documents.

Rules:
- Cite sources using [1], [2] etc. and always mention the filename and page number.
- If the answer is not clearly in the context, say: "I couldn't find that in your documents."
- Be concise but complete.
- Do not make up information."""

class ChatRequest(BaseModel):
    question: str
    project_id: str
    user_id: str

def build_context(chunks: list[dict]) -> str:
    context = ""
    for i, c in enumerate(chunks, 1):
        context += f"[{i}] File: {c['source']}, Page {c['page']} (relevance: {c['score']:.2f})\n{c['text']}\n\n"
    return context.strip()

@router.post("/")
async def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(400, "Question cannot be empty")

    namespace = f"{req.user_id}_{req.project_id}"
    chunks = query_index(req.question, namespace)

    if not chunks:
        return StreamingResponse(
            iter(["I couldn't find any relevant content in your documents for that question."]),
            media_type="text/plain"
        )

    context = build_context(chunks)
    sources = [{"source": c["source"], "page": c["page"], "score": round(c["score"], 3)} for c in chunks]
    user_message = f"Context documents:\n{context}\n\nQuestion: {req.question}"

    def stream():
        # Send sources as first line (JSON), then stream the answer
        yield f"__SOURCES__{json.dumps(sources)}__SOURCES_END__\n"
        with claude.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        ) as stream:
            for text in stream.text_stream:
                yield text

    return StreamingResponse(stream(), media_type="text/plain")

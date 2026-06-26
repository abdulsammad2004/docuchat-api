import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ingest, chat, projects

app = FastAPI(title="DocuChat API")

# In production, replace "*" with your actual Lovable/Vercel frontend domain
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])

@app.get("/")
def root():
    return {"status": "DocuChat API running"}

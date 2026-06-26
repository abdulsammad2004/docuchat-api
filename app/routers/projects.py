import os
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# ---------------------------------------------------------------------------
# Supabase integration (uncomment when SUPABASE_URL + SUPABASE_KEY are set)
# ---------------------------------------------------------------------------
# from supabase import create_client
# supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# For now: in-memory store so the API works immediately on Railway.
# Replace each function body with the commented-out Supabase calls below.
_projects: dict[str, list] = {}

class Project(BaseModel):
    name: str
    user_id: str

@router.post("/")
def create_project(project: Project):
    project_id = str(uuid.uuid4())

    # --- Supabase version ---
    # result = supabase.table("projects").insert({
    #     "id": project_id,
    #     "name": project.name,
    #     "user_id": project.user_id
    # }).execute()
    # return {"project_id": project_id, "name": project.name}

    _projects.setdefault(project.user_id, []).append({
        "project_id": project_id,
        "name": project.name,
        "user_id": project.user_id
    })
    return {"project_id": project_id, "name": project.name}

@router.get("/{user_id}")
def get_projects(user_id: str):
    # --- Supabase version ---
    # result = supabase.table("projects").select("*").eq("user_id", user_id).execute()
    # return {"projects": result.data}

    return {"projects": _projects.get(user_id, [])}

@router.delete("/{project_id}")
def delete_project(project_id: str, user_id: str):
    from app.services.pinecone_service import delete_namespace
    delete_namespace(f"{user_id}_{project_id}")

    # --- Supabase version ---
    # supabase.table("projects").delete().eq("id", project_id).eq("user_id", user_id).execute()

    if user_id in _projects:
        _projects[user_id] = [p for p in _projects[user_id] if p["project_id"] != project_id]

    return {"message": "Project deleted"}

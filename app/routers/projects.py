import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

router = APIRouter()

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"]
)

class Project(BaseModel):
    name: str
    user_id: str

@router.post("/")
def create_project(project: Project):
    result = supabase.table("projects").insert({
        "name": project.name,
        "user_id": project.user_id
    }).execute()
    data = result.data[0]
    return {"project_id": data["id"], "name": data["name"]}

@router.get("/{user_id}")
def get_projects(user_id: str):
    result = supabase.table("projects").select("*").eq("user_id", user_id).execute()
    return {"projects": [{"project_id": p["id"], "name": p["name"]} for p in result.data]}

@router.delete("/{project_id}")
def delete_project(project_id: str, user_id: str):
    from app.services.pinecone_service import delete_namespace
    delete_namespace(f"{user_id}_{project_id}")
    supabase.table("projects").delete().eq("id", project_id).eq("user_id", user_id).execute()
    return {"message": "Project deleted"}
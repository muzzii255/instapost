import os
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from pydantic import BaseModel, Field
from tasks import app as celery_app
from tasks import scrape_insta
from celery.result import AsyncResult
from typing import List, Optional, Dict, Any
from datetime import datetime
from db_utils import get_user_with_posts
from dotenv import load_dotenv
load_dotenv()



app = FastAPI(
    title="Insta API",
    version="1.0.0"
)

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    traceback: Optional[str] = None
    date_done: Optional[datetime] = None

class UserRequest(BaseModel):
    username : str

API_KEY =  os.getenv("APIKEY")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



def verify_api_key(request: Request):
    auth_header = request.headers.get("authorization")

    if not auth_header:
        raise HTTPException(status_code=401, detail="API key required")

    if auth_header.startswith("Bearer "):
        api_key = auth_header[7:]
    else:
        api_key = auth_header

    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True


def get_task_info(task_id: str) -> Dict[str, Any]:
    try:
        result = AsyncResult(task_id, app=celery_app)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result,
            "traceback": result.traceback,
            "date_done": result.date_done
        }
        if result.status in ['SUCCESS', 'FAILURE', 'REVOKED']:
            result.forget()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving task info: {str(e)}")




@app.get("/api/v1/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, _: bool = Depends(verify_api_key)):
    try:
        task_info = get_task_info(task_id)
        return TaskStatusResponse(**task_info)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")



@app.post("/api/v1/scrape/username", response_model=TaskResponse)
async def scrape_username(request: UserRequest, _: bool = Depends(verify_api_key)):
    try:
        task = scrape_insta.delay(
            request.username
        )
        return TaskResponse(
            task_id=task.id,
            status="queued",
            message=f"Userscraping task queued for {request.username}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@app.post("/api/v1/get-user")
async def get_user(request:UserRequest, _: bool = Depends(verify_api_key) ):
    try:
        data = get_user_with_posts(request.username)
        return data
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

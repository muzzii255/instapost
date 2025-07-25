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
import logging

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        logger.info(f"Checking task status for: {task_id}")
        result = AsyncResult(task_id, app=celery_app)
        
        logger.info(f"Task {task_id} status: {result.status}")
        
        task_info = {
            "task_id": task_id,
            "status": result.status,
            "result": result.result,
            "traceback": result.traceback,
            "date_done": result.date_done
        }
        
        return task_info
        
    except Exception as e:
        logger.error(f"Error retrieving task info for {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving task info: {str(e)}")

@app.get("/api/v1/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, _: bool = Depends(verify_api_key)):
    try:
        result = AsyncResult(task_id, app=celery_app)
        
        logger.info(f"Task {task_id} exists: {result.id is not None}")
        logger.info(f"Task {task_id} status: {result.status}")
        
        if result.status == 'PENDING' and result.result is None:
            logger.warning(f"Task {task_id} appears to not exist or has been cleaned up")
            raise HTTPException(
                status_code=404, 
                detail=f"Task not found or has been cleaned up: {task_id}"
            )
        
        task_info = {
            "task_id": task_id,
            "status": result.status,
            "result": result.result,
            "traceback": result.traceback,
            "date_done": result.date_done
        }
        
        return TaskStatusResponse(**task_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error checking task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking task status: {str(e)}")

@app.post("/api/v1/scrape/username", response_model=TaskResponse)
async def scrape_username(request: UserRequest, _: bool = Depends(verify_api_key)):
    try:
        logger.info(f"Starting scrape task for username: {request.username}")
        
        task = scrape_insta.delay(request.username)
        
        logger.info(f"Task created with ID: {task.id} for username: {request.username}")
        
        return TaskResponse(
            task_id=task.id,
            status="queued",
            message=f"User scraping task queued for {request.username}"
        )
    except Exception as e:
        logger.error(f"Error creating scrape task for {request.username}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/get-user")
async def get_user(request: UserRequest, _: bool = Depends(verify_api_key)):
    try:
        logger.info(f"Getting user data for: {request.username}")
        data = get_user_with_posts(request.username)
        return data
    except Exception as e:
        logger.error(f"Error getting user data for {request.username}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/debug/celery-status")
async def celery_status(_: bool = Depends(verify_api_key)):
    try:
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()
        
        return {
            "celery_broker": celery_app.conf.broker_url,
            "celery_backend": celery_app.conf.result_backend,
            "active_tasks": active_tasks,
            "registered_tasks": list(celery_app.tasks.keys())
        }
    except Exception as e:
        logger.error(f"Error checking Celery status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Celery connection error: {str(e)}")
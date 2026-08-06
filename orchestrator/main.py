import asyncio
import json
import uuid
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Header
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from celery import Celery
from settings import settings
from schemas import TaskRequest, TaskResponse, StepResult
from graph import make_planner, make_verifier, plan, verify
from logger import logger

app = FastAPI(title="Orbit AI Orchestrator", version="1.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

celery_app = Celery("orchestrator", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_default_queue = settings.executor_queue

planner_llm = make_planner(settings.planner_model)
verifier_llm = make_verifier(settings.verifier_model)

# ===== WebSocket Connection Manager =====
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        self.active_connections[task_id] = websocket
    
    def disconnect(self, task_id: str):
        if task_id in self.active_connections:
            del self.active_connections[task_id]
    
    async def send_update(self, task_id: str, data: dict):
        if task_id in self.active_connections:
            try:
                await self.active_connections[task_id].send_json(data)
            except Exception:
                self.disconnect(task_id)

manager = ConnectionManager()

# ===== Polling with Updates =====
async def poll_result_with_updates(task_id: str, celery_task_id: str, step_index: int, step_text: str, ws_task_id: str):
    """Poll for result and send WebSocket updates."""
    res = celery_app.AsyncResult(celery_task_id)
    max_iters = int(settings.poll_max_seconds / settings.poll_interval)
    
    for _ in range(max_iters):
        if res.ready():
            if res.failed():
                await manager.send_update(ws_task_id, {
                    "type": "step_failed",
                    "index": step_index,
                    "step": step_text,
                    "error": str(res.result)
                })
                raise HTTPException(502, f"Executor falhou: {res.result}")
            
            result = res.result
            await manager.send_update(ws_task_id, {
                "type": "step_completed",
                "index": step_index,
                "step": step_text,
                "output": result.get("output", ""),
                "evidence": result.get("evidence", [])
            })
            return result
        
        await asyncio.sleep(settings.poll_interval)
    
    raise HTTPException(504, "Executor timeout")

async def poll_result(task_id: str):
    """Original poll without WebSocket updates."""
    res = celery_app.AsyncResult(task_id)
    max_iters = int(settings.poll_max_seconds / settings.poll_interval)
    for _ in range(max_iters):
        if res.ready():
            if res.failed():
                raise HTTPException(502, f"Executor falhou: {res.result}")
            return res.result
        await asyncio.sleep(settings.poll_interval)
    raise HTTPException(504, "Executor timeout")

# ===== WebSocket Endpoint =====
@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time task updates."""
    await manager.connect(websocket, task_id)
    try:
        while True:
            # Keep connection alive, client sends goal via this connection
            data = await websocket.receive_json()
            
            if data.get("action") == "execute":
                goal = data.get("goal", "")
                wide = data.get("wide", False)
                
                if not goal:
                    await websocket.send_json({"type": "error", "message": "Goal is required"})
                    continue
                
                # Send planning started
                await websocket.send_json({"type": "planning_started"})
                
                # Plan steps
                try:
                    steps = await plan(planner_llm, goal)
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": f"Planning failed: {str(e)}"})
                    continue
                
                if not steps:
                    await websocket.send_json({"type": "error", "message": "Planejamento vazio; refine o objetivo."})
                    continue
                
                if wide:
                    steps = steps[:settings.max_fanout]
                
                # Send steps planned
                await websocket.send_json({
                    "type": "steps_planned",
                    "steps": [{"index": i, "text": s, "status": "pending"} for i, s in enumerate(steps)]
                })
                
                # Dispatch and track steps
                try:
                    celery_tasks = []
                    for i, step in enumerate(steps):
                        celery_task_id = celery_app.send_task("executor.run_step", args=[step]).id
                        celery_tasks.append((i, step, celery_task_id))
                        await websocket.send_json({
                            "type": "step_started",
                            "index": i,
                            "step": step
                        })
                except Exception as exc:
                    await websocket.send_json({"type": "error", "message": f"Dispatch failed: {str(exc)}"})
                    continue
                
                # Poll results with updates
                results = []
                for i, step, celery_task_id in celery_tasks:
                    try:
                        result = await poll_result_with_updates(task_id, celery_task_id, i, step, task_id)
                        results.append(result)
                    except Exception as e:
                        results.append({"step": step, "output": f"Error: {str(e)}", "evidence": []})
                
                # Verify
                await websocket.send_json({"type": "verifying"})
                lines = [f"{r.get('step', '')}\n{r.get('output', '')}" for r in results]
                try:
                    ok, summary = await verify(verifier_llm, goal, lines)
                except Exception as e:
                    ok, summary = False, f"Verification failed: {str(e)}"
                
                # Send final result
                await websocket.send_json({
                    "type": "completed",
                    "goal": goal,
                    "steps": [StepResult(**r).model_dump() for r in results],
                    "verified": ok,
                    "summary": summary
                })
                
    except WebSocketDisconnect:
        manager.disconnect(task_id)

# ===== Original REST Endpoint =====
@app.post("/task", response_model=TaskResponse)
async def run_task(req: TaskRequest):
    # Import here to avoid circular imports
    from database import create_task, update_task_status, add_step, update_step
    
    # Create task in database
    db_task_id = create_task(req.goal, req.wide)
    update_task_status(db_task_id, 'planning')
    
    steps = await plan(planner_llm, req.goal)
    if not steps:
        update_task_status(db_task_id, 'failed', False, "Planejamento vazio")
        raise HTTPException(400, "Planejamento vazio; refine o objetivo.")
    if req.wide:
        steps = steps[: settings.max_fanout]

    # Add steps to database
    db_step_ids = []
    for i, step in enumerate(steps):
        step_id = add_step(db_task_id, i, step)
        db_step_ids.append(step_id)
    
    update_task_status(db_task_id, 'executing')

    try:
        task_ids = [
            celery_app.send_task("executor.run_step", args=[step]).id
            for step in steps
        ]
    except Exception as exc:  # Celery/broker issues
        update_task_status(db_task_id, 'failed', False, f"Dispatch failed: {exc}")
        raise HTTPException(502, f"Não foi possível despachar para executores: {exc}") from exc
    logger.info("dispatched", steps=len(task_ids))

    results_raw = await asyncio.gather(*[poll_result(tid) for tid in task_ids], return_exceptions=True)
    failures = [r for r in results_raw if isinstance(r, Exception)]
    if failures:
        update_task_status(db_task_id, 'failed', False, f"Executor failure: {failures[0]}")
        raise HTTPException(502, f"Falha em executor: {failures[0]}")

    results_raw = [r for r in results_raw if not isinstance(r, Exception)]
    results = [StepResult(**r) for r in results_raw]
    
    # Update steps in database
    for i, (step_id, result) in enumerate(zip(db_step_ids, results)):
        update_step(step_id, 'completed', result.output, result.evidence)
    
    lines = [f"{r.step}\n{r.output}" for r in results]
    ok, summary = await verify(verifier_llm, req.goal, lines)
    
    # Update task as completed
    update_task_status(db_task_id, 'completed', ok, summary)
    
    return TaskResponse(goal=req.goal, steps=results, verified=ok, summary=summary)


# ===== History Endpoints =====
@app.get("/history")
async def get_history(limit: int = 20, offset: int = 0):
    """Get task history."""
    from database import get_task_history
    tasks = get_task_history(limit, offset)
    return {"tasks": tasks, "limit": limit, "offset": offset}


@app.get("/history/{task_id}")
async def get_task_by_id(task_id: int):
    """Get task details by ID."""
    from database import get_task_detail
    task = get_task_detail(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@app.delete("/history/{task_id}")
async def delete_task_by_id(task_id: int):
    """Delete a task from history."""
    from database import delete_task
    deleted = delete_task(task_id)
    if not deleted:
        raise HTTPException(404, "Task not found")
    return {"message": "Task deleted", "id": task_id}


# ===== Authentication Dependency =====
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Dependency to get current authenticated user."""
    from auth import validate_token, get_user_by_id
    
    if not authorization:
        return None  # Allow unauthenticated access by default
    
    # Extract token from "Bearer <token>" format
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        token = authorization
    
    user_id = validate_token(token)
    if not user_id:
        raise HTTPException(401, "Invalid or expired token")
    
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "User not found")
    
    return user


async def require_auth(user = Depends(get_current_user)):
    """Dependency that requires authentication."""
    if not user:
        raise HTTPException(401, "Authentication required")
    return user


# ===== Auth Endpoints =====
@app.post("/auth/register")
async def register(username: str, password: str, email: str = None):
    """Register a new user."""
    from auth import create_user, create_token, UserCreate
    
    if len(username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters")
    if len(password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    
    user_id = create_user(username, password, email)
    if not user_id:
        raise HTTPException(400, "Username already exists")
    
    token, expires_at = create_token(user_id)
    
    return {
        "message": "User created successfully",
        "user_id": user_id,
        "access_token": token,
        "token_type": "bearer"
    }


@app.post("/auth/login")
async def login(username: str, password: str):
    """Login and get access token."""
    from auth import authenticate_user, create_token
    
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(401, "Invalid username or password")
    
    token, expires_at = create_token(user['id'])
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user['id'],
        "username": user['username']
    }


@app.get("/auth/me")
async def get_me(user = Depends(require_auth)):
    """Get current user info."""
    return {
        "id": user['id'],
        "username": user['username'],
        "email": user.get('email'),
        "created_at": user.get('created_at')
    }


@app.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """Logout and invalidate token."""
    from auth import delete_token
    
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        delete_token(token)
    
    return {"message": "Logged out successfully"}

import sqlite3
from typing import Optional
from pydantic import BaseModel
from settings import settings
import json
import os

DB_PATH = settings.history_db_path


def ensure_db_dir() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ===== Pydantic Models =====
class TaskHistoryCreate(BaseModel):
    goal: str
    wide: bool = False

class TaskHistoryResponse(BaseModel):
    id: int
    goal: str
    status: str
    verified: Optional[bool] = None
    summary: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    steps_count: int = 0

class TaskHistoryDetail(TaskHistoryResponse):
    steps: list

# ===== Database Functions =====
def get_db():
    """Get database connection."""
    ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create tasks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal TEXT NOT NULL,
            wide BOOLEAN DEFAULT FALSE,
            status TEXT DEFAULT 'pending',
            verified BOOLEAN,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    
    # Create steps table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            step_index INTEGER NOT NULL,
            step_text TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            output TEXT,
            evidence TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

def create_task(goal: str, wide: bool = False) -> int:
    """Create a new task and return its ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (goal, wide, status) VALUES (?, ?, 'planning')",
        (goal, wide)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def update_task_status(task_id: int, status: str, verified: bool = None, summary: str = None):
    """Update task status."""
    conn = get_db()
    cursor = conn.cursor()
    
    if status == 'completed' or status == 'failed':
        cursor.execute(
            """UPDATE tasks 
               SET status = ?, verified = ?, summary = ?, completed_at = CURRENT_TIMESTAMP 
               WHERE id = ?""",
            (status, verified, summary, task_id)
        )
    else:
        cursor.execute(
            "UPDATE tasks SET status = ? WHERE id = ?",
            (status, task_id)
        )
    
    conn.commit()
    conn.close()

def add_step(task_id: int, step_index: int, step_text: str) -> int:
    """Add a step to a task."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO steps (task_id, step_index, step_text) VALUES (?, ?, ?)",
        (task_id, step_index, step_text)
    )
    step_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return step_id

def update_step(step_id: int, status: str, output: str = None, evidence: list = None):
    """Update step status and result."""
    conn = get_db()
    cursor = conn.cursor()
    
    evidence_json = json.dumps(evidence) if evidence else None
    
    if status in ('completed', 'failed'):
        cursor.execute(
            """UPDATE steps 
               SET status = ?, output = ?, evidence = ?, completed_at = CURRENT_TIMESTAMP 
               WHERE id = ?""",
            (status, output, evidence_json, step_id)
        )
    else:
        cursor.execute(
            "UPDATE steps SET status = ? WHERE id = ?",
            (status, step_id)
        )
    
    conn.commit()
    conn.close()

def get_task_history(limit: int = 20, offset: int = 0) -> list:
    """Get task history."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT t.*, COUNT(s.id) as steps_count
        FROM tasks t
        LEFT JOIN steps s ON t.id = s.task_id
        GROUP BY t.id
        ORDER BY t.created_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_task_detail(task_id: int) -> Optional[dict]:
    """Get task with all steps."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get task
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task_row = cursor.fetchone()
    
    if not task_row:
        conn.close()
        return None
    
    task = dict(task_row)
    
    # Get steps
    cursor.execute(
        "SELECT * FROM steps WHERE task_id = ? ORDER BY step_index",
        (task_id,)
    )
    steps = []
    for row in cursor.fetchall():
        step = dict(row)
        if step.get('evidence'):
            step['evidence'] = json.loads(step['evidence'])
        steps.append(step)
    
    task['steps'] = steps
    task['steps_count'] = len(steps)
    
    conn.close()
    return task

def delete_task(task_id: int) -> bool:
    """Delete a task and its steps."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM steps WHERE task_id = ?", (task_id,))
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

# Initialize database on module import
init_db()

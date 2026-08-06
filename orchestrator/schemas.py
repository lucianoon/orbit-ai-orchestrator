from pydantic import BaseModel
from typing import List, Any, Dict

class TaskRequest(BaseModel):
    goal: str
    wide: bool = False

class StepResult(BaseModel):
    step: str
    output: str
    evidence: List[Dict[str, Any]]

class TaskResponse(BaseModel):
    goal: str
    steps: List[StepResult]
    verified: bool
    summary: str

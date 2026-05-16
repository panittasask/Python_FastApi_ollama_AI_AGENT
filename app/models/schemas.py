"""Pydantic schemas used by the API and inter-agent communication."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Generation params ---

class ModelConfig(BaseModel):
    refiner_model: Optional[str] = None
    coder_model: Optional[str] = None
    fix_model: Optional[str] = None
    planner_model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    num_ctx: Optional[int] = None


# --- Plan & tasks ---

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanTask(BaseModel):
    id: str
    title: str
    description: str = ""
    file_path: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    notes: str = ""


class ProjectPlan(BaseModel):
    project_name: str
    description: str = ""
    architecture: str = ""
    dependencies: list[str] = Field(default_factory=list)
    tasks: list[PlanTask] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# --- File generation ---

class GeneratedFile(BaseModel):
    path: str = Field(..., description="Relative file path within the project")
    content: str
    purpose: str = ""


class CodeGenerationResult(BaseModel):
    files: list[GeneratedFile] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    notes: str = ""


# --- API request/response ---

class GenerateRequest(BaseModel):
    prompt: str
    output_path: Optional[str] = None
    project_name: Optional[str] = None
    config: Optional[ModelConfig] = None
    stream: bool = False


class GenerateProjectRequest(BaseModel):
    prompt: str
    project_name: str
    output_path: Optional[str] = None
    config: Optional[ModelConfig] = None
    auto_test: Optional[bool] = None
    max_loops: Optional[int] = None


class GenerateResponse(BaseModel):
    project_name: str
    output_path: str
    files: list[str] = Field(default_factory=list)
    refined_prompt: Optional[str] = None
    notes: str = ""


class TestRequest(BaseModel):
    project_path: str
    command: Optional[str] = None


class TestResult(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    command: str = ""


class FixRequest(BaseModel):
    project_path: str
    error_log: str
    file_path: Optional[str] = None
    config: Optional[ModelConfig] = None


class StatusResponse(BaseModel):
    running_jobs: int
    completed_jobs: int
    failed_jobs: int
    details: list[dict[str, Any]] = Field(default_factory=list)

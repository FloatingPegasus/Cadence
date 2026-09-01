from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ...domains.tasks import service as tasks_service
from ...extensions import get_db
from ...persistence.models.user import User
from .auth import get_current_user


router = APIRouter(tags=["tasks"])


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Task title cannot be blank")
        return title


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    due_date: date | None = None
    is_completed: bool | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        title = value.strip()
        if not title:
            raise ValueError("Task title cannot be blank")
        return title


def _translate_task_error(error: Exception) -> None:
    if isinstance(error, tasks_service.TaskNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    raise error


@router.get("/tasks")
async def list_tasks(
    due_on: date | None = None,
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await tasks_service.list_tasks(
        db, user.id, due_on=due_on, month=month
    )


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await tasks_service.create_task(
        db, user.id, title=body.title, due_date=body.due_date
    )


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    fields = body.model_dump(exclude_unset=True)
    try:
        return await tasks_service.update_task(
            db,
            user.id,
            task_id,
            title=fields.get("title"),
            due_date=fields.get("due_date"),
            is_completed=fields.get("is_completed"),
            due_date_set="due_date" in fields,
        )
    except tasks_service.TaskNotFoundError as error:
        _translate_task_error(error)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        await tasks_service.delete_task(db, user.id, task_id)
    except tasks_service.TaskNotFoundError as error:
        _translate_task_error(error)

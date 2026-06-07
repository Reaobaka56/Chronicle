"""Repo management and settings API."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, HttpUrl

from app.database import get_db
from app.models import Repo, Tone, User

router = APIRouter(prefix="/api/repos", tags=["repos"])


class RepoOut(BaseModel):
    id: int
    full_name: str
    name: str
    owner_login: str
    tone: Tone
    auto_publish: bool
    slack_webhook_url: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class RepoSettingsUpdate(BaseModel):
    tone: Optional[Tone] = None
    auto_publish: Optional[bool] = None
    slack_webhook_url: Optional[str] = None
    custom_template: Optional[str] = None


@router.get("", response_model=List[RepoOut])
async def list_repos(db: AsyncSession = Depends(get_db)):
    """List all repos for the current user."""
    result = await db.execute(select(Repo).order_by(Repo.created_at.desc()))
    return result.scalars().all()


@router.get("/{repo_id}", response_model=RepoOut)
async def get_repo(repo_id: int, db: AsyncSession = Depends(get_db)):
    """Get repo details."""
    result = await db.execute(select(Repo).where(Repo.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo


@router.patch("/{repo_id}/settings")
async def update_repo_settings(
    repo_id: int,
    update: RepoSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update repo settings."""
    result = await db.execute(select(Repo).where(Repo.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")

    if update.tone is not None:
        repo.tone = update.tone
    if update.auto_publish is not None:
        repo.auto_publish = update.auto_publish
    if update.slack_webhook_url is not None:
        repo.slack_webhook_url = update.slack_webhook_url
    if update.custom_template is not None:
        repo.custom_template = update.custom_template

    await db.commit()
    await db.refresh(repo)
    return repo

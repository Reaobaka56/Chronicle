"""Release and changelog API."""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from app.database import get_db
from app.models import Release, Repo, MergedPR, Tone
from app.github_utils import github_auth, GitHubAPI
from app.ai_service import generator

router = APIRouter(prefix="/api/releases", tags=["releases"])


class ReleaseOut(BaseModel):
    id: int
    tag_name: str
    name: Optional[str]
    body: Optional[str]
    body_draft: Optional[str]
    published: bool
    published_at: Optional[datetime]
    generated_at: datetime
    github_html_url: Optional[str]

    class Config:
        from_attributes = True


class GenerateRequest(BaseModel):
    tag_name: str
    since_tag: Optional[str] = None
    tone: Optional[Tone] = None


class PublishRequest(BaseModel):
    body: str


@router.get("/{repo_id}", response_model=List[ReleaseOut])
async def list_releases(repo_id: int, db: AsyncSession = Depends(get_db)):
    """List all releases for a repo."""
    result = await db.execute(
        select(Release)
        .where(Release.repo_id == repo_id)
        .order_by(desc(Release.created_at))
    )
    return result.scalars().all()


@router.get("/{repo_id}/{release_id}", response_model=ReleaseOut)
async def get_release(repo_id: int, release_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific release."""
    result = await db.execute(
        select(Release).where(Release.id == release_id, Release.repo_id == repo_id)
    )
    release = result.scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


@router.post("/{repo_id}/generate")
async def generate_changelog(
    repo_id: int,
    req: GenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually generate a changelog for a tag."""
    result = await db.execute(select(Repo).where(Repo.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")

    # Get installation token
    token = await github_auth.get_repo_installation_token(
        repo.owner_login, repo.name
    )
    gh = GitHubAPI(token)

    try:
        # Fetch PRs since last tag
        since = None
        if req.since_tag:
            # Get tag date from GitHub
            tags = await gh.get_tags(repo.owner_login, repo.name)
            for tag in tags:
                if tag["name"] == req.since_tag:
                    # Fetch commit date
                    commit_resp = await gh.client.get(tag["commit"]["url"])
                    commit_resp.raise_for_status()
                    since = datetime.fromisoformat(
                        commit_resp.json()["commit"]["committer"]["date"].replace("Z", "+00:00")
                    )
                    break

        # Get merged PRs from database (already stored via webhook)
        query = select(MergedPR).where(
            MergedPR.repo_id == repo_id,
            MergedPR.included_in_release_id.is_(None),
        )
        if since:
            query = query.where(MergedPR.merged_at > since)
        query = query.order_by(MergedPR.merged_at)

        pr_records = (await db.execute(query)).scalars().all()

        prs = [
            {
                "number": p.github_pr_number,
                "title": p.title,
                "author": p.author_login,
                "labels": p.labels,
                "merged_at": p.merged_at.isoformat() if p.merged_at else None,
                "body": p.body,
                "additions": p.additions,
                "deletions": p.deletions,
                "files_changed": p.files_changed,
            }
            for p in pr_records
        ]

        if not prs:
            raise HTTPException(status_code=400, detail="No merged PRs found for this range")

        tone = req.tone or repo.tone

        result_data = await generator.generate_with_validation(
            prs=prs,
            tone=tone,
            tag_name=req.tag_name,
            previous_tag=req.since_tag,
            custom_template=repo.custom_template,
            repo_name=repo.full_name,
        )

        # Create or update release record
        existing = await db.execute(
            select(Release).where(
                Release.repo_id == repo_id,
                Release.tag_name == req.tag_name,
            )
        )
        release = existing.scalar_one_or_none()

        if release:
            release.body_draft = result_data["changelog"]
            release.generated_at = datetime.utcnow()
        else:
            release = Release(
                repo_id=repo_id,
                tag_name=req.tag_name,
                name=req.tag_name,
                body_draft=result_data["changelog"],
            )
            db.add(release)

        await db.commit()
        await db.refresh(release)

        return {
            "release_id": release.id,
            "changelog": result_data["changelog"],
            "issues": result_data["issues"],
            "coverage": result_data["coverage"],
            "pr_count": result_data["pr_count"],
        }

    finally:
        await gh.close()


@router.post("/{repo_id}/{release_id}/publish")
async def publish_release(
    repo_id: int,
    release_id: int,
    req: PublishRequest,
    db: AsyncSession = Depends(get_db),
):
    """Publish a release — write to GitHub and mark as published."""
    result = await db.execute(
        select(Release).where(Release.id == release_id, Release.repo_id == repo_id)
    )
    release = result.scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")

    repo_result = await db.execute(select(Repo).where(Repo.id == repo_id))
    repo = repo_result.scalar_one()

    # Update GitHub release
    token = await github_auth.get_repo_installation_token(
        repo.owner_login, repo.name
    )
    gh = GitHubAPI(token)

    try:
        if release.github_release_id:
            await gh.update_release(
                repo.owner_login,
                repo.name,
                release.github_release_id,
                body=req.body,
                draft=False,
            )
        else:
            # Create new release
            gh_release = await gh.create_release(
                repo.owner_login,
                repo.name,
                release.tag_name,
                release.name or release.tag_name,
                req.body,
                draft=False,
            )
            release.github_release_id = gh_release["id"]
            release.github_html_url = gh_release["html_url"]

        release.body = req.body
        release.published = True
        release.published_at = datetime.utcnow()

        # Mark PRs as included
        await db.execute(
            select(MergedPR).where(
                MergedPR.repo_id == repo_id,
                MergedPR.included_in_release_id.is_(None),
            )
        )
        # In production, link specific PRs to this release

        await db.commit()

        return {"status": "published", "html_url": release.github_html_url}

    finally:
        await gh.close()

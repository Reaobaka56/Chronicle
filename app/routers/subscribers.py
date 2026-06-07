"""Email subscriber management."""
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models import Subscriber, Repo, Release
from app.config import get_settings

router = APIRouter(prefix="/api/subscribe", tags=["subscribers"])


@router.post("/{owner}/{repo}")
async def subscribe(
    owner: str,
    repo: str,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Subscribe to a repo's changelog."""
    full_name = f"{owner}/{repo}"

    result = await db.execute(select(Repo).where(Repo.full_name == full_name))
    repo_obj = result.scalar_one_or_none()
    if not repo_obj:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Check if already subscribed
    existing = await db.execute(
        select(Subscriber).where(
            Subscriber.repo_id == repo_obj.id,
            Subscriber.email == email,
        )
    )
    if existing.scalar_one_or_none():
        return {"status": "already_subscribed"}

    subscriber = Subscriber(
        repo_id=repo_obj.id,
        email=email,
        confirmed=True,  # Simplified — add email confirmation in production
    )
    db.add(subscriber)
    await db.commit()

    return {"status": "subscribed", "email": email}


async def notify_subscribers(repo_id: int, release: Release, db: AsyncSession):
    """Send email notification to subscribers when a release is published."""
    settings = get_settings()

    if not settings.resend_api_key:
        return

    result = await db.execute(
        select(Subscriber).where(
            Subscriber.repo_id == repo_id,
            Subscriber.confirmed == True,
        )
    )
    subscribers = result.scalars().all()

    if not subscribers:
        return

    import httpx

    emails = [s.email for s in subscribers]

    async with httpx.AsyncClient() as client:
        for email in emails:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.resend_from_email,
                    "to": email,
                    "subject": f"New release: {release.tag_name}",
                    "html": f"""
                    <h1>{release.name or release.tag_name}</h1>
                    <p>A new release has been published. <a href="{release.github_html_url}">View on GitHub</a></p>
                    <hr>
                    {release.body[:2000] if release.body else ""}
                    """,
                },
            )

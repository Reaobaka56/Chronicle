"""GitHub webhook handler."""
import json
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database import get_db
from app.models import Repo, MergedPR, Installation, User, Release
from app.github_utils import verify_github_signature, github_auth, GitHubAPI
from app.ai_service import generator

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


SKIP_LABELS = {"chore", "deps", "dependencies", "internal", "ci", "docs-only"}


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Receive and process GitHub webhooks."""
    settings = get_settings()

    # Verify signature
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")

    if not verify_github_signature(body, signature, settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = request.headers.get("x-github-event", "")
    payload = json.loads(body)

    # Handle pull request merged
    if event_type == "pull_request" and payload.get("action") == "closed":
        pr_data = payload["pull_request"]
        if not pr_data.get("merged"):
            return {"status": "ignored", "reason": "not merged"}

        background_tasks.add_task(_handle_pr_merged, payload, db)
        return {"status": "queued", "event": "pr_merged"}

    # Handle release published (tag push)
    if event_type == "release" and payload.get("action") == "published":
        background_tasks.add_task(_handle_release_published, payload, db)
        return {"status": "queued", "event": "release_published"}

    # Handle installation events
    if event_type == "installation" and payload.get("action") == "created":
        background_tasks.add_task(_handle_installation_created, payload, db)
        return {"status": "queued", "event": "installation_created"}

    return {"status": "ignored", "event": event_type}


async def _handle_pr_merged(payload: dict, db: AsyncSession):
    """Process a merged PR webhook."""
    pr_data = payload["pull_request"]
    repo_data = payload["repository"]

    full_name = repo_data["full_name"]

    # Find or create repo
    result = await db.execute(select(Repo).where(Repo.full_name == full_name))
    repo = result.scalar_one_or_none()

    if not repo:
        # Auto-create repo on first PR if installation exists
        installation_id = payload.get("installation", {}).get("id")
        if installation_id:
            inst_result = await db.execute(
                select(Installation).where(
                    Installation.github_installation_id == installation_id
                )
            )
            installation = inst_result.scalar_one_or_none()
            if installation:
                repo = Repo(
                    github_repo_id=repo_data["id"],
                    owner_id=installation.user_id,
                    installation_id=installation.id,
                    full_name=full_name,
                    name=repo_data["name"],
                    owner_login=repo_data["owner"]["login"],
                    default_branch=repo_data.get("default_branch", "main"),
                )
                db.add(repo)
                await db.flush()

    if not repo:
        return  # Silently drop if repo not tracked

    # Check for duplicates
    existing = await db.execute(
        select(MergedPR).where(
            MergedPR.repo_id == repo.id,
            MergedPR.github_pr_number == pr_data["number"],
        )
    )
    if existing.scalar_one_or_none():
        return  # Idempotent

    # Extract labels
    labels = [label["name"] for label in pr_data.get("labels", [])]

    # Skip if only skip labels
    if labels and all(l.lower() in SKIP_LABELS for l in labels):
        return

    merged_pr = MergedPR(
        repo_id=repo.id,
        github_pr_number=pr_data["number"],
        title=pr_data["title"],
        body=pr_data.get("body", ""),
        author_login=pr_data["user"]["login"],
        merged_at=datetime.fromisoformat(pr_data["merged_at"].replace("Z", "+00:00")),
        merge_commit_sha=pr_data.get("merge_commit_sha"),
        labels=labels,
        additions=pr_data.get("additions", 0),
        deletions=pr_data.get("deletions", 0),
        files_changed=pr_data.get("changed_files", 0),
    )
    db.add(merged_pr)
    await db.commit()


async def _handle_release_published(payload: dict, db: AsyncSession):
    """Auto-generate changelog when a release is published."""
    release_data = payload["release"]
    repo_data = payload["repository"]
    full_name = repo_data["full_name"]

    result = await db.execute(select(Repo).where(Repo.full_name == full_name))
    repo = result.scalar_one_or_none()
    if not repo:
        return

    tag_name = release_data["tag_name"]

    # Check if already processed
    existing = await db.execute(
        select(Release).where(
            Release.repo_id == repo.id,
            Release.tag_name == tag_name,
        )
    )
    if existing.scalar_one_or_none():
        return

    # Get installation token
    installation_id = payload.get("installation", {}).get("id")
    if not installation_id:
        return

    token = await github_auth.get_installation_token(installation_id)
    gh = GitHubAPI(token)

    try:
        # Find previous release tag
        tags = await gh.get_tags(repo.owner_login, repo.name)
        previous_tag = None
        for i, tag in enumerate(tags):
            if tag["name"] == tag_name and i + 1 < len(tags):
                previous_tag = tags[i + 1]["name"]
                break

        # Fetch merged PRs since last release
        prs = await gh.get_merged_prs_since(
            repo.owner_login,
            repo.name,
            since=None,  # We'll filter by the release date range
        )

        # Filter PRs between tags (simplified — in production, use git compare)
        # For MVP, use PRs merged in last 30 days as heuristic
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=30)

        recent_prs = [
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
            for p in (await db.execute(
                select(MergedPR).where(
                    MergedPR.repo_id == repo.id,
                    MergedPR.merged_at >= cutoff,
                    MergedPR.included_in_release_id.is_(None),
                )
            )).scalars().all()
        ]

        if not recent_prs:
            return

        # Generate changelog
        result = await generator.generate_with_validation(
            prs=recent_prs,
            tone=repo.tone,
            tag_name=tag_name,
            previous_tag=previous_tag,
            custom_template=repo.custom_template,
            repo_name=full_name,
        )

        # Create release record
        release = Release(
            repo_id=repo.id,
            tag_name=tag_name,
            name=release_data.get("name", tag_name),
            body_draft=result["changelog"],
            github_release_id=release_data["id"],
            github_html_url=release_data.get("html_url"),
            published=repo.auto_publish,
        )
        db.add(release)
        await db.flush()

        # Mark PRs as included
        for pr in recent_prs:
            await db.execute(
                select(MergedPR).where(
                    MergedPR.repo_id == repo.id,
                    MergedPR.github_pr_number == pr["number"],
                )
            )

        # Update GitHub release if auto-publish
        if repo.auto_publish:
            await gh.update_release(
                repo.owner_login,
                repo.name,
                release_data["id"],
                body=result["changelog"],
                draft=False,
            )
            release.published = True
            release.published_at = datetime.utcnow()
            release.body = result["changelog"]

        await db.commit()

    finally:
        await gh.close()


async def _handle_installation_created(payload: dict, db: AsyncSession):
    """Handle GitHub App installation."""
    installation_data = payload["installation"]

    # Find or create user
    sender = payload["sender"]
    result = await db.execute(
        select(User).where(User.github_id == sender["id"])
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            github_id=sender["id"],
            github_login=sender["login"],
            email=sender.get("email"),
            avatar_url=sender.get("avatar_url"),
        )
        db.add(user)
        await db.flush()

    # Create installation record
    inst = Installation(
        github_installation_id=installation_data["id"],
        user_id=user.id,
        account_login=installation_data["account"]["login"],
        account_type=installation_data["account"]["type"],
    )
    db.add(inst)

    # Create repo records for each selected repo
    for repo_data in payload.get("repositories", []):
        repo = Repo(
            github_repo_id=repo_data["id"],
            owner_id=user.id,
            installation_id=inst.id,
            full_name=repo_data["full_name"],
            name=repo_data["name"],
            owner_login=repo_data["full_name"].split("/")[0],
        )
        db.add(repo)

    await db.commit()

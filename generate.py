#!/usr/bin/env python3
"""CLI trigger for manual changelog generation."""
import asyncio
import argparse
import os
import sys
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import AsyncSessionLocal, init_db
from app.models import Repo, MergedPR, Release
from app.github_utils import github_auth, GitHubAPI
from app.ai_service import generator, Tone


async def generate_cli(repo_full_name: str, since_tag: str = None, tone: str = "technical"):
    """Generate changelog via CLI."""
    await init_db()

    async with AsyncSessionLocal() as db:
        # Find repo
        from sqlalchemy import select
        result = await db.execute(
            select(Repo).where(Repo.full_name == repo_full_name)
        )
        repo = result.scalar_one_or_none()

        if not repo:
            print(f"Repo {repo_full_name} not found in database. Add it first via the dashboard.")
            return

        # Get token
        token = await github_auth.get_repo_installation_token(
            repo.owner_login, repo.name
        )
        gh = GitHubAPI(token)

        try:
            # Determine since date
            since = None
            if since_tag:
                tags = await gh.get_tags(repo.owner_login, repo.name)
                for tag in tags:
                    if tag["name"] == since_tag:
                        commit_resp = await gh.client.get(tag["commit"]["url"])
                        commit_resp.raise_for_status()
                        since = datetime.fromisoformat(
                            commit_resp.json()["commit"]["committer"]["date"].replace("Z", "+00:00")
                        )
                        break

            if not since:
                since = datetime.utcnow() - timedelta(days=30)

            # Fetch PRs from DB
            query = select(MergedPR).where(
                MergedPR.repo_id == repo.id,
                MergedPR.merged_at > since,
                MergedPR.included_in_release_id.is_(None),
            ).order_by(MergedPR.merged_at)

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
                print(f"No merged PRs found since {since}")
                return

            print(f"Found {len(prs)} PRs to include")

            # Generate
            tone_enum = Tone(tone)
            tag_name = f"v{datetime.utcnow().strftime('%Y.%m.%d')}"

            result_data = await generator.generate_with_validation(
                prs=prs,
                tone=tone_enum,
                tag_name=tag_name,
                previous_tag=since_tag,
                custom_template=repo.custom_template,
                repo_name=repo.full_name,
            )

            print("
" + "="*60)
            print("GENERATED CHANGELOG")
            print("="*60)
            print(result_data["changelog"])
            print("="*60)

            if result_data["issues"]:
                print("
⚠️  Quality issues:")
                for issue in result_data["issues"]:
                    print(f"  - {issue}")

            print(f"
Coverage: {result_data['coverage']:.0%}")

            # Save to DB
            release = Release(
                repo_id=repo.id,
                tag_name=tag_name,
                name=tag_name,
                body_draft=result_data["changelog"],
            )
            db.add(release)
            await db.commit()
            print(f"
✓ Saved as draft release (ID: {release.id})")

        finally:
            await gh.close()


def main():
    parser = argparse.ArgumentParser(description="Generate changelog from merged PRs")
    parser.add_argument("--repo", required=True, help="Owner/repo format")
    parser.add_argument("--since", help="Tag to generate since")
    parser.add_argument("--tone", default="technical", choices=["technical", "user_facing", "marketing"])

    args = parser.parse_args()
    asyncio.run(generate_cli(args.repo, args.since, args.tone))


if __name__ == "__main__":
    main()

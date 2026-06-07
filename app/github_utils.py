"""GitHub App authentication and API utilities."""
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import httpx
from fastapi import HTTPException, Request

from app.config import get_settings


def verify_github_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)


class GitHubAppAuth:
    """Handles GitHub App JWT and installation token management."""

    def __init__(self):
        self.settings = get_settings()
        self._jwt_token: Optional[str] = None
        self._jwt_expires_at: float = 0
        self._install_tokens: Dict[int, tuple] = {}  # installation_id -> (token, expires_at)

    def _generate_jwt(self) -> str:
        """Generate a GitHub App JWT (valid for 10 minutes)."""
        import jwt

        now = int(time.time())
        payload = {
            "iat": now - 60,  # 1 min leeway
            "exp": now + 600,  # 10 minutes
            "iss": self.settings.github_app_id,
        }

        private_key = self.settings.github_private_key
        # Handle both PEM content and file path
        if private_key.startswith("-----"):
            key = private_key
        else:
            with open(private_key, "r") as f:
                key = f.read()

        return jwt.encode(payload, key, algorithm="RS256")

    def get_jwt(self) -> str:
        """Get cached or fresh JWT."""
        now = time.time()
        if not self._jwt_token or now >= self._jwt_expires_at - 60:
            self._jwt_token = self._generate_jwt()
            self._jwt_expires_at = now + 600
        return self._jwt_token

    async def get_installation_token(self, installation_id: int) -> str:
        """Get cached or fresh installation access token."""
        now = time.time()
        cached = self._install_tokens.get(installation_id)
        if cached and now < cached[1] - 60:
            return cached[0]

        jwt_token = self.get_jwt()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            token = data["token"]
            expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
            self._install_tokens[installation_id] = (token, expires_at.timestamp())
            return token

    async def get_repo_installation_token(self, owner: str, repo: str) -> str:
        """Get installation token for a specific repo."""
        jwt_token = self.get_jwt()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/installation",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            installation_id = resp.json()["id"]
            return await self.get_installation_token(installation_id)


# Singleton instance
github_auth = GitHubAppAuth()


class GitHubAPI:
    """GitHub API client using installation tokens."""

    def __init__(self, token: str):
        self.token = token
        self.client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    async def close(self):
        await self.client.aclose()

    async def get_merged_prs_since(
        self,
        owner: str,
        repo: str,
        since: Optional[datetime] = None,
        base: str = "main",
    ) -> List[Dict[str, Any]]:
        """Fetch merged PRs since a given date."""
        params = {
            "state": "closed",
            "sort": "updated",
            "direction": "desc",
            "per_page": 100,
            "base": base,
        }
        if since:
            # GitHub search API for better filtering
            q = f"repo:{owner}/{repo} is:pr is:merged"
            if since:
                q += f" merged:>={since.strftime('%Y-%m-%dT%H:%M:%SZ')}"

            prs = []
            page = 1
            while True:
                resp = await self.client.get(
                    "/search/issues",
                    params={"q": q, "per_page": 100, "page": page},
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break

                # Fetch full PR details for each
                for item in items:
                    pr_resp = await self.client.get(
                        f"/repos/{owner}/{repo}/pulls/{item['number']}"
                    )
                    if pr_resp.status_code == 200:
                        prs.append(pr_resp.json())

                if len(items) < 100:
                    break
                page += 1

            return prs
        else:
            # Simple PR list
            resp = await self.client.get(
                f"/repos/{owner}/{repo}/pulls",
                params={**params, "state": "closed"},
            )
            resp.raise_for_status()
            return [pr for pr in resp.json() if pr.get("merged_at")]

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Get files changed in a PR."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
            params={"per_page": 100},
        )
        resp.raise_for_status()
        return resp.json()

    async def create_release(
        self,
        owner: str,
        repo: str,
        tag_name: str,
        name: str,
        body: str,
        draft: bool = True,
        prerelease: bool = False,
    ) -> Dict[str, Any]:
        """Create a GitHub release."""
        resp = await self.client.post(
            f"/repos/{owner}/{repo}/releases",
            json={
                "tag_name": tag_name,
                "name": name,
                "body": body,
                "draft": draft,
                "prerelease": prerelease,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def update_release(
        self,
        owner: str,
        repo: str,
        release_id: int,
        body: str,
        draft: bool = False,
    ) -> Dict[str, Any]:
        """Update an existing release."""
        resp = await self.client.patch(
            f"/repos/{owner}/{repo}/releases/{release_id}",
            json={"body": body, "draft": draft},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_latest_release(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Get the latest release."""
        resp = await self.client.get(f"/repos/{owner}/{repo}/releases/latest")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def get_tags(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Get repository tags."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/tags",
            params={"per_page": 100},
        )
        resp.raise_for_status()
        return resp.json()

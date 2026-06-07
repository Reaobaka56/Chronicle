"""GitHub OAuth flow for user authentication."""
import secrets

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from app.config import get_settings
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/github")
async def github_login():
    """Redirect to GitHub OAuth."""
    settings = get_settings()
    state = secrets.token_urlsafe(32)

    # In production, store state in session/cache
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        f"&redirect_uri={settings.app_url}/auth/github/callback"
        f"&scope=read:user user:email"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/github/callback")
async def github_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle GitHub OAuth callback."""
    settings = get_settings()

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(status_code=400, detail="OAuth failed")

        # Fetch user info
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        user_resp.raise_for_status()
        github_user = user_resp.json()

    # Find or create user
    result = await db.execute(
        select(User).where(User.github_id == github_user["id"])
    )
    user = result.scalar_one_or_none()

    if user:
        user.github_login = github_user["login"]
        user.avatar_url = github_user.get("avatar_url")
        user.email = github_user.get("email")
    else:
        user = User(
            github_id=github_user["id"],
            github_login=github_user["login"],
            email=github_user.get("email"),
            avatar_url=github_user.get("avatar_url"),
        )
        db.add(user)

    await db.commit()

    # Return JWT token (simplified — use proper JWT library in production)
    return {
        "access_token": access_token,  # In production, generate your own JWT
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "github_login": user.github_login,
            "avatar_url": user.avatar_url,
            "plan_tier": user.plan_tier.value,
        },
    }

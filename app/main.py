"""PR Changelog Generator — FastAPI backend."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import webhooks, releases, repos, public, oauth, subscribers, stripe


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await init_db()
    yield


app = FastAPI(
    title="PR Changelog Generator",
    description="AI-powered changelog generation for GitHub releases",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourapp.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(oauth.router)
app.include_router(webhooks.router)
app.include_router(releases.router)
app.include_router(repos.router)
app.include_router(subscribers.router)
app.include_router(stripe.router)
app.include_router(public.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}

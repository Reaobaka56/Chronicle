"""Database configuration."""
import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/pr_changelog")

# Use NullPool for serverless environments, standard pool for persistent
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool if os.getenv("SERVERLESS") else None,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db():
    """Create tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
